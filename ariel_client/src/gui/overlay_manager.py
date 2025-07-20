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
            self.stt_overlay = OverlayWindow(config_manager=self.config_manager)
    
    # ... (show/hide 메서드들은 기존과 동일, 변경 없음) ...
    def show_stt_overlay(self):
        self._ensure_stt_overlay()
        self.stt_overlay.show()
        self.stt_overlay.activateWindow()

    def hide_stt_overlay(self):
        if self.stt_overlay:
            self.stt_overlay.close()
            self.stt_overlay = None

    def hide_ocr_overlay(self):
        for patch in self.ocr_patches:
            patch.close()
        self.ocr_patches.clear()

    @Slot(str, dict)
    def add_stt_translation(self, original_text: str, translations: dict):
        self._ensure_stt_overlay()
        if not self.stt_overlay.isVisible(): self.stt_overlay.show()
        translated_text = next(iter(translations.values()), "Translation failed")
        self.stt_overlay.add_stt_message(original_text, translated_text)

    @Slot(str)
    def add_system_message_to_stt(self, message: str):
        if not self.stt_overlay:
            # STT 오버레이가 아직 없는 상태에서 오는 시스템 메시지는 무시하거나,
            # 혹은 이 메시지가 오면 오버레이를 띄울 수도 있습니다. 지금은 무시.
            return
        if not message.strip():
            # 메시지가 비어있으면 오버레이를 숨기지 않고, 마지막 메시지를 유지.
            # 상태 메시지가 "음성 듣는 중..."으로 고정되도록 합니다.
            return 
        self.stt_overlay.add_stt_message("", message, is_system=True)

    # [신규] OCR 상태 메시지를 처리할 슬롯 추가
    @Slot(str)
    def update_ocr_status(self, message: str):
        """OCR 처리 상태를 로깅합니다. (향후 OCR 오버레이에 상태 표시용으로 확장 가능)"""
        if message:
            logger.info(f"[OCR STATUS]: {message}")
        # 현재는 OCR 오버레이에 상태를 표시하는 기능이 없으므로 로깅만 합니다.

    @Slot(list)
    def show_ocr_patches(self, patches: list):
        # ... (기존과 동일, 변경 없음) ...
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