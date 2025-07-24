# ariel_client/src/gui/overlay_manager.py (V12.4: 실시간 처리 방식)
import logging
from PySide6.QtCore import Slot, QObject, QRect, QTimer

from .overlay_window import OverlayWindow, OcrPatchWindow
from ..config_manager import ConfigManager

logger = logging.getLogger(__name__)

class OverlayManager(QObject):
    def __init__(self, config_manager: ConfigManager, parent: QObject | None = None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.stt_overlay = None
        self.ocr_patches = []

        # [추가] 실시간 자막 조립을 위한 변수들
        self.last_text_update_time = 0
        self.current_stt_line_original = ""
        self.current_stt_line_translated = ""
        
        # [추가] 문장이 끝났는지 판단하기 위한 타이머
        # 1.5초 동안 새로운 텍스트 조각이 없으면, 문장이 끝난 것으로 간주하고 줄을 내림
        self.sentence_end_timer = QTimer(self)
        self.sentence_end_timer.setInterval(1500) # 1.5초
        self.sentence_end_timer.setSingleShot(True)
        self.sentence_end_timer.timeout.connect(self.finalize_stt_sentence)

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
    def add_stt_chunk(self, original_chunk: str, translated_chunk: str):
        """[수정] 번역된 '조각'을 받아 기존 자막에 이어 붙입니다."""
        self._ensure_stt_overlay()
        
        if self.sentence_end_timer.isActive():
            self.sentence_end_timer.stop()

        self.current_stt_line_original += f" {original_chunk.strip()}"
        self.current_stt_line_translated += f" {translated_chunk.strip()}"
        
        # [핵심 수정] 새 메서드 이름(update_item)을 사용하고, is_final=False로 호출합니다.
        self.stt_overlay.update_item(
            self.current_stt_line_original.strip(),
            self.current_stt_line_translated.strip(),
            is_final=False
        )

        self.sentence_end_timer.start()

    @Slot()
    def finalize_stt_sentence(self):
        """타이머 시간이 다 되면 호출되어, 현재까지의 자막을 한 줄로 확정합니다."""
        if not self.current_stt_line_translated.strip():
            return

        logger.info(f"Finalizing sentence: {self.current_stt_line_translated.strip()}")
        
        self._ensure_stt_overlay()
        # [핵심 수정] 새 메서드 이름(update_item)을 사용하고, is_final=True로 호출합니다.
        self.stt_overlay.update_item(
            self.current_stt_line_original.strip(),
            self.current_stt_line_translated.strip(),
            is_final=True
        )
        
        self.current_stt_line_original = ""
        self.current_stt_line_translated = ""

    @Slot(str)
    def update_stt_status(self, message: str):
        self._ensure_stt_overlay()
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
        logger.debug("OverlayManager: 설정 변경 시그널 수신.")
        if self.stt_overlay and self.stt_overlay.isVisible():
            self.stt_overlay.on_settings_changed()