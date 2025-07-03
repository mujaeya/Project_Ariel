import sys
import logging
from PySide6.QtWidgets import QSystemTrayIcon, QMenu, QMessageBox, QApplication
from PySide6.QtGui import QIcon, QAction
from PySide6.QtCore import Slot, QObject, QRect, QThread

from ..utils import resource_path
from ..config_manager import ConfigManager
from .setup_window import SetupWindow
from .overlay_manager import OverlayManager
from .ocr_capturer import OcrCapturer
from ..core.screen_monitor import ScreenMonitor
from ..core.translation_worker import TranslationWorker
from ..core.hotkey_manager import HotkeyManager
from ..core.audio_processor import AudioProcessor
from ..core.sound_player import SoundPlayer

class TrayIcon(QObject):
    def __init__(self, config_manager: ConfigManager, icon_path: str, app: QApplication):
        super().__init__()
        self.app = app
        self.config_manager = config_manager
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(QIcon(icon_path))
        self.tray_icon.setToolTip("Ariel by Seeth")

        # --- 핵심 컴포넌트 ---
        self.worker_thread = QThread(self)
        self.worker = TranslationWorker(self.config_manager)
        self.worker.moveToThread(self.worker_thread)
        self.worker_thread.start()

        self.hotkey_manager = HotkeyManager(self.config_manager, self)
        self.overlay_manager = OverlayManager(self.config_manager, self)
        self.sound_player = SoundPlayer(self)

        self.setup_window = None
        self.ocr_capturer = None
        self.ocr_monitor_thread, self.screen_monitor = None, None
        self.stt_processor_thread, self.audio_processor = None, None

        self.create_menu()
        self.tray_icon.setContextMenu(self.menu)
        self.tray_icon.show()

        # --- 시그널 연결 ---
        self.hotkey_manager.hotkey_pressed.connect(self.on_hotkey_pressed)
        self.worker.translation_ready.connect(self.overlay_manager.add_translation)
        self.worker.status_updated.connect(self.overlay_manager.update_status)
        self.worker.error_occurred.connect(self.on_worker_error)

        logging.info("트레이 아이콘 및 핵심 컴포넌트 준비 완료.")
        volume = self.config_manager.get("sound_master_volume", 80) / 100.0
        self.sound_player.play(self.config_manager.get("sound_app_start"), volume)
        
        # --- [수정됨] 최초 실행 검사 및 설정 창 자동 열기 ---
        if self.config_manager.get("is_first_run", True):
            logging.info("최초 실행을 감지했습니다. 설정 창을 자동으로 엽니다.")
            self.open_setup_window()
            # 다음 실행부터는 창이 열리지 않도록 플래그를 업데이트합니다.
            self.config_manager.set("is_first_run", False)

    def create_menu(self):
        self.menu = QMenu()
        self.voice_translation_action = self.menu.addAction("음성 번역 시작/중지")
        self.voice_translation_action.setCheckable(True)

        self.ocr_translation_action = self.menu.addAction("화면 번역 시작/중지")
        self.ocr_translation_action.setCheckable(True)

        self.menu.addSeparator()
        self.setup_action = self.menu.addAction("설정...")
        self.quit_action = self.menu.addAction("종료")

        self.voice_translation_action.toggled.connect(self.toggle_voice_translation)
        self.ocr_translation_action.toggled.connect(self.toggle_ocr_translation)
        self.setup_action.triggered.connect(self.open_setup_window)
        self.quit_action.triggered.connect(self.quit_application)

    @Slot(str)
    def on_hotkey_pressed(self, action_name):
        logging.info(f"단축키 액션 '{action_name}' 수신")
        if action_name == "toggle_stt": self.voice_translation_action.toggle()
        elif action_name == "toggle_ocr": self.ocr_translation_action.toggle()
        elif action_name == "stop_stt": self.stop_voice_translation()
        elif action_name == "stop_ocr": self.stop_ocr_monitoring()
        elif action_name == "toggle_setup": self.toggle_setup_window()
        elif action_name == "quit_app": self.quit_application()

    @Slot(bool)
    def toggle_voice_translation(self, checked):
        if checked:
            self.start_voice_translation()
        else:
            self.stop_voice_translation()

    def start_voice_translation(self):
        self.stop_voice_translation()

        self.stt_processor_thread = QThread(self)
        self.audio_processor = AudioProcessor(self.config_manager)
        self.audio_processor.moveToThread(self.stt_processor_thread)

        self.stt_processor_thread.started.connect(self.audio_processor.start_processing)
        self.audio_processor.audio_chunk_ready.connect(self.worker.process_stt_audio)
        self.audio_processor.status_updated.connect(self.overlay_manager.update_status)
        self.audio_processor.stopped.connect(self.stt_processor_thread.quit)
        self.stt_processor_thread.finished.connect(self.stt_processor_thread.deleteLater)
        self.audio_processor.finished.connect(self.audio_processor.deleteLater)

        self.stt_processor_thread.start()
        self.overlay_manager.update_status("음성 감지 대기 중...")
        
        volume = self.config_manager.get("sound_master_volume", 80) / 100.0
        self.sound_player.play(self.config_manager.get("sound_stt_start"), volume)
        self.voice_translation_action.setChecked(True)

    def stop_voice_translation(self):
        if self.stt_processor_thread is None:
            return

        was_running = self.voice_translation_action.isChecked()

        if self.audio_processor:
            self.audio_processor.stop()

        self.stt_processor_thread.quit()
        self.stt_processor_thread.wait(500)

        self.audio_processor = None
        self.stt_processor_thread = None

        if was_running:
            self.overlay_manager.update_status("")
            self.voice_translation_action.setChecked(False)
            volume = self.config_manager.get("sound_master_volume", 80) / 100.0
            self.sound_player.play(self.config_manager.get("sound_stt_stop"), volume)

    @Slot(bool)
    def toggle_ocr_translation(self, checked):
        if checked:
            self.stop_ocr_monitoring() # 먼저 정리
            self.ocr_capturer = OcrCapturer()
            self.ocr_capturer.region_selected.connect(self.start_ocr_monitoring_on_region)
            self.ocr_capturer.finished.connect(self._on_ocr_capturer_finished)
            self.ocr_capturer.show()
        else:
            self.stop_ocr_monitoring()

    @Slot()
    def _on_ocr_capturer_finished(self):
        is_running = self.ocr_monitor_thread is not None and self.ocr_monitor_thread.isRunning()
        self.ocr_translation_action.setChecked(is_running)
        self.ocr_capturer = None

    @Slot(QRect)
    def start_ocr_monitoring_on_region(self, selected_rect):
        self.ocr_monitor_thread = QThread(self)
        self.screen_monitor = ScreenMonitor(
            rect=selected_rect, ignored_rect_func=self.overlay_manager.get_overlay_geometry)
        self.screen_monitor.moveToThread(self.ocr_monitor_thread)

        self.ocr_monitor_thread.started.connect(self.screen_monitor.start_monitoring)
        self.screen_monitor.image_changed.connect(self.worker.process_ocr_image)
        self.screen_monitor.stopped.connect(self.ocr_monitor_thread.quit)
        self.ocr_monitor_thread.finished.connect(self.screen_monitor.deleteLater)
        self.ocr_monitor_thread.finished.connect(self.ocr_monitor_thread.deleteLater)

        self.ocr_monitor_thread.start()
        self.overlay_manager.update_status("화면 변화 감시 중...")
        volume = self.config_manager.get("sound_master_volume", 80) / 100.0
        self.sound_player.play(self.config_manager.get("sound_ocr_start"), volume)
        self.ocr_translation_action.setChecked(True)

    def stop_ocr_monitoring(self):
        if self.ocr_monitor_thread is None:
            return

        was_running = self.ocr_translation_action.isChecked()

        if self.screen_monitor:
            self.screen_monitor.stop()

        self.ocr_monitor_thread.quit()
        self.ocr_monitor_thread.wait(500)

        self.screen_monitor = None
        self.ocr_monitor_thread = None

        if was_running:
            self.overlay_manager.hide_all()
            self.ocr_translation_action.setChecked(False)
            volume = self.config_manager.get("sound_master_volume", 80) / 100.0
            self.sound_player.play(self.config_manager.get("sound_ocr_stop"), volume)

    @Slot(str)
    def on_worker_error(self, message):
        QMessageBox.critical(None, "작업 오류", message)
        if self.voice_translation_action.isChecked(): self.stop_voice_translation()
        if self.ocr_translation_action.isChecked(): self.stop_ocr_monitoring()

    def open_setup_window(self):
        if not self.setup_window or not self.setup_window.isVisible():
            self.setup_window = SetupWindow(self.config_manager)
            # 설정 창이 닫힐 때 단축키를 다시 로드하도록 시그널 연결
            self.setup_window.closed.connect(self.on_setup_window_closed)
            self.setup_window.show()
        self.setup_window.activateWindow()
        self.setup_window.raise_()

    @Slot()
    def on_setup_window_closed(self):
        """설정 창이 닫히면 HotkeyManager에게 설정을 다시 불러오라고 알립니다."""
        logging.info("설정 창이 닫혔습니다. 단축키를 다시 로드합니다.")
        self.hotkey_manager.reload_hotkeys()

    def toggle_setup_window(self):
        if not self.setup_window or not self.setup_window.isVisible():
            self.open_setup_window()
        else:
            self.setup_window.close()

    def quit_application(self):
        logging.info("애플리케이션 종료 절차 시작...")
        self.stop_ocr_monitoring()
        self.stop_voice_translation()

        if self.hotkey_manager:
            self.hotkey_manager.stop()

        self.worker_thread.quit()
        self.worker_thread.wait(500)

        logging.info("모든 리소스 정리 완료. 애플리케이션을 종료합니다.")
        self.app.quit()