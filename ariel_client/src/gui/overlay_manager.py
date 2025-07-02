# ariel_client/src/gui/overlay_manager.py (이 코드로 전체 교체)
import logging
# [수정] QRect를 사용하기 위해 import 구문에 추가합니다.
from PySide6.QtCore import QObject, QTimer, Slot, QRect
from collections import deque
from .overlay_window import OverlayWindow
from ..config_manager import ConfigManager

class OverlayManager(QObject):
    """
    모든 번역 결과를 단일 큐로 관리하고,
    하나의 오버레이 창에 순차적으로 표시하는 중앙 허브.
    """
    def __init__(self, config_manager: ConfigManager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.translation_queue = deque()
        self.overlay_window = None
        self.is_showing = False

        self.timer = QTimer(self)
        self.timer.setInterval(300) # 0.3초마다 큐 확인
        self.timer.timeout.connect(self.process_queue)
        self.timer.start()

    @Slot(str)
    def update_status(self, message: str):
        if not self.overlay_window or not self.overlay_window.isVisible():
            # 번역 기능이 시작될 때 오버레이 창이 없다면, 새로 만들어서 상태를 표시
            if message:
                self.overlay_window = OverlayWindow(self.config_manager)
                self.overlay_window.show()
        
        if self.overlay_window:
            self.overlay_window.update_status(message)

    @Slot(str, dict, str)
    def add_translation(self, original: str, results: dict, source: str):
        # ...
        if not self.overlay_window or not self.overlay_window.isVisible():
            self.overlay_window = OverlayWindow(self.config_manager)
            self.overlay_window.show()
        # 번역을 추가하기 전에 상태 메시지는 지움
        self.update_status("")
        self.overlay_window.add_translation(original, results, source)

    def hide_all(self):
        if self.overlay_window:
            self.overlay_window.clear_all()
            self.overlay_window.hide()

    @Slot(str, dict, str)
    def add_to_queue(self, original: str, results: dict, source: str):
        """외부(Worker)에서 번역 결과를 받아 큐에 추가합니다."""
        if not results or not original.strip(): return
        logging.info(f"번역 대기열에 추가: [{source}] {original}")
        self.translation_queue.append((original, results, source))

    def process_queue(self):
        """큐에 항목이 있고, 현재 오버레이가 표시 중이 아닐 때 하나를 꺼내 표시합니다."""
        if self.translation_queue and not self.is_showing:
            original, results, source = self.translation_queue.popleft()
            self.show_overlay(original, results, source)

    def show_overlay(self, original, results, source):
        if not self.overlay_window:
            self.overlay_window = OverlayWindow(self.config_manager)
        
        # [수정] 이전에 제안했던 로직 대신, OverlayManager가 직접 제어하도록 수정
        # self.overlay_window.add_translation(original, results, source)
        
        if not self.overlay_window.isVisible():
            self.overlay_window.show()
        
        self.is_showing = True
        display_duration = min(max(5000, len(original) * 150), 15000)
        QTimer.singleShot(display_duration, self.hide_if_not_hovered)

    def hide_if_not_hovered(self):
        if self.overlay_window and not self.overlay_window.underMouse():
            self.overlay_window.hide()
            self.is_showing = False
        else:
            QTimer.singleShot(1000, self.hide_if_not_hovered)
            
    def hide_all(self):
        if self.overlay_window:
            self.overlay_window.hide()
        self.is_showing = False
        self.translation_queue.clear()
        
    def get_overlay_geometry(self) -> QRect | None:
        """
        현재 표시 중인 오버레이 창의 화면 좌표(QRect)를 반환합니다.
        """
        if self.overlay_window and self.overlay_window.isVisible():
            return self.overlay_window.geometry()
        return None