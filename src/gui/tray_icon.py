# src/gui/tray_icon.py
import sys
import keyboard
from PySide6.QtWidgets import QSystemTrayIcon, QMenu, QMessageBox, QApplication
from PySide6.QtGui import QIcon, QAction
from PySide6.QtCore import Slot

from config_manager import ConfigManager
from gui.setup_window import SetupWindow
from gui.overlay_window import OverlayWindow
from worker import Worker

class TrayIcon(QSystemTrayIcon):
    def __init__(self, config_manager: ConfigManager, icon_path: str, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.worker = None
        self.overlay = None
        self.setup_window = None
        
        icon = QIcon(icon_path)
        if icon.isNull():
            print(f"경고: 아이콘 파일을 찾을 수 없습니다: {icon_path}")
        self.setIcon(icon)
        self.setToolTip("Ariel by Seeth")

        self.menu = QMenu()
        self.start_action = self.menu.addAction("번역 시작 (Ctrl+F9)")
        self.stop_action = self.menu.addAction("번역 중지 (Ctrl+F10)")
        self.menu.addSeparator()
        self.setup_action = self.menu.addAction("설정...")
        self.menu.addSeparator()
        self.quit_action = self.menu.addAction("종료")
        
        self.setContextMenu(self.menu)

        self.start_action.triggered.connect(self.start_translation)
        self.stop_action.triggered.connect(self.stop_translation)
        self.setup_action.triggered.connect(self.open_setup_window)
        self.quit_action.triggered.connect(self.quit_application)
        
        self.stop_action.setEnabled(False)
        self._register_hotkeys()
        
        print("트레이 아이콘 준비 완료. 단축키 리스닝 시작...")

    def _register_hotkeys(self):
        start_key = self.config_manager.get("hotkey_start_translate")
        stop_key = self.config_manager.get("hotkey_stop_translate")
        try:
            keyboard.add_hotkey(start_key, self.start_translation, suppress=True)
            keyboard.add_hotkey(stop_key, self.stop_translation, suppress=True)
        except Exception as e:
            self.show_error_message("단축키 등록 실패", f"단축키를 등록하는 데 실패했습니다: {e}\n프로그램을 관리자 권한으로 실행해보세요.")

    @Slot()
    def start_translation(self):
        if self.worker and self.worker.isRunning(): return
        print("번역 시작 요청...")
        
        if not self.overlay:
            self.overlay = OverlayWindow(self.config_manager)
        else:
            self.overlay.update_styles()
        self.overlay.show()
        
        try:
            self.worker = Worker(self.config_manager)
            self.worker.translation_ready.connect(self.overlay.update_translation)
            self.worker.worker_error.connect(self.on_worker_error)
            self.worker.start()
        except Exception as e:
            self.show_error_message("시작 오류", f"번역 작업을 시작하는 중 오류 발생: {e}")
            if self.overlay: self.overlay.hide()
            return
            
        self.start_action.setEnabled(False)
        self.stop_action.setEnabled(True)
        self.showMessage("번역 시작", "Ariel 실시간 번역을 시작합니다.", self.icon(), 2000)

    @Slot()
    def stop_translation(self):
        if not self.worker or not self.worker.isRunning(): return
        print("번역 중지 요청...")
        self.worker.stop()
        self.worker.wait(5000)
        self.worker = None

        if self.overlay:
            self.overlay.clear_all_labels()
            self.overlay.hide()
            
        self.start_action.setEnabled(True)
        self.stop_action.setEnabled(False)
        self.showMessage("번역 중지", "Ariel 실시간 번역을 중지합니다.", self.icon(), 2000)

    @Slot(str)
    def on_worker_error(self, message):
        self.show_error_message("백엔드 오류", message)
        self.stop_translation()

    @Slot()
    def open_setup_window(self):
        if not self.setup_window or not self.setup_window.isVisible():
            self.setup_window = SetupWindow(self.config_manager)
            self.setup_window.show()

    def show_error_message(self, title, text):
        msg_box = QMessageBox(QMessageBox.Icon.Critical, title, text)
        msg_box.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint)
        msg_box.exec()

    @Slot()
    def quit_application(self):
        print("애플리케이션 종료 요청...")
        self.stop_translation()
        keyboard.unhook_all()
        QApplication.instance().quit()