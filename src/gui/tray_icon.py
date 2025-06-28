# src/gui/tray_icon.py (최종 아키텍처 완성본)
import sys
from PySide6.QtWidgets import QSystemTrayIcon, QMenu, QMessageBox, QApplication
from PySide6.QtGui import QIcon, QAction
from PySide6.QtCore import Slot, QObject, QThread

# hotkey_manager가 없다면 이전 단계의 코드를 참고하여 생성해야 합니다.
try:
    from hotkey_manager import HotkeyManager
except ImportError:
    print("경고: hotkey_manager.py 파일을 찾을 수 없습니다. 단축키 기능이 작동하지 않습니다.")
    HotkeyManager = None

from config_manager import ConfigManager
from gui.setup_window import SetupWindow
from gui.overlay_window import OverlayWindow
from worker import Worker

class TrayIcon(QObject):
    """
    시스템 트레이 아이콘과 애플리케이션의 메인 로직을 관리하는 총괄 클래스.
    모든 스레드와 UI 객체의 생명 주기를 관리합니다.
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
        self.worker = None # Worker는 이제 스레드가 아니므로 thread 변수 불필요
        self.overlay = None
        self.setup_window = None
        self.hotkey_manager = None
        self.hotkey_thread = None

        # 메뉴 생성 및 연결
        self.create_menu()
        self.tray_icon.show()

        # 단축키 관리자 설정
        if HotkeyManager:
            self.setup_hotkey_manager()
        
        self._update_menu_hotkeys()
        print("트레이 아이콘 준비 완료.")

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

    def setup_hotkey_manager(self):
        """HotkeyManager를 별도의 스레드에서 실행하고 시그널을 연결합니다."""
        self.hotkey_thread = QThread()
        self.hotkey_manager = HotkeyManager(self.config_manager)
        self.hotkey_manager.moveToThread(self.hotkey_thread)

        self.hotkey_manager.start_hotkey_pressed.connect(self.start_translation)
        self.hotkey_manager.stop_hotkey_pressed.connect(self.stop_translation)
        self.hotkey_manager.setup_hotkey_pressed.connect(self.open_setup_window)

        self.hotkey_thread.started.connect(self.hotkey_manager.start_listening)
        self.hotkey_thread.start()

    def _update_menu_hotkeys(self):
        """메뉴에 표시되는 단축키 텍스트를 업데이트합니다."""
        start_key = self.config_manager.get("hotkey_start_translate", "").replace("+", " + ")
        stop_key = self.config_manager.get("hotkey_stop_translate", "").replace("+", " + ")
        setup_key = self.config_manager.get("hotkey_toggle_setup_window", "").replace("+", " + ")
        
        self.start_action.setText(f"번역 시작 ({start_key.upper()})")
        self.stop_action.setText(f"번역 중지 ({stop_key.upper()})")
        self.setup_action.setText(f"설정... ({setup_key.upper()})")

    @Slot()
    def start_translation(self):
        # Worker가 이미 생성되어 동작 중인지 확인
        if self.worker and self.worker._is_running:
            return

        print("번역 시작 요청...")
        self.start_action.setEnabled(False)
        self.stop_action.setEnabled(True)

        # 1. 오버레이 창 준비
        if not self.overlay:
            self.overlay = OverlayWindow(self.config_manager)
        self.overlay.show()

        # 2. Worker를 메인 스레드에서 생성 (스레드로 옮기지 않음)
        self.worker = Worker(self.config_manager)

        # 3. 시그널-슬롯 연결
        self.worker.translation_ready.connect(self.overlay.add_translation)
        self.worker.status_update.connect(self.overlay.update_status)
        self.worker.error_occurred.connect(self.on_worker_error)
        
        # 4. Worker의 처리 시작
        self.worker.start_processing()
        self.tray_icon.showMessage("번역 시작", "Ariel 실시간 번역을 시작합니다.", self.tray_icon.icon(), 2000)

    @Slot()
    def stop_translation(self):
        print("번역 중지 요청...")
        
        if self.worker:
            self.worker.stop_processing()
            # Worker 객체는 다음 시작 시 새로 생성되므로, 여기서 참조를 제거
            self.worker = None
        
        if self.overlay:
            self.overlay.hide()
            # 오버레이 창도 다음에 다시 생성되도록 참조 제거
            self.overlay = None
            
        self.start_action.setEnabled(True)
        self.stop_action.setEnabled(False)
        self.tray_icon.showMessage("번역 중지", "Ariel 실시간 번역을 중지합니다.", self.tray_icon.icon(), 2000)

    @Slot(str)
    def on_worker_error(self, message):
        self.tray_icon.showMessage("오류 발생", message, self.tray_icon.icon(), 3000)
        # 오류 발생 시에도 확실하게 중지 로직 실행
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
        # 창이 닫힐 때 참조를 제거하여 토글 기능이 가능하도록 함
        self.setup_window = None
        
        if is_saved:
            print("설정이 저장되어, 관련 내용을 리프레시합니다.")
            if self.hotkey_manager:
                self.hotkey_manager.reregister_hotkeys()
            self._update_menu_hotkeys()
            if self.overlay and self.overlay.isVisible():
                self.overlay.update_styles()

    @Slot()
    def quit_application(self):
        print("애플리케이션 종료 요청...")
        self.stop_translation()
        
        if self.hotkey_manager:
            self.hotkey_manager.stop_listening()
        if self.hotkey_thread:
            self.hotkey_thread.quit()
            self.hotkey_thread.wait(3000)
        
        self.app.quit()