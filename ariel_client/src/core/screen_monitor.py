# ariel_client/src/core/screen_monitor.py (이 코드로 전체 교체)
import logging
from PySide6.QtCore import QObject, Slot, Signal, QThread, QRect
from mss import mss
import numpy as np
from skimage.metrics import structural_similarity as ssim
from PIL import Image
import io

logger = logging.getLogger(__name__)

class ScreenMonitor(QObject):
    image_changed = Signal(bytes)
    finished = Signal()
    status_updated = Signal(str)

    def __init__(self, rect: QRect, stt_overlay_getter):
        super().__init__(None)
        if rect.isNull() or rect.width() <= 0 or rect.height() <= 0:
            raise ValueError("유효하지 않은 감시 영역입니다.")
        
        self.monitor_rect = {'top': rect.top(), 'left': rect.left(), 'width': rect.width(), 'height': rect.height()}
        self.get_stt_overlay_geometry = stt_overlay_getter
        self._is_running = False
        self.last_image_np = None
        self.similarity_threshold = 0.95
        self.check_interval_ms = 500
        logger.info(f"ScreenMonitor 초기화 완료. 감시 영역: {self.monitor_rect}")

    @Slot()
    def stop(self):
        logger.info("화면 감시 중지 요청 수신.")
        self._is_running = False

    @Slot()
    def start_monitoring(self):
        if self._is_running:
            logger.warning("이미 화면 감시가 실행 중입니다.")
            return

        self._is_running = True
        logger.info(f"화면 감시 시작: {self.monitor_rect['left']},{self.monitor_rect['top']} {self.monitor_rect['width']}x{self.monitor_rect['height']}")

        # [수정] mss 객체를 스레드 내에서 생성하고 with 문으로 관리
        try:
            with mss() as sct:
                while self._is_running:
                    try:
                        sct_img = sct.grab(self.monitor_rect)
                        current_image_np = np.array(sct_img)
                        
                        stt_overlay_geom = self.get_stt_overlay_geometry()
                        if stt_overlay_geom.isValid() and stt_overlay_geom.intersects(QRect(**self.monitor_rect)):
                             logger.warning("감시 영역이 STT 오버레이와 겹칩니다. 감시를 일시 중지합니다.")
                             QThread.msleep(2000)
                             continue

                        if self.last_image_np is not None:
                            similarity = ssim(self.last_image_np, current_image_np, channel_axis=2, data_range=255)
                            if similarity < self.similarity_threshold:
                                logger.info(f"화면 변경 감지 (유사도: {similarity:.4f}). 이미지 처리 요청.")
                                img_bytes = self.to_bytes(sct_img)
                                self.image_changed.emit(img_bytes)
                        
                        self.last_image_np = current_image_np
                        QThread.msleep(self.check_interval_ms)

                    except Exception as e:
                        logger.error(f"화면 감시 루프 중 예외 발생: {e}", exc_info=True)
                        self._is_running = False # 루프 중단

        except Exception as e:
            logger.error(f"mss 초기화 또는 주 루프 진입 실패: {e}", exc_info=True)
        finally:
            self._is_running = False
            self.last_image_np = None
            logger.info("화면 감시가 종료되었습니다.")
            self.finished.emit()

    def to_bytes(self, sct_img) -> bytes:
        img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format='PNG')
        return img_byte_arr.getvalue()