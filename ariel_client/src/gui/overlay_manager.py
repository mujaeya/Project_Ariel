# ariel_client/src/gui/overlay_manager.py (이 코드로 전체 교체)
import logging
from PySide6.QtCore import Slot, QObject, QRect
from .overlay_window import OverlayWindow, OcrPatchWindow
from ..config_manager import ConfigManager

logger = logging.getLogger(__name__)

class OverlayManager(QObject):
    def __init__(self, config_manager: ConfigManager, parent: QObject | None = None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.stt_overlay = None
        self.ocr_patches = []

    def _ensure_stt_overlay(self):
        """STT 오버레이 객체가 존재하고 화면에 표시되도록 보장합니다."""
        if not self.stt_overlay or not self.stt_overlay.isVisible():
            self.stt_overlay = OverlayWindow(config_manager=self.config_manager)
            self.stt_overlay.show()
    
    def show_stt_overlay(self):
        self._ensure_stt_overlay()
        self.stt_overlay.activateWindow()

    def hide_stt_overlay(self):
        if self.stt_overlay:
            self.stt_overlay.close()
            self.stt_overlay = None

    def hide_ocr_overlay(self):
        for patch in self.ocr_patches:
            patch.close()
        self.ocr_patches.clear()

    @Slot(str, str)
    def add_stt_translation(self, original_text: str, translated_text: str):
        """번역 결과를 오버레이에 추가합니다."""
        self._ensure_stt_overlay()
        self.stt_overlay.add_translation_item(original_text, translated_text)

    @Slot(str)
    def update_stt_status(self, message: str):
        """STT 오버레이의 상태 메시지를 업데이트합니다."""
        self._ensure_stt_overlay() # 상태 메시지를 표시하기 위해서라도 창이 필요
        self.stt_overlay.update_status_text(message)

    @Slot(str)
    def update_ocr_status(self, message: str):
        if message:
            logger.info(f"[OCR STATUS]: {message}")

    @Slot(list)
    def show_ocr_patches(self, patches: list):
        self.hide_ocr_overlay()
        style_config = self.config_manager.get("ocr_overlay_style")
        for patch_info in patches:
            patch_window = OcrPatchWindow(patch_info, style_config)
            patch_window.show()
            self.ocr_patches.append(patch_window)

    def get_stt_overlay_geometry(self) -> QRect:
        if self.stt_overlay and self.stt_overlay.isVisible():
            return self.stt_overlay.geometry()
        return QRect()
        
    @Slot()
    def on_settings_changed(self):
        """[추가] 설정 변경 시그널을 수신하여 활성화된 오버레이에 전파합니다."""
        logger.debug("OverlayManager: 설정 변경 시그널 수신.")
        if self.stt_overlay and self.stt_overlay.isVisible():
            self.stt_overlay.on_settings_changed()