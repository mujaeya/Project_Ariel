# ariel_client/src/core/screen_monitor.py (이 코드로 전체 교체)
import logging
import mss
import numpy as np
from skimage.metrics import structural_similarity as ssim
import cv2
from PySide6.QtCore import QObject, Signal, QRect, QThread

class ScreenMonitor(QObject):
    """
    지정된 화면 영역(QRect)을 지속적으로 감시하며,
    특정 무시 영역(ignored_rect)을 제외하고 의미있는 변화가 감지되었을 때
    이미지 데이터(bytes)를 포함한 시그널을 보냅니다.
    """
    image_changed = Signal(bytes)
    stopped = Signal()

    def __init__(self, rect: QRect, ignored_rect_func, parent=None):
        """
        :param rect: 감시할 전체 영역
        :param ignored_rect_func: 무시할 영역의 QRect를 반환하는 함수
        """
        super().__init__(parent)
        if rect.isNull() or rect.width() <= 0 or rect.height() <= 0:
            raise ValueError("감시할 영역(rect)이 유효하지 않습니다.")

        self._is_running = False
        self.monitor_rect = {
            "top": rect.y(),
            "left": rect.x(),
            "width": rect.width(),
            "height": rect.height()
        }
        # [수정] 무시할 영역의 좌표를 반환하는 함수를 멤버 변수로 저장
        self.get_ignored_rect = ignored_rect_func
        self.previous_frame = None
        self.ssim_threshold = 0.95
        self.interval_ms = 200

    def start_monitoring(self):
        """메인 감시 루프를 실행합니다."""
        self._is_running = True
        logging.info(f"{self.monitor_rect} 영역에 대한 감시를 시작합니다.")

        with mss.mss() as sct:
            while self._is_running:
                # 1. 화면 캡처
                sct_img = sct.grab(self.monitor_rect)
                current_frame_bgra = np.array(sct_img)

                # 2. [핵심 로직] '자기 인식' - 오버레이 창 무시하기
                ignored_rect = self.get_ignored_rect()
                if ignored_rect:
                    # 감시 영역(monitor_rect) 기준으로 무시할 영역의 상대 좌표 계산
                    # ignored_rect는 전체 화면 기준 좌표이므로, 감시 영역의 시작점(left, top)을 빼줘야 함
                    relative_ignored_rect = ignored_rect.translated(-self.monitor_rect['left'], -self.monitor_rect['top'])
                    
                    # 겹치는 영역이 실제로 있는지 확인
                    capture_area = QRect(0, 0, self.monitor_rect['width'], self.monitor_rect['height'])
                    intersection = capture_area.intersected(relative_ignored_rect)

                    if not intersection.isEmpty():
                        # 겹치는 영역을 검은색 사각형으로 칠해서 AI가 인식하지 못하게 함
                        cv2.rectangle(
                            current_frame_bgra,
                            (intersection.left(), intersection.top()),
                            (intersection.right(), intersection.bottom()),
                            (0, 0, 0, 255), # 검은색 (BGRA)
                            -1 # 채우기
                        )

                # 3. 이미지 전처리 및 비교
                current_frame_gray = cv2.cvtColor(current_frame_bgra, cv2.COLOR_BGRA2GRAY)
                if self.previous_frame is not None:
                    score = ssim(self.previous_frame, current_frame_gray, data_range=current_frame_gray.max() - current_frame_gray.min())
                    if score < self.ssim_threshold:
                        logging.info(f"변화 감지! (유사도: {score:.4f})")
                        _, img_bytes = cv2.imencode('.png', current_frame_bgra)
                        self.image_changed.emit(img_bytes.tobytes())

                self.previous_frame = current_frame_gray
                QThread.msleep(self.interval_ms)

        logging.info("화면 감시가 중지되었습니다.")
        self.stopped.emit()

    def stop(self):
        """감시 루프를 중지하도록 요청합니다."""
        self._is_running = False