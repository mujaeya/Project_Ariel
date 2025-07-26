# ariel_client/src/gui/tray_icon.py (수정 완료)

import logging
import queue
import time

from PySide6.QtWidgets import QSystemTrayIcon, QMenu, QMessageBox, QApplication
from PySide6.QtGui import QIcon, QAction
from PySide6.QtCore import QObject, QRect, QThread, QTimer, QCoreApplication, Signal, Slot

from ..config_manager import ConfigManager
from .setup_window import SetupWindow
from .overlay_manager import OverlayManager
from .ocr_capturer import OcrCapturer
from ..core.screen_monitor import ScreenMonitor
from ..core.translation_worker import TranslationWorker
from ..core.hotkey_manager import HotkeyManager
from ..core.sound_player import SoundPlayer

from ..core.audio_capturer import AudioCapturer
from ..core.audio_processor import AudioProcessor


logger = logging.getLogger(__name__)


class TrayIcon(QObject):
    sound_request_queued = Signal(str)

    def __init__(self, config_manager: ConfigManager, icon: QIcon, app: QApplication):
        super().__init__()
        self.app = app
        self.config_manager = config_manager
        self.audio_queue = queue.Queue()
        self._last_error_time = 0

        self.sound_player = SoundPlayer(self.config_manager, self)
        self.tray_icon = QSystemTrayIcon(icon, self)
        # [수정] ToolTip 국제화 처리
        self.tray_icon.setToolTip(self.tr("TrayIcon", "Ariel by Seeth"))

        self.worker_thread = QThread()
        self.worker = TranslationWorker(self.config_manager)
        self.worker.moveToThread(self.worker_thread)

        self.hotkey_manager = HotkeyManager(self.config_manager, self)
        self.overlay_manager = OverlayManager(config_manager, self)

        self.setup_window = None
        self.ocr_capturer = None
        self.ocr_monitor_thread = None
        self.screen_monitor = None
        
        self.capturer_thread = None
        self.audio_capturer = None
        self.processor_thread = None
        self.audio_processor = None

        self.threads = [] 

        self.create_menu()
        self.tray_icon.setContextMenu(self.menu)
        self.connect_base_signals()
        
        self.tray_icon.show()
        self.worker_thread.start()
        self.threads.append(self.worker_thread)
        
        self.hotkey_manager.start()
        self.sound_request_queued.emit("sound_app_start")

        if self.config_manager.get("is_first_run"):
            QTimer.singleShot(100, self.open_setup_window)

    def connect_base_signals(self):
        self.sound_request_queued.connect(self.sound_player.play)
        
        self.worker.stt_chunk_translated.connect(self.overlay_manager.add_stt_chunk)
        self.worker.stt_status_updated.connect(self.overlay_manager.update_stt_status)
        self.worker.ocr_patches_ready.connect(self.overlay_manager.show_ocr_patches)
        self.worker.ocr_status_updated.connect(self.overlay_manager.update_ocr_status)
        self.worker.error_occurred.connect(self.on_worker_error)
        
        self.worker_thread.finished.connect(self.worker.deleteLater)
        
        self.hotkey_manager.hotkey_pressed.connect(self.on_hotkey_pressed)
        
        self.config_manager.settings_changed.connect(self.overlay_manager.on_settings_changed)
        self.config_manager.settings_changed.connect(self.hotkey_manager.reload_hotkeys)
        self.config_manager.settings_changed.connect(self.sound_player.update_volume)

    def create_menu(self):
        self.menu = QMenu()
        # [수정] 컨텍스트를 명시하여 tr() 호출
        self.voice_translation_action = QAction(self.tr("TrayIcon", "Start Voice Translation"), self, checkable=True)
        self.ocr_translation_action = QAction(self.tr("TrayIcon", "Start Screen Translation"), self, checkable=True)
        self.setup_action = QAction(self.tr("TrayIcon", "Settings..."), self)
        self.quit_action = QAction(self.tr("TrayIcon", "Quit"), self)

        self.menu.addAction(self.voice_translation_action)
        self.menu.addAction(self.ocr_translation_action)
        self.menu.addSeparator()
        self.menu.addAction(self.setup_action)
        self.menu.addAction(self.quit_action)

        self.voice_translation_action.toggled.connect(self.toggle_voice_translation)
        self.ocr_translation_action.toggled.connect(self.toggle_ocr_translation)
        self.setup_action.triggered.connect(self.open_setup_window)
        self.quit_action.triggered.connect(self.quit_application)
    
    def open_setup_window(self):
        if self.setup_window and self.setup_window.isVisible():
            self.setup_window.close()
            self.setup_window = None
        else:
            self.setup_window = SetupWindow(self.config_manager)
            self.setup_window.show()
            self.setup_window.raise_()
            self.setup_window.activateWindow()

    @Slot(str)
    def on_hotkey_pressed(self, action_name: str):
        actions = {
            "hotkey_toggle_stt": self.voice_translation_action.toggle,
            "hotkey_toggle_ocr": self.ocr_translation_action.toggle,
            "hotkey_toggle_setup": self.open_setup_window,
            "hotkey_quit_app": self.quit_application
        }
        if (action := actions.get(action_name)):
            action()

    @Slot(bool)
    def toggle_voice_translation(self, checked: bool):
        self.worker.set_stt_enabled(checked)
        self.voice_translation_action.setEnabled(False) 
        
        if checked:
            lang = self.config_manager.get("stt_source_language", "auto")
            self.worker.set_stt_language(lang)
            self.start_voice_translation()
        else:
            self.stop_voice_translation()
        
        QTimer.singleShot(1000, lambda: self.voice_translation_action.setEnabled(True))

    def start_voice_translation(self):
        if self.capturer_thread or self.processor_thread:
            logger.warning("Audio threads are already running. Ignoring start request.")
            if not self.voice_translation_action.isChecked():
                self.voice_translation_action.setChecked(True)
            return

        logger.info("Starting voice translation service (real-time architecture)...")
        
        self.processor_thread = QThread()
        self.threads.append(self.processor_thread)
        self.audio_processor = AudioProcessor(self.config_manager, self.audio_queue)
        self.audio_processor.moveToThread(self.processor_thread)

        self.audio_processor.audio_chunk_ready.connect(self.worker.process_stt_chunk)
        self.audio_processor.status_updated.connect(self.overlay_manager.update_stt_status)
        self.audio_processor.error_occurred.connect(self.on_worker_error)
        self.audio_processor.finished.connect(self.on_audio_threads_finished)
        self.processor_thread.started.connect(self.audio_processor.run)

        self.capturer_thread = QThread()
        self.threads.append(self.capturer_thread)
        self.audio_capturer = AudioCapturer(self.audio_queue)
        self.audio_capturer.moveToThread(self.capturer_thread)
        self.audio_capturer.error_occurred.connect(self.on_worker_error)
        self.capturer_thread.started.connect(self.audio_capturer.start_capturing)
        
        self.processor_thread.start()
        self.capturer_thread.start()
        
        self.sound_request_queued.emit("sound_stt_start")
        self.overlay_manager.show_stt_overlay()
        # [수정] 동적 텍스트도 tr() 적용
        self.voice_translation_action.setText(self.tr("TrayIcon", "Stop Voice Translation"))
        logger.info("Voice translation service started.")

    def stop_voice_translation(self):
        logger.info("Stopping voice translation service...")
        if self.audio_capturer:
            self.audio_capturer.stop_capturing()
        if self.audio_processor:
            self.audio_processor.stop()

    @Slot()
    def on_audio_threads_finished(self):
        logger.debug("on_audio_threads_finished slot called.")
        
        if self.audio_processor:
            self.audio_processor.deleteLater()
            self.audio_processor = None
        if self.processor_thread in self.threads:
            self.threads.remove(self.processor_thread)
        if self.processor_thread:
            self.processor_thread.quit()
            self.processor_thread.wait(1000)
            self.processor_thread.deleteLater()
            self.processor_thread = None

        if self.audio_capturer:
            self.audio_capturer.deleteLater()
            self.audio_capturer = None
        if self.capturer_thread in self.threads:
            self.threads.remove(self.capturer_thread)
        if self.capturer_thread:
            self.capturer_thread.quit()
            self.capturer_thread.wait(1000)
            self.capturer_thread.deleteLater()
            self.capturer_thread = None

        while not self.audio_queue.empty():
            try: self.audio_queue.get_nowait()
            except queue.Empty: break

        self.sound_request_queued.emit("sound_stt_stop")
        self.overlay_manager.hide_stt_overlay()
        
        if self.voice_translation_action.isChecked():
            self.voice_translation_action.setChecked(False)
        # [수정] 동적 텍스트도 tr() 적용
        self.voice_translation_action.setText(self.tr("TrayIcon", "Start Voice Translation"))
        
        logger.info("All resources related to the voice translation service have been cleaned up.")

    @Slot(bool)
    def toggle_ocr_translation(self, checked: bool):
        self.ocr_translation_action.setEnabled(False)
        if checked:
            self.select_ocr_region()
        else:
            self.stop_ocr_monitoring()
        QTimer.singleShot(500, lambda: self.ocr_translation_action.setEnabled(True))

    def select_ocr_region(self):
        if self.ocr_capturer and self.ocr_capturer.isVisible(): return
        self.ocr_capturer = OcrCapturer()
        self.ocr_capturer.region_selected.connect(self.start_ocr_monitoring_on_region)
        self.ocr_capturer.cancelled.connect(lambda: self.ocr_translation_action.setChecked(False))
        self.ocr_capturer.show()

    @Slot(QRect)
    def start_ocr_monitoring_on_region(self, rect: QRect):
        if rect.isNull():
            self.ocr_translation_action.setChecked(False)
            return
        
        if self.ocr_monitor_thread and self.ocr_monitor_thread.isRunning():
            self.stop_ocr_monitoring()
            QTimer.singleShot(100, lambda: self._start_ocr_monitoring_after_stop(rect))
        else:
             self._start_ocr_monitoring_after_stop(rect)

    def _start_ocr_monitoring_after_stop(self, rect: QRect):
        if self.ocr_monitor_thread is not None:
            logger.warning("Screen monitor thread is still cleaning up. Ignoring start request.")
            self.ocr_translation_action.setChecked(False)
            return

        logger.info(f"Starting screen translation service... (Region: {rect})")
        self.ocr_monitor_thread = QThread()
        self.threads.append(self.ocr_monitor_thread)
        self.screen_monitor = ScreenMonitor(rect, self.overlay_manager.get_stt_overlay_geometry)
        self.screen_monitor.moveToThread(self.ocr_monitor_thread)

        self.screen_monitor.image_changed.connect(self.worker.process_ocr_image)
        self.screen_monitor.finished.connect(self.ocr_monitor_thread.quit)
        self.ocr_monitor_thread.started.connect(self.screen_monitor.start_monitoring)
        self.ocr_monitor_thread.finished.connect(lambda: self.on_ocr_thread_finished(play_sound=False))

        self.ocr_monitor_thread.start()
        self.sound_request_queued.emit("sound_ocr_start")
        # [수정] 동적 텍스트도 tr() 적용
        self.ocr_translation_action.setText(self.tr("TrayIcon", "Stop Screen Translation"))
        logger.info("Screen translation service started.")

    def stop_ocr_monitoring(self, play_sound=True):
        logger.info("Stopping screen translation service...")
        if self.screen_monitor:
            self.screen_monitor.stop()

    @Slot(bool)
    def on_ocr_thread_finished(self, play_sound=True):
        logger.debug("on_ocr_thread_finished slot called.")
        if self.screen_monitor:
            self.screen_monitor.deleteLater()
            self.screen_monitor = None
        if self.ocr_monitor_thread in self.threads:
            self.threads.remove(self.ocr_monitor_thread)
        if self.ocr_monitor_thread:
            self.ocr_monitor_thread.quit()
            self.ocr_monitor_thread.wait(1000)
            self.ocr_monitor_thread.deleteLater()
            self.ocr_monitor_thread = None

        self.overlay_manager.hide_ocr_overlay()
        if play_sound: self.sound_request_queued.emit("sound_ocr_stop")
        if self.ocr_translation_action.isChecked():
            self.ocr_translation_action.setChecked(False)
        # [수정] 동적 텍스트도 tr() 적용
        self.ocr_translation_action.setText(self.tr("TrayIcon", "Start Screen Translation"))
        logger.info("All resources and UI related to the screen translation service have been cleaned up.")

    @Slot(str)
    def on_worker_error(self, message: str):
        if time.time() - self._last_error_time < 5:
            return
        self._last_error_time = time.time()
        
        # [수정] QMessageBox 제목 국제화 처리
        error_title = self.tr("TrayIcon", "Error")
        QMessageBox.warning(None, error_title, message)
        
        if "STT" in message or "Audio" in message or "VAD" in message: 
            if self.voice_translation_action.isChecked():
                self.voice_translation_action.toggle()
        if "OCR" in message or "Screen" in message: 
            if self.ocr_translation_action.isChecked():
                self.ocr_translation_action.toggle()

    def cleanup_threads(self):
        logger.info("Starting cleanup of all background threads...")
        
        self.stop_voice_translation()
        self.stop_ocr_monitoring(play_sound=False)
        
        if self.worker_thread:
            self.worker_thread.quit()

        for thread in list(self.threads):
            if thread and thread.isRunning():
                logger.info(f"Waiting for thread to finish...")
                if not thread.wait(3000):
                    logger.warning(f"Thread did not finish gracefully within 3 seconds. Attempting to terminate.")
                    thread.terminate()

        logger.info("All threads have been cleaned up.")

    @Slot()
    def quit_application(self):
        logger.info("Starting application quit procedure...")
        self.tray_icon.hide()
        if self.setup_window:
            self.setup_window.close()
        
        self.hotkey_manager.stop()
        self.cleanup_threads()
        
        logger.info("All resources cleaned up. Quitting application.")
        QTimer.singleShot(100, QApplication.instance().quit)
    
    # [수정] 컨텍스트를 받는 tr() 메서드로 변경
    def tr(self, context, text):
        return QCoreApplication.translate(context, text)