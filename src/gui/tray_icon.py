# src/gui/tray_icon.py

import sys
import os
from PySide6.QtWidgets import QSystemTrayIcon, QMenu, QMessageBox, QApplication
from PySide6.QtGui import QIcon, QAction
from PySide6.QtCore import Slot, QObject, Qt

from config_manager import ConfigManager
from worker import Worker
from hotkey_manager import HotkeyManager # 단축키 관리자 다시 사용
from gui.overlay_window import OverlayWindow
from gui.setup_window import SetupWindow

class TrayIcon(QObject):
    def __init__(self, config_manager: ConfigManager, icon_path: str, app: QApplication):
        super().__init__()
        self.app = app
        self.config_manager = config_manager
        self.tray_icon = QSystemTrayIcon(self)
        self.worker = None
        self.overlay = None
        self.setup_window = None
        self.hotkey_manager = None

        icon = QIcon(icon_path)
        self.tray_icon.setIcon(icon)
        self.tray_icon.setToolTip("Ariel by Seeth")

        self.create_menu()
        self.tray_icon.show()
        
        self.setup_hotkey_manager()
        self._update_menu_hotkeys()
        
    def create_menu(self):
        self.menu = QMenu()
        self.start_action = self.menu.addAction("번역 시작")
        self.stop_action = self.menu.addAction("번역 중지")
        self.setup_action = self.menu.addAction("설정...")
        self.menu.addSeparator()
        self.quit_action = self.menu.addAction("종료")
        self.tray_icon.setContextMenu(self.menu)
        
        self.start_action.triggered.connect(self.start_translation)
        self.stop_action.triggered.connect(self.stop_translation)
        self.setup_action.triggered.connect(self.open_setup_window)
        self.quit_action.triggered.connect(self.quit_application)
        self.stop_action.setEnabled(False)

    def setup_hotkey_manager(self):
        hotkeys_config = {
            "hotkey_start_translate": self.config_manager.get("hotkey_start_translate"),
            "hotkey_stop_translate": self.config_manager.get("hotkey_stop_translate"),
            "hotkey_toggle_setup_window": self.config_manager.get("hotkey_toggle_setup_window"),
        }
        self.hotkey_manager = HotkeyManager(hotkeys_config, self)

        # 안정성을 위해 QueuedConnection은 유지하는 것이 좋습니다.
        self.hotkey_manager.start_pressed.connect(self.start_translation, Qt.QueuedConnection)
        self.hotkey_manager.stop_pressed.connect(self.stop_translation, Qt.QueuedConnection)
        self.hotkey_manager.setup_pressed.connect(self.open_setup_window, Qt.QueuedConnection)

        self.hotkey_manager.start()
        
    @Slot()
    def open_setup_window(self):
        # 이제 이 코드는 어떤 상황에서도 안전하게 동작합니다.
        if self.setup_window and self.setup_window.isVisible():
            self.setup_window.activateWindow()
            return
        
        self.setup_window = SetupWindow(self.config_manager)
        self.setup_window.show()
        self.setup_window.activateWindow()

    @Slot()
    def quit_application(self):
        if self.hotkey_manager:
            self.hotkey_manager.stop()
        self.stop_translation()
        self.app.quit()

    # 이하 나머지 메서드는 변경할 필요 없습니다.
    def _update_menu_hotkeys(self):
        start_key = self.config_manager.get("hotkey_start_translate", "").replace("+", " + ")
        stop_key = self.config_manager.get("hotkey_stop_translate", "").replace("+", " + ")
        setup_key = self.config_manager.get("hotkey_toggle_setup_window", "").replace("+", " + ")
        self.start_action.setText(f"번역 시작 ({start_key.upper()})"); self.stop_action.setText(f"번역 중지 ({stop_key.upper()})"); self.setup_action.setText(f"설정... ({setup_key.upper()})")
        
    @Slot()
    def start_translation(self):
        if self.worker and self.worker._is_running: return; self.start_action.setEnabled(False); self.stop_action.setEnabled(True)
        if not self.overlay: self.overlay = OverlayWindow(self.config_manager)
        saved_geometry = self.config_manager.get("overlay_geometry");
        if saved_geometry: self.overlay.setGeometry(*saved_geometry)
        self.overlay.show()
        self.worker = Worker(self.config_manager)
        self.worker.translation_ready.connect(self.overlay.add_translation); self.worker.status_update.connect(self.overlay.update_status); self.worker.error_occurred.connect(self.on_worker_error)
        self.worker.start_processing()
        self.tray_icon.showMessage("번역 시작", "Ariel 실시간 번역을 시작합니다.", self.tray_icon.icon(), 2000)

    @Slot()
    def stop_translation(self):
        if self.worker: self.worker.stop_processing(); self.worker = None
        if self.overlay: self.overlay.hide(); self.overlay = None
        self.start_action.setEnabled(True); self.stop_action.setEnabled(False)
        self.tray_icon.showMessage("번역 중지", "Ariel 실시간 번역을 중지합니다.", self.tray_icon.icon(), 2000)

    @Slot(str)
    def on_worker_error(self, message):
        self.tray_icon.showMessage("오류 발생", message, self.tray_icon.icon(), 3000)
        self.stop_translation()