# src/gui/tray_icon.py (최종 솔루션 버전)
import sys
import keyboard
import logging
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
        # 단축키 중복 실행 방지를 위한 상태 딕셔너리
        self.hotkey_states = {"start": False, "ocr": False, "setup": False, "quit": False}
        logging.info("트레이 아이콘 준비 완료.")

    def check_api_keys(self):
        """API 키가 설정되었는지 확인하고, 없으면 경고 후 설정 창을 엽니다."""
        if not self.config_manager.get("google_credentials_path") or not self.config_manager.get("deepl_api_key"):
            QMessageBox.warning(None, "설정 필요", "API 키가 설정되지 않았습니다.\n[설정] > [연동 서비스]에서 API 키를 먼저 설정해주세요.")
            self.open_setup_window()
            return False
        return True

    def create_menu(self):
        """트레이 아이콘의 컨텍스트 메뉴를 생성/갱신합니다."""
        self.menu.clear() 
        self.profile_menu = self.menu.addMenu("프로필")
        self.update_profile_menu()
        self.menu.addSeparator()
        # [개선] '시작/중지' 메뉴를 하나로 통합 (토글 방식)
        self.start_action = self.menu.addAction("음성 번역 시작/중지")
        self.ocr_action = self.menu.addAction("화면 번역 (영역 지정)")
        self.menu.addSeparator()
        self.setup_action = self.menu.addAction("설정...")
        self.menu.addSeparator()
        self.quit_action = self.menu.addAction("종료")
        
        # [개선] 토글 함수로 연결
        self.start_action.triggered.connect(self.toggle_translation)
        self.ocr_action.triggered.connect(self.start_ocr_capture)
        self.setup_action.triggered.connect(self.open_setup_window)
        self.quit_action.triggered.connect(self.quit_application)
        self._update_menu_state()

    def update_profile_menu(self):
        """프로필 목록 메뉴를 업데이트합니다."""
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
        """프로필을 전환합니다."""
        # 프로필 전환 시 실행 중이던 번역 중지
        if self.worker and self.worker._is_running:
            self.stop_translation()
        
        if self.config_manager.switch_profile(profile_name):
            self.worker.config_manager = self.config_manager # Worker의 설정도 갱신
        
        self.create_menu() # 메뉴 텍스트(단축키 등) 갱신
        self.tray_icon.showMessage("프로필 전환", f"'{profile_name}' 프로필이 활성화되었습니다.", self.tray_icon.icon(), 2000)

    def _update_menu_state(self):
        """번역 상태에 따라 메뉴 텍스트와 상태를 업데이트합니다."""
        is_running = self.worker and self.worker._is_running
        
        start_key = self.config_manager.get('hotkey_start_translate', '').upper()
        self.start_action.setText(f"음성 번역 {'중지' if is_running else '시작'} ({start_key})")
        
        ocr_key = self.config_manager.get("hotkey_ocr", "").replace("+", " + ").upper()
        setup_key = self.config_manager.get("hotkey_toggle_setup_window", "").replace("+", " + ").upper()
        
        self.ocr_action.setText(f"화면 번역 ({ocr_key})")
        self.setup_action.setText(f"설정... ({setup_key})")

    def check_hotkeys(self):
        """[개선] 설정된 단축키를 확인하고 해당 동작을 실행합니다 (간결화된 구조)."""
        try:
            hotkey_map = {
                "start": "hotkey_start_translate",
                "ocr": "hotkey_ocr",
                "setup": "hotkey_toggle_setup_window",
                "quit": "hotkey_quit_app"
            }
            actions = {
                "start": self.toggle_translation,
                "ocr": self.start_ocr_capture,
                "setup": self.open_setup_window,
                "quit": self.quit_application
            }
            
            for name, config_key in hotkey_map.items():
                key_str = self.config_manager.get(config_key)
                if key_str:
                    is_pressed = keyboard.is_pressed(key_str)
                    if is_pressed and not self.hotkey_states[name]:
                        actions[name]()
                    self.hotkey_states[name] = is_pressed
        except Exception:
            # 키보드 라이브러리에서 발생하는 예외(예: 권한 문제)를 무시
            pass
        
    @Slot()
    def toggle_translation(self):
        """음성 번역을 시작하거나 중지합니다."""
        if self.worker and self.worker._is_running:
            self.stop_translation()
        else:
            self.start_translation()

    @Slot()
    def start_ocr_capture(self):
        """화면 번역(OCR) 캡처를 시작합니다."""
        if not self.check_api_keys(): return # API 키 확인
        
        tesseract_path = self.config_manager.get("tesseract_path")
        self.ocr_capturer = OcrCapturer(tesseract_path)
        self.ocr_capturer.text_captured.connect(self.worker.on_ocr_text_captured)
        self.ocr_capturer.show()

    @Slot()
    def start_translation(self):
        """음성 번역을 시작하고 오버레이 창을 표시합니다."""
        if not self.check_api_keys(): return # API 키 확인
        
        if not self.overlay: 
            self.overlay = OverlayWindow(self.config_manager)
            self.worker.translation_ready.connect(self.overlay.add_translation)
            self.worker.status_update.connect(self.overlay.update_status)
            self.worker.error_occurred.connect(self.on_worker_error)

        # 오버레이 창 위치/크기 복원
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
        self.tray_icon.showMessage("음성 번역 시작", "Ariel 실시간 번역을 시작합니다.", self.tray_icon.icon(), 2000)

    @Slot()
    def stop_translation(self):
        """음성 번역을 중지하고 오버레이 창을 숨깁니다."""
        if not (self.worker and self.worker._is_running): return
        self.worker.stop_processing()
        if self.overlay: self.overlay.hide()
        self._update_menu_state()
        self.tray_icon.showMessage("음성 번역 중지", "Ariel 실시간 번역을 중지합니다.", self.tray_icon.icon(), 2000)

    @Slot(str)
    def on_worker_error(self, message):
        QMessageBox.critical(None, "치명적 오류", message)
        self.stop_translation()

    @Slot()
    def open_setup_window(self):
        """[개선] 설정 창을 열거나, 이미 열려있으면 닫습니다 (토글 기능)."""
        from gui.setup_window import SetupWindow # 순환 참조 방지를 위해 로컬 임포트
        
        if self.setup_window and self.setup_window.isVisible():
            self.setup_window.close()
            self.setup_window = None # 참조 제거
            return
        
        self.setup_window = SetupWindow(self.config_manager)
        self.setup_window.closed.connect(self.on_setup_window_closed)
        self.setup_window.show()
        self.setup_window.activateWindow()

    @Slot(bool, str)
    def on_setup_window_closed(self, is_saved, context):
        self.setup_window = None # 창이 닫혔으므로 참조 제거
        if is_saved:
            self.create_menu() # 단축키 등 메뉴 정보 갱신
            if self.overlay and self.overlay.isVisible():
                self.overlay.update_styles()

    @Slot()
    def quit_application(self):
        """애플리케이션을 안전하게 종료합니다."""
        logging.info("애플리케이션 종료 요청...")
        self.hotkey_timer.stop()
        if self.worker:
            self.worker.stop_processing()
        self.app.quit()