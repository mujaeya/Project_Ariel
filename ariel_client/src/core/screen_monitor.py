# ariel_client/src/core/screen_monitor.py (수정 후)
import logging
import mss
import numpy as np
import io
from PIL import Image, ImageDraw
from skimage.metrics import structural_similarity as ssim
from PySide6.QtCore import QObject, Signal, QRect, QThread, Slot

logger = logging.getLogger(__name__)

class ScreenMonitor(QObject):
    """
    지정된 화면 영역을 감시하며, 구조적 유사성(SSIM)을 기반으로
    의미 있는 변화가 감지될 때 이미지 바이트를 시그널로 보냅니다.
    """
    # [수정] TranslationWorker와 시그니처를 맞추기 위해 QRect 인자 제거
    image_changed = Signal(bytes)
    stopped = Signal()

    def __init__(self, rect: QRect, ignored_rects_func, parent=None):
        super().__init__(parent)
        if rect.isNull() or rect.width() <= 0 or rect.height() <= 0:
            raise ValueError("감시할 영역(rect)이 유효하지 않습니다.")

        self._is_running = False
        self.monitor_rect = {"top": rect.y(), "left": rect.x(), "width": rect.width(), "height": rect.height()}
        self.get_ignored_rects = ignored_rects_func
        
        self.sct = mss.mss()
        self.last_image_gray = None
        
        # 설정값 (필요 시 ConfigManager에서 로드)
        self.similarity_threshold = 0.95 # 이미지 유사도 임계값
        self.check_interval_ms = 250     # 감시 간격 (ms)
        
        logger.info(f"ScreenMonitor 초기화 완료. 감시 영역: {self.monitor_rect}")

    def _process_image(self, img_bgra: np.ndarray) -> np.ndarray:
        """이미지를 비교에 적합한 회색조로 변환합니다."""
        # BGRA -> Gray
        return np.dot(img_bgra[...,:3], [0.114, 0.587, 0.299]).astype(np.uint8)

    @Slot()
    def start_monitoring(self):
        self._is_running = True
        logger.info(f"화면 감시 스레드 시작. 간격: {self.check_interval_ms}ms, 유사도 임계값: {self.similarity_threshold}")

        try:
            # 첫 번째 기준 이미지 캡처
            sct_img = self.sct.grab(self.monitor_rect)
            img_bgra = np.array(sct_img)
            self.last_image_gray = self._process_image(img_bgra)

            while self._is_running:
                sct_img = self.sct.grab(self.monitor_rect)
                current_frame_bgra = np.array(sct_img)
                current_frame_gray = self._process_image(current_frame_bgra)
                
                # 구조적 유사성(SSIM) 계산
                score = ssim(self.last_image_gray, current_frame_gray)
                
                if score < self.similarity_threshold:
                    logger.info(f"화면 변화 감지! (유사도: {score:.4f})")
                    self.last_image_gray = current_frame_gray
                    
                    pil_img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
                    
                    # 무시할 영역(STT 오버레이 등)을 투명하게 처리
                    ignored_rects = self.get_ignored_rects()
                    if ignored_rects:
                        draw = ImageDraw.Draw(pil_img)
                        for ignored_rect in ignored_rects:
                            # 캡처 영역 기준 상대 좌표로 변환
                            relative_rect = ignored_rect.translated(-self.monitor_rect['left'], -self.monitor_rect['top'])
                            draw.rectangle(
                                (relative_rect.left(), relative_rect.top(), relative_rect.right(), relative_rect.bottom()),
                                fill="black" # 검은색으로 칠해 텍스트 인식을 방지
                            )

                    # 이미지를 바이트로 변환하여 전송
                    with io.BytesIO() as byte_io:
                        pil_img.save(byte_io, format='PNG')
                        img_bytes = byte_io.getvalue()

                    # [수정] QRect 없이 이미지 바이트만 전송
                    self.image_changed.emit(img_bytes)
                
                # QThread가 다른 이벤트를 처리할 수 있도록 CPU 양보
                QThread.msleep(self.check_interval_ms)
        
        except Exception as e:
            logger.error(f"화면 감시 루프 중 예외 발생: {e}", exc_info=True)
        
        finally:
            self.sct.close()
            logger.info("화면 감시가 중지되고 'stopped' 시그널을 방출합니다.")
            self.stopped.emit()

    @Slot()
    def stop(self):
        """화면 감시 루프를 안전하게 중지하도록 요청합니다."""
        if not self._is_running:
            return
        logger.info("화면 감시 중지 요청 수신.")
        self._is_running = False