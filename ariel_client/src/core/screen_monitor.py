# ariel_client/src/core/screen_monitor.py (이 코드로 전체 교체)
import logging
import mss
import numpy as np
import cv2
from PySide6.QtCore import QObject, Signal, QRect, QThread

class ScreenMonitor(QObject):
    """
    지정된 화면 영역을 감시하며, '자기 인식'으로 오버레이 창을 제외하고
    의미있는 변화가 감지되었을 때 이미지 데이터(bytes) 시그널을 보냅니다.
    """
    image_changed = Signal(bytes)
    stopped = Signal()

    def __init__(self, rect: QRect, ignored_rect_func, parent=None):
        super().__init__(parent)
        if rect.isNull() or rect.width() <= 0 or rect.height() <= 0:
            raise ValueError("감시할 영역(rect)이 유효하지 않습니다.")

        self._is_running = False
        self.monitor_rect = {"top": rect.y(), "left": rect.x(), "width": rect.width(), "height": rect.height()}
        self.get_ignored_rect = ignored_rect_func
        
        # [성능 개선] SSIM 대신 더 가벼운 히스토그램 비교로 변경
        self.previous_hist = None
        self.hist_threshold = 0.98 # 히스토그램 유사도 임계값
        self.interval_ms = 250 # 감시 간격 조정

    def start_monitoring(self):
        self._is_running = True
        logging.info(f"자기 인식 OCR 감시 시작: {self.monitor_rect}")

        with mss.mss() as sct:
            while self._is_running:
                # 1. 화면 캡처
                sct_img = sct.grab(self.monitor_rect)
                current_frame_bgra = np.array(sct_img)
                
                # 2. [핵심] '자기 인식' - 오버레이 창 영역 무시
                ignored_rect = self.get_ignored_rect()
                if ignored_rect:
                    # 감시 영역 기준으로 무시할 영역의 상대 좌표 계산
                    relative_ignored_rect = ignored_rect.translated(-self.monitor_rect['left'], -self.monitor_rect['top'])
                    capture_area_rect = QRect(0, 0, self.monitor_rect['width'], self.monitor_rect['height'])
                    intersection = capture_area_rect.intersected(relative_ignored_rect)

                    if not intersection.isEmpty():
                        # 해당 영역을 검은색으로 칠해버림
                        cv2.rectangle(
                            current_frame_bgra,
                            (intersection.left(), intersection.top()),
                            (intersection.right(), intersection.bottom()),
                            (0, 0, 0, 255), -1
                        )
                
                # 3. 이미지 비교 (히스토그램)
                current_frame_gray = cv2.cvtColor(current_frame_bgra, cv2.COLOR_BGRA2GRAY)
                current_hist = cv2.calcHist([current_frame_gray], [0], None, [256], [0, 256])
                cv2.normalize(current_hist, current_hist, 0, 1, cv2.NORM_MINMAX)

                if self.previous_hist is not None:
                    score = cv2.compareHist(self.previous_hist, current_hist, cv2.HISTCMP_CORREL)
                    if score < self.hist_threshold:
                        logging.info(f"화면 변화 감지! (유사도: {score:.4f})")
                        _, img_bytes = cv2.imencode('.png', current_frame_bgra)
                        self.image_changed.emit(img_bytes.tobytes())
                
                self.previous_hist = current_hist
                QThread.msleep(self.interval_ms)

        logging.info("화면 감시가 중지되었습니다.")
        self.stopped.emit()

    def stop(self):
        self._is_running = False