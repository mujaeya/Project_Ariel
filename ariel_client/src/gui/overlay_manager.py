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
        if not self.stt_overlay or not self.stt_overlay.isVisible():
            # [수정] OverlayWindow 생성자에서 mode 인자 제거
            self.stt_overlay = OverlayWindow(config_manager=self.config_manager)
        
    def show_stt_overlay(self):
        self._ensure_stt_overlay()
        self.stt_overlay.show()
        self.stt_overlay.activateWindow()

    def hide_stt_overlay(self):
        if self.stt_overlay:
            self.stt_overlay.close()
            self.stt_overlay = None

    def show_ocr_overlay(self):
        # OCR은 개별 패치로 표시되므로 메인 오버레이 창은 없음
        pass

    def hide_ocr_overlay(self):
        for patch in self.ocr_patches:
            patch.close()
        self.ocr_patches.clear()

    @Slot(str, dict)
    def add_stt_translation(self, original_text: str, translations: dict):
        self._ensure_stt_overlay()
        if not self.stt_overlay.isVisible(): self.stt_overlay.show()
        # 첫 번째 (아마도 유일한) 번역 결과를 사용
        translated_text = next(iter(translations.values()), "Translation failed")
        self.stt_overlay.add_stt_message(original_text, translated_text)

    @Slot(str)
    def add_system_message_to_stt(self, message: str):
        if not message.strip() or not self.stt_overlay: return
        self.stt_overlay.add_stt_message("", message, is_system=True)

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