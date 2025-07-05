# ariel_client/src/gui/overlay_manager.py (이 코드로 전체 교체)
import logging
from PySide6.QtCore import QObject, Slot, QRect, QPoint
from PySide6.QtWidgets import QApplication
from .overlay_window import OverlayWindow
from ..config_manager import ConfigManager

class OverlayManager(QObject):
    """
    [핵심 수정] STT와 OCR 전용 오버레이 창을 각각 생성하고 중앙에서 관리합니다.
    이를 통해 두 기능의 표시 방식이 충돌하지 않도록 합니다.
    """
    def __init__(self, config_manager: ConfigManager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        
        # STT와 OCR 오버레이를 별개의 인스턴스로 관리
        self.stt_overlay = None
        self.ocr_overlay = None

    def _ensure_stt_overlay(self):
        """STT 오버레이가 없으면 생성하고 화면에 표시합니다."""
        if self.stt_overlay is None or not self.stt_overlay.isVisible():
            # [수정] overlay_type을 명시하고 config_manager를 전달합니다.
            self.stt_overlay = OverlayWindow(config_manager=self.config_manager, overlay_type='stt')
            self.stt_overlay.show()
    
    def _ensure_ocr_overlay(self):
        """OCR 오버레이가 없으면 생성합니다. (표시는 OCR 요청 시)"""
        if self.ocr_overlay is None:
            # [수정] overlay_type을 명시하고 config_manager를 전달합니다.
            self.ocr_overlay = OverlayWindow(config_manager=self.config_manager, overlay_type='ocr')

    @Slot(str)
    def update_status(self, message: str):
        """
        [사용되지 않음 - OverlayWindow가 자체적으로 상태를 가짐]
        이전 버전과의 호환성을 위해 메서드는 남겨두지만, 현재 구조에서는
        각 OverlayWindow가 개별적으로 관리되므로 중앙 상태 업데이트는 필요하지 않습니다.
        향후 시스템 전역 상태 표시줄이 필요할 경우를 대비해 남겨둘 수 있습니다.
        """
        logging.debug(f"상태 메시지 수신(사용 안 함): {message}")


    @Slot(str, dict, str)
    def add_translation(self, original: str, results: dict, source: str):
        """
        Worker로부터 받은 번역 결과를 소스(stt/ocr)에 맞는 오버레이로 전달합니다.
        """
        if not original.strip() or not results:
            return

        if source == 'stt':
            self._ensure_stt_overlay()
            self.stt_overlay.add_translation(original, results, source)
            self.stt_overlay.show() # 항상 보이도록 보장

        elif source == 'ocr':
            # OCR은 위치 정보(geometry)가 필요하므로 별도의 메서드로 처리
            logging.warning("add_translation이 'ocr' 소스로 호출됨. "
                            "위치 정보가 없는 OCR 표시는 지원되지 않습니다. "
                            "show_ocr_translation_at를 사용하세요.")

    def add_system_message_to_stt(self, message: str):
        """
        STT 오버레이에 시스템 메시지를 표시합니다.
        (예: "음성 듣는 중...", "오디오 장치 없음")
        """
        if self.stt_overlay and self.stt_overlay.isVisible():
            # 기존 'add_translation' 메서드를 재활용하여 시스템 메시지를 표시합니다.
            # 'SYSTEM' 키를 사용해 일반 번역과 구분합니다.
            self.add_translation("SYSTEM", { "message": message }, "stt")

    def show_ocr_translation_at(self, original: str, results: dict, geometry: QRect):
        """[신규] OCR 번역 결과를 지정된 위치에 표시합니다."""
        self._ensure_ocr_overlay()

        # OCR 창의 내용을 업데이트합니다.
        self.ocr_overlay.add_translation(original, results, 'ocr')
        
        # 번역 내용에 맞게 창 크기를 먼저 조절합니다.
        self.ocr_overlay.adjustSize()
        
        # 그 다음, 지정된 위치로 창을 이동시킵니다.
        # OCR 결과는 보통 캡처된 영역 바로 아래에 표시됩니다.
        screen_geometry = QApplication.primaryScreen().geometry()
        x = geometry.x()
        y = geometry.y() + geometry.height() + 5 # 캡처 영역 바로 아래

        # 오버레이가 화면 밖으로 나가지 않도록 좌표 보정
        if x + self.ocr_overlay.width() > screen_geometry.width():
            x = screen_geometry.width() - self.ocr_overlay.width()
        if y + self.ocr_overlay.height() > screen_geometry.height():
            y = geometry.y() - self.ocr_overlay.height() - 5 # 캡처 영역 위로 이동

        self.ocr_overlay.move(QPoint(x, y))
        self.ocr_overlay.show()

    def hide_stt_overlay(self):
        if self.stt_overlay:
            self.stt_overlay.hide()

    def hide_ocr_overlay(self):
        if self.ocr_overlay:
            self.ocr_overlay.hide()

    def hide_all(self):
        """모든 오버레이 창을 숨기고 리소스를 해제합니다."""
        if self.stt_overlay:
            self.stt_overlay.hide()
            self.stt_overlay.deleteLater()
            self.stt_overlay = None
        
        if self.ocr_overlay:
            self.ocr_overlay.hide()
            self.ocr_overlay.deleteLater()
            self.ocr_overlay = None

    def get_overlay_geometry(self) -> QRect | None:
        """
        '자기 인식 OCR'을 위해 현재 STT 오버레이 창의 화면 좌표(QRect)를 반환합니다.
        """
        if self.stt_overlay and self.stt_overlay.isVisible():
            return self.stt_overlay.geometry()
        return None