import sys
import keyboard  # keyboard 라이브러리를 직접 사용
from PySide6.QtWidgets import QSystemTrayIcon, QMenu, QMessageBox, QApplication
from PySide6.QtGui import QIcon, QAction, QScreen
from PySide6.QtCore import Slot, QObject, QTimer, QRect

from config_manager import ConfigManager
from gui.setup_window import SetupWindow
from gui.overlay_window import OverlayWindow
from worker import Worker

class TrayIcon(QObject):
    """
    시스템 트레이 아이콘과 애플리케이션의 메인 로직을 관리하는 총괄 클래스.
    QTimer를 이용한 단축키 폴링 방식을 사용하여 안정성을 높였습니다.
    """
    def __init__(self, config_manager: ConfigManager, icon_path: str, app: QApplication):
        super().__init__()
        self.app = app
        self.config_manager = config_manager

        # QSystemTrayIcon은 이 컨트롤러 클래스의 멤버 변수로 관리합니다.
        self.tray_icon = QSystemTrayIcon(self)
        icon = QIcon(icon_path)
        self.tray_icon.setIcon(icon)
        self.tray_icon.setToolTip("Ariel by Seeth")

        # 멤버 변수 초기화
        self.worker = None
        self.overlay = None
        self.setup_window = None

        # 메뉴 생성 및 연결
        self.create_menu()
        self.tray_icon.show()

        # 단축키 폴링을 위한 QTimer 설정
        self.hotkey_timer = QTimer(self)
        self.hotkey_timer.setInterval(50)  # 0.05초마다 확인
        self.hotkey_timer.timeout.connect(self.check_hotkeys)
        self.hotkey_timer.start()

        # 이전에 눌린 상태를 기억하여 키를 누르고 있을 때 반복 실행 방지
        self.hotkey_states = {
            "start": False,
            "stop": False,
            "setup": False,
            "quit": False # 종료 단축키 상태 추가
        }

        self._update_menu_hotkeys()
        print("트레이 아이콘 준비 완료. (안정화된 폴링 방식 단축키 사용)")

    def create_menu(self):
        """트레이 아이콘의 컨텍스트 메뉴를 생성합니다."""
        self.menu = QMenu()
        self.start_action = self.menu.addAction("번역 시작")
        self.stop_action = self.menu.addAction("번역 중지")
        self.menu.addSeparator()
        self.setup_action = self.menu.addAction("설정...")
        self.menu.addSeparator()
        self.quit_action = self.menu.addAction("종료")

        self.tray_icon.setContextMenu(self.menu)

        self.start_action.triggered.connect(self.start_translation)
        self.stop_action.triggered.connect(self.stop_translation)
        self.setup_action.triggered.connect(self.open_setup_window)
        self.quit_action.triggered.connect(self.quit_application)

        self.stop_action.setEnabled(False)

    def _update_menu_hotkeys(self):
        """메뉴에 표시되는 단축키 텍스트를 업데이트합니다."""
        start_key = self.config_manager.get("hotkey_start_translate", "").replace("+", " + ")
        stop_key = self.config_manager.get("hotkey_stop_translate", "").replace("+", " + ")
        setup_key = self.config_manager.get("hotkey_toggle_setup_window", "").replace("+", " + ")

        self.start_action.setText(f"번역 시작 ({start_key.upper()})")
        self.stop_action.setText(f"번역 중지 ({stop_key.upper()})")
        self.setup_action.setText(f"설정... ({setup_key.upper()})")
    
    def check_hotkeys(self):
        """QTimer에 의해 주기적으로 호출되어 단축키 입력을 확인합니다."""
        try:
            start_key = self.config_manager.get("hotkey_start_translate")
            stop_key = self.config_manager.get("hotkey_stop_translate")
            setup_key = self.config_manager.get("hotkey_toggle_setup_window")
            quit_key = self.config_manager.get("hotkey_quit_app") # 종료 단축키 불러오기

            # 시작 단축키 확인 (단축키가 설정된 경우에만 검사)
            is_start_pressed = keyboard.is_pressed(start_key) if start_key else False
            if is_start_pressed and not self.hotkey_states["start"]:
                self.start_translation()
            self.hotkey_states["start"] = is_start_pressed

            # 중지 단축키 확인
            is_stop_pressed = keyboard.is_pressed(stop_key) if stop_key else False
            if is_stop_pressed and not self.hotkey_states["stop"]:
                self.stop_translation()
            self.hotkey_states["stop"] = is_stop_pressed

            # 설정창 단축키 확인
            is_setup_pressed = keyboard.is_pressed(setup_key) if setup_key else False
            if is_setup_pressed and not self.hotkey_states["setup"]:
                self.open_setup_window()
            self.hotkey_states["setup"] = is_setup_pressed
            
            # 종료 단축키 확인
            is_quit_pressed = keyboard.is_pressed(quit_key) if quit_key else False
            if is_quit_pressed and not self.hotkey_states["quit"]:
                print("종료 단축키 감지, 애플리케이션을 종료합니다.")
                self.quit_application()
            self.hotkey_states["quit"] = is_quit_pressed

        except Exception:
            # keyboard.is_pressed()가 키 조합 분석 중 예외를 발생시킬 수 있음 (예: "ctrl+")
            # 이 경우 조용히 무시하여 프로그램이 중단되지 않도록 함
            pass

    @Slot()
    def start_translation(self):
        if self.worker and self.worker._is_running:
            return

        print("번역 시작 요청...")
        self.start_action.setEnabled(False)
        self.stop_action.setEnabled(True)

        if not self.overlay:
            self.overlay = OverlayWindow(self.config_manager)

        # --- 오버레이 위치/크기 적용 로직 강화 ---
        pos_x = self.config_manager.get("overlay_pos_x")
        pos_y = self.config_manager.get("overlay_pos_y")
        width = self.config_manager.get("overlay_width", 800)
        height = self.config_manager.get("overlay_height", 100)

        # 저장된 위치가 현재 화면 내에 있는지 확인
        is_on_screen = False
        if pos_x is not None and pos_y is not None:
            saved_rect = QRect(pos_x, pos_y, width, height)
            for screen in self.app.screens():
                if screen.geometry().intersects(saved_rect):
                    is_on_screen = True
                    break
        
        if is_on_screen:
            self.overlay.move(pos_x, pos_y)
            self.overlay.resize(width, height)
        else:
            if pos_x is not None or pos_y is not None:
                 print("저장된 위치가 화면 밖에 있어 중앙으로 초기화합니다.")
            self.overlay.resize(width, height)
            self.overlay._center_on_screen()
        # --- 여기까지 강화 ---
            
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
    def open_setup_window(self):
        if self.setup_window and self.setup_window.isVisible():
            self.setup_window.close()
            return
        
        self.setup_window = SetupWindow(self.config_manager)
        self.setup_window.closed.connect(self.on_setup_window_closed)
        self.setup_window.show()
        self.setup_window.activateWindow()

    @Slot(bool, str)
    def on_setup_window_closed(self, is_saved, context):
        self.setup_window = None
        
        if is_saved:
            print("설정이 저장되어, 관련 내용을 리프레시합니다.")
            self._update_menu_hotkeys()  # 메뉴 텍스트만 업데이트, 리스너 재등록 불필요
            if self.overlay and self.overlay.isVisible():
                self.overlay.update_styles()

    @Slot()
    def quit_application(self):
        print("애플리케이션 종료 요청...")
        self.hotkey_timer.stop()  # 종료 전 타이머를 정지
        self.stop_translation()
        self.app.quit()