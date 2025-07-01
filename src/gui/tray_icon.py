# src/gui/tray_icon.py (이 코드로 전체를 교체해주세요)
import sys
import keyboard
import logging
import traceback
from PySide6.QtWidgets import QSystemTrayIcon, QMenu, QMessageBox, QApplication
from PySide6.QtGui import QIcon, QAction
from PySide6.QtCore import Slot, QObject, QTimer, QRect
from utils import resource_path
from config_manager import ConfigManager
from gui.overlay_window import OverlayWindow
from gui.ocr_capturer import OcrCapturer
from worker import Worker

class TrayIcon(QObject):
    def __init__(self, config_manager: ConfigManager, icon_path: str, app: QApplication):
        super().__init__()
        self.app = app
        self.config_manager = config_manager
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(QIcon(icon_path))
        self.tray_icon.setToolTip("Ariel by Seeth")

        self.worker = Worker(self.config_manager, self)
        self.overlay, self.setup_window, self.ocr_capturer = None, None, None
        
        self.menu = QMenu()
        self.create_menu()
        self.tray_icon.setContextMenu(self.menu)
        self.tray_icon.show()

        self.hotkey_timer = QTimer(self)
        self.hotkey_timer.setInterval(50)
        self.hotkey_timer.timeout.connect(self.check_hotkeys)
        self.hotkey_timer.start()
        self.hotkey_states = {"start": False, "ocr": False, "setup": False, "quit": False}
        logging.info("트레이 아이콘 준비 완료.")

    # [핵심] 앱 시작 직후 호출될 초기 확인 함수
    def run_initial_check(self):
        """API 키 존재 여부를 확인하고, 없으면 설정 창을 엽니다."""
        if not self.config_manager.get("google_credentials_path") or not self.config_manager.get("deepl_api_key"):
            QMessageBox.information(None, "Ariel에 오신 것을 환영합니다!",
                                    "실시간 번역기 'Ariel'을 사용하기 전에, \n"
                                    "필수적인 API 키 설정을 먼저 완료해야 합니다.")
            # '연동 서비스' 페이지(인덱스 1)가 보이도록 설정 창을 엽니다.
            self.open_setup_window(initial_page_index=1)
        
    def show_tray_message(self, title, message, duration=2000):
        if self.config_manager.get("show_tray_notifications", True):
            self.tray_icon.showMessage(title, message, self.tray_icon.icon(), duration)

    # (check_api_keys 함수는 이제 사용되지 않으므로 삭제하거나 그대로 두어도 무방합니다)

    # ... create_menu, update_profile_menu 등 다른 함수들은 이전과 동일 ...
    def create_menu(self):
        self.menu.clear() 
        self.profile_menu = self.menu.addMenu("프로필")
        self.update_profile_menu()
        self.menu.addSeparator()
        self.start_action = self.menu.addAction("음성 번역 시작/중지")
        self.ocr_action = self.menu.addAction("화면 번역 (영역 지정)")
        self.menu.addSeparator()
        self.setup_action = self.menu.addAction("설정...")
        self.menu.addSeparator()
        self.quit_action = self.menu.addAction("종료")
        
        self.start_action.triggered.connect(self.toggle_translation)
        self.ocr_action.triggered.connect(self.start_ocr_capture)
        self.setup_action.triggered.connect(self.open_setup_window)
        self.quit_action.triggered.connect(self.quit_application)
        self._update_menu_state()

    def update_profile_menu(self):
        self.profile_menu.clear()
        profile_names = self.config_manager.get_profile_names()
        active_profile = self.config_manager.get_active_profile_name()
        for name in profile_names:
            action = QAction(name, self)
            action.setCheckable(True)
            if name == active_profile:
                action.setChecked(True)
            action.triggered.connect(lambda checked, n=name: self.switch_profile(n))
            self.profile_menu.addAction(action)

    def switch_profile(self, profile_name):
        if self.worker and self.worker._is_running:
            self.stop_translation(show_message=False)
        
        if self.config_manager.switch_profile(profile_name):
            self.worker.config_manager = self.config_manager
        
        self.create_menu()
        self.show_tray_message("프로필 전환", f"'{profile_name}' 프로필이 활성화되었습니다.")

    def _update_menu_state(self):
        is_running = self.worker and self.worker._is_running
        start_key = self.config_manager.get('hotkey_start_translate', '').upper()
        self.start_action.setText(f"음성 번역 {'중지' if is_running else '시작'} ({start_key})")
        ocr_key = self.config_manager.get("hotkey_ocr", "").replace("+", " + ").upper()
        setup_key = self.config_manager.get("hotkey_toggle_setup_window", "").replace("+", " + ").upper()
        self.ocr_action.setText(f"화면 번역 ({ocr_key})")
        self.setup_action.setText(f"설정... ({setup_key})")

    def check_hotkeys(self):
        try:
            hotkey_map = { "start": "hotkey_start_translate", "ocr": "hotkey_ocr",
                           "setup": "hotkey_toggle_setup_window", "quit": "hotkey_quit_app" }
            actions = { "start": self.toggle_translation, "ocr": self.start_ocr_capture,
                        "setup": self.open_setup_window, "quit": self.quit_application }
            
            for name, config_key in hotkey_map.items():
                key_str = self.config_manager.get(config_key)
                if key_str:
                    is_pressed = keyboard.is_pressed(key_str)
                    if is_pressed and not self.hotkey_states[name]:
                        actions[name]()
                    self.hotkey_states[name] = is_pressed
        except Exception:
            pass
        
    @Slot()
    def toggle_translation(self):
        # 번역 시작 전에는 API 키 확인
        if not (self.worker and self.worker._is_running):
            if not self.run_initial_check(): # API 키가 없으면 시작 안함
                return
        
        if self.worker and self.worker._is_running:
            self.stop_translation()
        else:
            self.start_translation()

    @Slot()
    def start_ocr_capture(self):
        if not self.run_initial_check(): return
        
        tesseract_path = self.config_manager.get("tesseract_path")
        self.ocr_capturer = OcrCapturer(tesseract_path)
        self.ocr_capturer.text_captured.connect(self.worker.on_ocr_text_captured)
        self.ocr_capturer.show()

    @Slot()
    def start_translation(self):
        if not self.overlay: 
            self.overlay = OverlayWindow(self.config_manager)
            self.worker.translation_ready.connect(self.overlay.add_translation)
            self.worker.status_update.connect(self.overlay.update_status)
            self.worker.error_occurred.connect(self.on_worker_error)

        pos_x, pos_y = self.config_manager.get("overlay_pos_x"), self.config_manager.get("overlay_pos_y")
        width, height = self.config_manager.get("overlay_width", 800), self.config_manager.get("overlay_height", 100)
        self.overlay.resize(width, height)

        is_on_screen = False
        if pos_x is not None and pos_y is not None:
            saved_rect = QRect(pos_x, pos_y, width, height)
            if any(s.geometry().intersects(saved_rect) for s in self.app.screens()):
                is_on_screen = True
        
        if is_on_screen:
            self.overlay.move(pos_x, pos_y)
        else:
            self.overlay.move_to_center_of_primary_screen()
            
        self.overlay.show()
        self.worker.start_processing()
        self._update_menu_state()
        self.show_tray_message("음성 번역 시작", "Ariel 실시간 번역을 시작합니다.")

    @Slot()
    def stop_translation(self, show_message=True):
        if not (self.worker and self.worker._is_running): return
        self.worker.stop_processing()
        if self.overlay: self.overlay.hide()
        self._update_menu_state()
        if show_message:
            self.show_tray_message("음성 번역 중지", "Ariel 실시간 번역을 중지합니다.")

    @Slot(str)
    def on_worker_error(self, message):
        QMessageBox.critical(None, "치명적 오류", message)
        self.stop_translation()

    # [핵심 수정] 함수가 특정 페이지로 열리도록 인자를 받게 함
    @Slot()
    def open_setup_window(self, initial_page_index=0):
        """설정 창을 열거나, 이미 열려있으면 닫습니다 (오류 처리 및 페이지 지정 기능)."""
        try:
            # 순환 참조 방지를 위해 로컬 임포트
            from gui.setup_window import SetupWindow
            
            if self.setup_window and self.setup_window.isVisible():
                self.setup_window.activateWindow() # 이미 열려있으면 맨 앞으로 가져옴
                return
            
            # 생성자에 초기 페이지 인덱스를 전달
            self.setup_window = SetupWindow(self.config_manager, initial_page_index=initial_page_index)
            self.setup_window.closed.connect(self.on_setup_window_closed)
            self.setup_window.show()
            self.setup_window.activateWindow()

        except Exception as e:
            error_message = f"설정 창을 여는 중 심각한 오류가 발생했습니다:\n\n{str(e)}"
            detailed_error = traceback.format_exc()
            logging.critical(f"{error_message}\n{detailed_error}")
            QMessageBox.critical(None, "치명적 오류", f"{error_message}\n\n'ariel_app.log' 파일을 확인해주세요.")
            self.setup_window = None

    @Slot(bool, str)
    def on_setup_window_closed(self, is_saved, context):
        self.setup_window = None
        if is_saved:
            self.create_menu()
            if self.overlay and self.overlay.isVisible():
                self.overlay.update_styles()

    @Slot()
    def quit_application(self):
        logging.info("애플리케이션 종료 요청...")
        self.hotkey_timer.stop()
        if self.worker: self.worker.stop_processing()
        self.app.quit()