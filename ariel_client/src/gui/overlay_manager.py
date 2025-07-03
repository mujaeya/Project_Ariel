# ariel_client/src/gui/overlay_manager.py (이 코드로 전체 교체)
import logging
from PySide6.QtCore import QObject, Slot, QRect
from .overlay_window import OverlayWindow
from ..config_manager import ConfigManager

class OverlayManager(QObject):
    """
    모든 번역 결과와 상태 메시지를 제어하고,
    단일 지능형 오버레이 창(OverlayWindow)을 관리하는 중앙 허브.
    """
    def __init__(self, config_manager: ConfigManager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.overlay_window = None # 창을 필요할 때 생성하도록 초기화

    def ensure_overlay_visible(self):
        """오버레이 창이 없거나 숨겨져 있으면 새로 만들고 표시합니다."""
        if not self.overlay_window or not self.overlay_window.isVisible():
            self.overlay_window = OverlayWindow(self.config_manager)
            self.overlay_window.show()

    @Slot(str)
    def update_status(self, message: str):
        """Worker로부터 상태 메시지를 받아 오버레이에 표시합니다."""
        if not message and (not self.overlay_window or not self.overlay_window.isVisible()):
             return # 표시할 메시지도 없고 창도 없으면 아무것도 안 함

        self.ensure_overlay_visible()
        self.overlay_window.update_status(message)

    @Slot(str, dict, str)
    def add_translation(self, original: str, results: dict, source: str):
        """Worker로부터 번역 결과를 받아 오버레이에 추가합니다."""
        if not original.strip() or not results:
            return
            
        self.ensure_overlay_visible()
        # 번역 결과가 도착하면, '번역 중' 같은 상태 메시지는 숨김
        self.overlay_window.update_status("")
        self.overlay_window.add_translation(original, results, source)

    def hide_all(self):
        """모든 번역 표시를 중단하고 창을 숨깁니다."""
        if self.overlay_window:
            self.overlay_window.clear_all()
            self.overlay_window.hide()
            # [메모리 관리] 창을 닫아서 리소스를 해제
            self.overlay_window.deleteLater()
            self.overlay_window = None

    def get_overlay_geometry(self) -> QRect | None:
        """
        '자기 인식 OCR'을 위해 현재 오버레이 창의 화면 좌표(QRect)를 반환합니다.
        """
        if self.overlay_window and self.overlay_window.isVisible():
            return self.overlay_window.geometry()
        return None