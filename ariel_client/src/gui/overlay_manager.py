import logging
from PySide6.QtCore import QObject, QRect, Slot
from PySide6.QtGui import QGuiApplication
from .overlay_window import OverlayWindow

logger = logging.getLogger(__name__)

class OverlayManager(QObject):
    def __init__(self, config_manager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        
        self.stt_overlay = None
        self.ocr_overlay = None

    def _ensure_stt_overlay(self):
        if not self.stt_overlay:
            self.stt_overlay = OverlayWindow(mode='stt', config_manager=self.config_manager)
            self.stt_overlay.destroyed.connect(self._on_stt_overlay_destroyed)
            logger.info("STT 오버레이 창이 생성되었습니다.")
            
    def _on_stt_overlay_destroyed(self):
        # 창이 (예: 사용자에 의해) 닫혔을 때 참조를 정리
        self.stt_overlay = None
        logger.info("STT 오버레이 창이 소멸되었습니다.")

    def _ensure_ocr_overlay(self):
        if not self.ocr_overlay:
            self.ocr_overlay = OverlayWindow(mode='ocr', config_manager=self.config_manager)
            logger.info("OCR 오버레이 창이 생성되었습니다.")

    @Slot()
    def show_stt_overlay(self):
        self._ensure_stt_overlay()
        if not self.stt_overlay.isVisible():
            self.stt_overlay.show()
        self.stt_overlay.add_stt_message("시스템", "음성 번역을 시작합니다.", is_system=True)

    @Slot()
    def hide_stt_overlay(self):
        if self.stt_overlay:
            self.stt_overlay.hide()
            self.stt_overlay.clear_stt_messages()

    @Slot()
    def hide_ocr_overlay(self):
        if self.ocr_overlay:
            self.ocr_overlay.hide_patches()

    @Slot(str)
    def add_system_message_to_stt(self, message: str):
        if self.stt_overlay and self.stt_overlay.isVisible():
            self.stt_overlay.add_stt_message("시스템", message, is_system=True)

    @Slot(str, dict)
    def add_stt_translation(self, original: str, results: dict):
        self._ensure_stt_overlay()
        if not self.stt_overlay.isVisible():
            self.stt_overlay.show()
            
        target_lang = list(results.keys())[0]
        translation = results[target_lang]
        self.stt_overlay.add_stt_message(original, translation)

    @Slot(list)
    def show_ocr_patches(self, patches_data: list):
        self._ensure_ocr_overlay()
        self.ocr_overlay.update_ocr_patches(patches_data)
        
    def get_stt_overlay_geometry(self) -> QRect:
        if self.stt_overlay and self.stt_overlay.isVisible():
            return self.stt_overlay.geometry()
        return QRect()