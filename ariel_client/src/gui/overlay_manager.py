import logging
from PySide6.QtCore import QObject, QRect, Slot
from .overlay_window import OverlayWindow, OcrPatchWindow # [추가] OcrPatchWindow 임포트

logger = logging.getLogger(__name__)

class OverlayManager(QObject):
    def __init__(self, config_manager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.stt_overlay = None
        self.ocr_patch_windows = [] # [수정] OCR 오버레이를 단일 객체가 아닌 리스트로 관리

    def _ensure_stt_overlay(self):
        if not self.stt_overlay:
            self.stt_overlay = OverlayWindow(mode='stt', config_manager=self.config_manager)
            # [개선] 창이 닫힐 때 참조를 바로 정리하도록 람다 함수 사용
            self.stt_overlay.destroyed.connect(lambda: setattr(self, 'stt_overlay', None))
            logger.info("STT 오버레이 창이 생성되었습니다.")
            
    @Slot()
    def show_stt_overlay(self):
        self._ensure_stt_overlay()
        if not self.stt_overlay.isVisible(): self.stt_overlay.show()
        self.stt_overlay.add_stt_message("시스템", "음성 번역을 시작합니다.", is_system=True)

    @Slot()
    def hide_stt_overlay(self):
        if self.stt_overlay: 
            self.stt_overlay.hide()
            self.stt_overlay.clear_stt_messages()

    @Slot(str)
    def add_system_message_to_stt(self, message: str):
        if self.stt_overlay and self.stt_overlay.isVisible():
            self.stt_overlay.add_stt_message("시스템", message, is_system=True)

    @Slot(str, dict)
    def add_stt_translation(self, original: str, results: dict):
        self._ensure_stt_overlay()
        if not self.stt_overlay.isVisible(): self.stt_overlay.show()
        target_lang = list(results.keys())[0]
        self.stt_overlay.add_stt_message(original, results[target_lang])

    @Slot(list)
    def show_ocr_patches(self, patches_data: list):
        """[핵심 수정] 이전 패치를 모두 지우고 새 패치 창들을 생성합니다."""
        self.hide_ocr_overlay() # 이전 창들 제거
        if not patches_data: return

        style_config = self.config_manager.get("ocr_overlay_style", {})
        for patch_info in patches_data:
            patch_window = OcrPatchWindow(patch_info, style_config)
            self.ocr_patch_windows.append(patch_window)
            patch_window.show()

    @Slot()
    def hide_ocr_overlay(self):
        """[핵심 수정] 모든 OCR 패치 창을 닫고 리스트를 비웁니다."""
        while self.ocr_patch_windows:
            # pop()으로 리스트에서 제거하고 close()로 창을 닫습니다.
            # close()는 내부적으로 deleteLater()를 호출하여 안전하게 소멸됩니다.
            self.ocr_patch_windows.pop().close() 
            
    def get_stt_overlay_geometry(self) -> QRect:
        return self.stt_overlay.geometry() if self.stt_overlay and self.stt_overlay.isVisible() else QRect()