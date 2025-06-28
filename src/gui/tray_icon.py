import sys
from multiprocessing import Process, Queue
from PySide6.QtWidgets import QSystemTrayIcon, QMenu, QMessageBox, QApplication
from PySide6.QtGui import QIcon, QAction
from PySide6.QtCore import Slot, QObject, QTimer

from config_manager import ConfigManager
from worker import Worker
from hotkey_manager import hotkey_listener 
from gui.overlay_window import OverlayWindow
# 이제 최상단에서 직접 import 해도 안전합니다.
from gui.setup_window import SetupWindow

class TrayIcon(QObject):
    def __init__(self, config_manager: ConfigManager, icon_path: str, app: QApplication):
        super().__init__()
        self.app = app
        self.config_manager = config_manager
        self.tray_icon = QSystemTrayIcon(self)
        icon = QIcon(icon_path)
        self.tray_icon.setIcon(icon)
        self.tray_icon.setToolTip("Ariel by Seeth")
        self.worker = None
        self.overlay = None
        self.setup_window = None
        self.hotkey_process = None
        self.hotkey_queue = Queue()
        self.hotkey_checker = QTimer(self)
        self.create_menu()
        self.tray_icon.show()
        self.setup_hotkey_process()
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

    def setup_hotkey_process(self):
        hotkeys_config = {
            "hotkey_start_translate": self.config_manager.get("hotkey_start_translate"),
            "hotkey_stop_translate": self.config_manager.get("hotkey_stop_translate"),
            "hotkey_toggle_setup_window": self.config_manager.get("hotkey_toggle_setup_window"),
            "hotkey_toggle_pause": self.config_manager.get("hotkey_toggle_pause")
        }
        self.hotkey_process = Process(target=hotkey_listener, args=(self.hotkey_queue, hotkeys_config), daemon=True)
        self.hotkey_process.start()
        self.hotkey_checker.timeout.connect(self.check_hotkey_queue)
        self.hotkey_checker.start(100)

    def check_hotkey_queue(self):
        if not self.hotkey_queue.empty():
            event = self.hotkey_queue.get()
            if event == "start": self.start_translation()
            elif event == "stop": self.stop_translation()
            elif event == "setup": self.open_setup_window()

    def _update_menu_hotkeys(self):
        start_key = self.config_manager.get("hotkey_start_translate", "").replace("+", " + ")
        stop_key = self.config_manager.get("hotkey_stop_translate", "").replace("+", " + ")
        setup_key = self.config_manager.get("hotkey_toggle_setup_window", "").replace("+", " + ")
        self.start_action.setText(f"번역 시작 ({start_key.upper()})")
        self.stop_action.setText(f"번역 중지 ({stop_key.upper()})")
        self.setup_action.setText(f"설정... ({setup_key.upper()})")

    @Slot()
    def open_setup_window(self):
        if self.setup_window and self.setup_window.isVisible():
            self.setup_window.activateWindow()
            return
        self.setup_window = SetupWindow(self.config_manager)
        self.setup_window.show()
        self.setup_window.activateWindow()
        
    # (start_translation, stop_translation, on_worker_error, quit_application 등 나머지 메서드는 그대로 둡니다)
    @Slot()
    def start_translation(self):
        if self.worker and self.worker._is_running:
            return

        print("번역 시작 요청...")
        self.start_action.setEnabled(False)
        self.stop_action.setEnabled(True)

        if not self.overlay:
            self.overlay = OverlayWindow(self.config_manager)

        saved_geometry = self.config_manager.get("overlay_geometry")
        if saved_geometry and len(saved_geometry) == 4:
            self.overlay.setGeometry(*saved_geometry)

        self.overlay.show()

        self.worker = Worker(self.config_manager)

        self.worker.translation_ready.connect(self.overlay.add_translation)
        self.worker.status_update.connect(self.overlay.update_status)
        self.worker.error_occurred.connect(self.on_worker_error)
        
        self.worker.start_processing()
        self.tray_icon.showMessage("번역 시작", "Ariel 실시간 번역을 시작합니다.", self.tray_icon.icon(), 2000)

    @Slot()
    def stop_translation(self):
        print("번역 중지 요청...")
        
        if self.worker:
            self.worker.stop_processing()
            self.worker = None
        
        if self.overlay:
            self.overlay.hide()
            self.overlay = None
            
        self.start_action.setEnabled(True)
        self.stop_action.setEnabled(False)
        self.tray_icon.showMessage("번역 중지", "Ariel 실시간 번역을 중지합니다.", self.tray_icon.icon(), 2000)

    @Slot(str)
    def on_worker_error(self, message):
        self.tray_icon.showMessage("오류 발생", message, self.tray_icon.icon(), 3000)
        self.stop_translation()

    @Slot()
    def quit_application(self):
        print("애플리케이션 종료 요청...")
        if self.hotkey_process and self.hotkey_process.is_alive():
            self.hotkey_process.terminate()
            self.hotkey_process.join()
        self.stop_translation()
        self.app.quit()