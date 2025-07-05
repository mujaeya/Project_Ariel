# F:/projects/Project_Ariel/ariel_client/src/gui/overlay_manager.py (최종 수정본)
import logging
from PySide6.QtCore import QObject, QRect, Qt, Slot
from .overlay_window import OverlayWindow

logger = logging.getLogger(__name__)

class OverlayManager(QObject):
    """
    STT 및 OCR 번역 결과를 표시하는 여러 오버레이 창을 중앙에서 관리합니다.
    """
    def __init__(self, config_manager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        
        self.stt_overlay = None
        self.ocr_overlay = None
        
        # 설정 로드
        self.stt_style = self.config_manager.get("stt_overlay_style", {})
        self.ocr_style = self.config_manager.get("ocr_overlay_style", {})

    def _ensure_stt_overlay(self):
        """STT 자막용 오버레이 창을 생성하고 초기화합니다."""
        if not self.stt_overlay:
            self.stt_overlay = OverlayWindow(mode='stt', style_config=self.stt_style)
            # 초기 위치 및 크기 설정 (설정 파일 기반)
            pos_x = self.config_manager.get("stt_overlay_pos_x", 100)
            pos_y = self.config_manager.get("stt_overlay_pos_y", 100)
            width = self.config_manager.get("stt_overlay_width", 800)
            height = self.config_manager.get("stt_overlay_height", 200)
            self.stt_overlay.setGeometry(pos_x, pos_y, width, height)
            logger.info("STT 오버레이 창이 생성되었습니다.")

    def _ensure_ocr_overlay(self):
        """OCR 결과 표시용 오버레이 창을 생성하고 초기화합니다."""
        if not self.ocr_overlay:
            self.ocr_overlay = OverlayWindow(mode='ocr', style_config=self.ocr_style)
            logger.info("OCR 오버레이 창이 생성되었습니다.")

    @Slot()
    def show_stt_overlay(self):
        """STT 오버레이를 화면에 표시합니다."""
        self._ensure_stt_overlay()
        self.stt_overlay.show()
        self.stt_overlay.add_stt_message("시스템", "음성 번역을 시작합니다.", is_system=True)

    @Slot()
    def hide_stt_overlay(self):
        """STT 오버레이를 화면에서 숨깁니다."""
        if self.stt_overlay:
            self.stt_overlay.hide()
            self.stt_overlay.clear_stt_messages()

    @Slot(str)
    def add_system_message_to_stt(self, message: str):
        """시스템 메시지를 STT 오버레이에 추가합니다."""
        if self.stt_overlay:
            self.stt_overlay.add_stt_message("시스템", message, is_system=True)

    @Slot(str, dict)
    def add_stt_translation(self, original: str, results: dict):
        """번역 결과를 STT 오버레이에 추가합니다."""
        self._ensure_stt_overlay()
        target_lang = list(results.keys())[0]
        self.stt_overlay.add_stt_message(original, results[target_lang])

    @Slot(list)
    def show_ocr_patches(self, patches_data: list):
        """OCR 번역 결과를 패치 형태로 화면에 표시합니다."""
        self._ensure_ocr_overlay()
        self.ocr_overlay.update_ocr_patches(patches_data)
        
    def get_stt_overlay_geometry(self) -> QRect:
        """STT 오버레이의 현재 지오메트리를 반환합니다."""
        if self.stt_overlay and self.stt_overlay.isVisible():
            return self.stt_overlay.geometry()
        return QRect()