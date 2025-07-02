# ariel_client/src/gui/tray_icon.py (이 코드로 전체 교체)
import sys
import logging
from PySide6.QtWidgets import QSystemTrayIcon, QMenu, QMessageBox, QApplication
from PySide6.QtGui import QIcon, QAction
from PySide6.QtCore import Slot, QObject, QRect, QThread

from ..utils import resource_path
from ..config_manager import ConfigManager
from .setup_window import SetupWindow
from .overlay_manager import OverlayManager # OverlayWindow 대신 Manager를 임포트
from .ocr_capturer import OcrCapturer
from ..core.screen_monitor import ScreenMonitor
from ..core.translation_worker import TranslationWorker
from ..core.hotkey_manager import HotkeyManager
from ..core.audio_processor import AudioProcessor

class TrayIcon(QObject):
    def __init__(self, config_manager: ConfigManager, icon_path: str, app: QApplication):
        super().__init__()
        self.app = app
        self.config_manager = config_manager
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(QIcon(icon_path))
        self.tray_icon.setToolTip("Ariel by Seeth")

        # --- 핵심 로직 인스턴스 ---
        self.worker = TranslationWorker(self.config_manager, self)
        self.hotkey_manager = HotkeyManager(self.config_manager, self)
        # [수정] OverlayManager 인스턴스 생성
        self.overlay_manager = OverlayManager(self.config_manager, self)
        self.worker.status_updated.connect(self.overlay_manager.update_status)


        # --- UI 인스턴스 ---
        self.setup_window, self.ocr_capturer = None, None

        # --- 스레드 관련 변수 ---
        self.ocr_monitor_thread, self.screen_monitor = None, None
        self.stt_processor_thread, self.audio_processor = None, None

        self.menu = QMenu()
        self.create_menu()
        self.tray_icon.setContextMenu(self.menu)
        self.tray_icon.show()

        # --- 시그널과 슬롯 연결 ---
        self.hotkey_manager.hotkey_pressed.connect(self.on_hotkey_pressed)
        # [수정] Worker의 신호를 OverlayManager의 큐 추가 슬롯으로 연결
        self.worker.translation_ready.connect(self.overlay_manager.add_to_queue)
        self.worker.error_occurred.connect(self.on_worker_error)
        logging.info("트레이 아이콘 준비 완료.")

    def create_menu(self):
        """트레이 메뉴를 생성하고 업데이트합니다."""
        self.menu.clear()
        self.voice_translation_action = self.menu.addAction("음성 번역 시작")
        self.ocr_translation_action = self.menu.addAction("화면 번역 (영역 지정)")
        self.menu.addSeparator()
        self.setup_action = self.menu.addAction("설정...")
        self.quit_action = self.menu.addAction("종료")

        self.voice_translation_action.triggered.connect(self.toggle_voice_translation)
        self.ocr_translation_action.triggered.connect(self.toggle_ocr_translation)
        self.setup_action.triggered.connect(self.open_setup_window)
        self.quit_action.triggered.connect(self.quit_application)

    @Slot(str)
    def on_hotkey_pressed(self, action_name):
        """단축키 매니저로부터 받은 신호를 처리합니다."""
        if action_name == "start_ocr":
            self.toggle_ocr_translation()
        elif action_name == "toggle_translation":
            self.toggle_voice_translation()
        elif action_name == "open_setup":
            self.open_setup_window()
        elif action_name == "quit_app":
            self.quit_application()

    @Slot()
    def toggle_voice_translation(self):
        """음성 번역 시작/중지 토글"""
        if self.stt_processor_thread and self.stt_processor_thread.isRunning():
            self.stop_voice_translation()
        else:
            self.start_voice_translation()

    def start_voice_translation(self):
        self.stop_voice_translation()
        self.stt_processor_thread = QThread()
        self.audio_processor = AudioProcessor(self.config_manager)
        self.audio_processor.moveToThread(self.stt_processor_thread)
        self.stt_processor_thread.started.connect(self.audio_processor.start_processing)
        self.audio_processor.audio_chunk_ready.connect(self.worker.process_stt_audio)
        self.audio_processor.stopped.connect(self.stt_processor_thread.quit)
        self.stt_processor_thread.finished.connect(self.on_stt_thread_finished)
        self.stt_processor_thread.start()
        self.overlay_manager.update_status("음성 감지 대기 중...")        
        self.voice_translation_action.setText("음성 번역 중지")

    def stop_voice_translation(self):
        if self.stt_processor_thread and self.stt_processor_thread.isRunning():
            logging.info("음성 번역 스레드 종료 요청...")
            self.audio_processor.stop()
            self.stt_processor_thread.quit()
            self.stt_processor_thread.wait(500)
        self.overlay_manager.hide_all()
        self.voice_translation_action.setText("음성 번역 시작")

    def on_stt_thread_finished(self):
        logging.info("음성 번역 스레드 정리 완료.")
        self.stt_processor_thread = None
        self.audio_processor = None

    @Slot()
    def toggle_ocr_translation(self):
        """화면 번역 시작/중지 토글"""
        if self.ocr_monitor_thread and self.ocr_monitor_thread.isRunning():
            self.stop_ocr_monitoring()
        else:
            self.start_ocr_capture_mode()

    def start_ocr_capture_mode(self):
        self.ocr_capturer = OcrCapturer()
        self.ocr_capturer.region_selected.connect(self.start_ocr_monitoring_on_region)
        self.ocr_capturer.show()

    @Slot(QRect)
    def start_ocr_monitoring_on_region(self, selected_rect):
        self.stop_ocr_monitoring()
        self.ocr_monitor_thread = QThread()

        # [수정] ScreenMonitor 생성 시, 오버레이 위치를 알려주는 함수를 함께 전달
        self.screen_monitor = ScreenMonitor(
            rect=selected_rect,
            ignored_rect_func=self.overlay_manager.get_overlay_geometry
        )
        
        self.screen_monitor.moveToThread(self.ocr_monitor_thread)
        self.ocr_monitor_thread.started.connect(self.screen_monitor.start_monitoring)

        self.screen_monitor.image_changed.connect(self.worker.process_ocr_image)
        self.screen_monitor.stopped.connect(self.ocr_monitor_thread.quit)
        self.ocr_monitor_thread.finished.connect(self.on_ocr_thread_finished)
        self.ocr_monitor_thread.start()
        self.overlay_manager.update_status("화면 변화 감시 중...")
        self.ocr_translation_action.setText("화면 번역 중지")

    def stop_ocr_monitoring(self):
        if self.ocr_monitor_thread and self.ocr_monitor_thread.isRunning():
            logging.info("화면 번역 스레드 종료 요청...")
            if self.screen_monitor:
                self.screen_monitor.stop()
            self.ocr_monitor_thread.quit()
            self.ocr_monitor_thread.wait(500)
        self.overlay_manager.hide_all()
        self.ocr_translation_action.setText("화면 번역 (영역 지정)")

    def on_ocr_thread_finished(self):
        logging.info("화면 번역 스레드 정리 완료.")
        self.ocr_monitor_thread = None
        self.screen_monitor = None

    @Slot(str)
    def on_worker_error(self, message):
        QMessageBox.critical(None, "작업 오류", message)

    def open_setup_window(self):
        """설정 창을 열거나, 이미 열려있으면 맨 앞으로 가져옵니다."""
        if not self.setup_window:
            self.setup_window = SetupWindow(self.config_manager)
            self.setup_window.closed.connect(lambda: setattr(self, 'setup_window', None))
            self.setup_window.show()
            self.setup_window.activateWindow()
        else:
            self.setup_window.activateWindow()

    def quit_application(self):
        """애플리케이션을 안전하게 종료합니다."""
        logging.info("애플리케이션 종료 요청...")
        self.stop_ocr_monitoring()
        self.stop_voice_translation()
        if self.hotkey_manager:
            self.hotkey_manager.stop()
        self.app.quit()