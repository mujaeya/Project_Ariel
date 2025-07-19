# ariel_client/src/gui/tray_icon.py (이 코드로 전체 교체)
import logging
from PySide6.QtWidgets import QSystemTrayIcon, QMenu, QMessageBox, QApplication
from PySide6.QtGui import QIcon, QAction
from PySide6.QtCore import Slot, QObject, QRect, QThread, QTimer, QCoreApplication

from ..config_manager import ConfigManager
from .setup_window import SetupWindow
from .overlay_manager import OverlayManager
from .ocr_capturer import OcrCapturer
from ..core.screen_monitor import ScreenMonitor
from ..core.translation_worker import TranslationWorker
from ..core.hotkey_manager import HotkeyManager
from ..core.audio_processor import AudioProcessor
from ..core.sound_player import SoundPlayer

logger = logging.getLogger(__name__)

class TrayIcon(QObject):
    def __init__(self, config_manager: ConfigManager, icon: QIcon, app: QApplication):
        super().__init__()
        self.app = app
        self.config_manager = config_manager
        
        self.sound_player = SoundPlayer(self.config_manager, self)
        self.tray_icon = QSystemTrayIcon(icon, self)
        self.tray_icon.setToolTip("Ariel by Seeth")

        self.worker_thread = QThread()
        self.worker = TranslationWorker(self.config_manager)
        self.worker.moveToThread(self.worker_thread)

        self.hotkey_manager = HotkeyManager(self.config_manager, self)
        self.overlay_manager = OverlayManager(config_manager, self)
        
        self.audio_thread = self.audio_processor = None
        self.setup_window = self.ocr_capturer = None
        self.ocr_monitor_thread = self.screen_monitor = None

        self.create_menu()
        self.tray_icon.setContextMenu(self.menu)
        self.connect_signals()

        self.tray_icon.show()
        self.worker_thread.start()
        self.hotkey_manager.start()
        self.sound_player.play("sound_app_start")

        if self.config_manager.get("is_first_run"):
            QTimer.singleShot(100, self.open_setup_window)

    def connect_signals(self):
        self.worker.stt_translation_ready.connect(self.overlay_manager.add_stt_translation)
        self.worker.ocr_patches_ready.connect(self.overlay_manager.show_ocr_patches)
        self.worker.error_occurred.connect(self.on_worker_error)
        self.worker.status_updated.connect(self.overlay_manager.add_system_message_to_stt)
        self.worker_thread.finished.connect(self.worker.deleteLater)
        self.hotkey_manager.hotkey_pressed.connect(self.on_hotkey_pressed)
        self.config_manager.settings_changed.connect(self.hotkey_manager.reload_hotkeys)
        self.config_manager.settings_changed.connect(self.sound_player.update_volume)
    
    def create_menu(self):
        self.menu = QMenu()
        self.voice_translation_action = QAction(self.tr("Start Voice Translation"), self, checkable=True)
        self.ocr_translation_action = QAction(self.tr("Start Screen Translation"), self, checkable=True)
        self.setup_action = QAction(self.tr("Settings..."), self)
        self.quit_action = QAction(self.tr("Quit"), self)

        self.menu.addAction(self.voice_translation_action); self.menu.addAction(self.ocr_translation_action)
        self.menu.addSeparator(); self.menu.addAction(self.setup_action); self.menu.addAction(self.quit_action)

        self.voice_translation_action.toggled.connect(self.toggle_voice_translation)
        self.ocr_translation_action.toggled.connect(self.toggle_ocr_translation)
        self.setup_action.triggered.connect(self.open_setup_window)
        self.quit_action.triggered.connect(self.quit_application)

    def open_setup_window(self):
        # [수정] 창이 이미 열려있으면 닫고, 없으면 새로 엽니다.
        if self.setup_window and self.setup_window.isVisible():
            self.setup_window.close()
            self.setup_window = None
        else:
            self.setup_window = SetupWindow(self.config_manager)
            self.setup_window.show()
            self.setup_window.activateWindow()

    @Slot(str)
    def on_hotkey_pressed(self, action_name: str):
        actions = {"hotkey_toggle_stt": self.voice_translation_action.toggle, "hotkey_toggle_ocr": self.ocr_translation_action.toggle, "hotkey_toggle_setup": self.open_setup_window, "hotkey_quit_app": self.quit_application}
        if (action := actions.get(action_name)): action()

    @Slot(bool)
    def toggle_voice_translation(self, checked: bool):
        if checked: self.start_voice_translation()
        else: self.stop_voice_translation()

    def start_voice_translation(self):
        if self.audio_thread and self.audio_thread.isRunning(): return
        self.audio_thread = QThread()
        self.audio_processor = AudioProcessor(self.config_manager)
        self.audio_processor.moveToThread(self.audio_thread)
        
        # [수정] TranslationWorker의 슬롯에 맞게 채널 수를 전달
        self.audio_processor.audio_processed.connect(self.worker.process_stt_audio)
        self.audio_processor.status_updated.connect(lambda msg: self.overlay_manager.add_system_message_to_stt(f"Audio: {msg}"))
        self.audio_processor.finished.connect(self.audio_thread.quit)
        self.audio_thread.finished.connect(self.on_audio_thread_finished)
        self.audio_thread.started.connect(self.audio_processor.run)
        
        self.audio_thread.start()
        self.sound_player.play("sound_stt_start")
        self.overlay_manager.show_stt_overlay()
        self.voice_translation_action.setText(self.tr("Stop Voice Translation"))

    def stop_voice_translation(self):
        if self.audio_processor: self.audio_processor.stop()
        else: self.on_audio_thread_finished()
            
    @Slot()
    def on_audio_thread_finished(self):
        if self.audio_processor: self.audio_processor.deleteLater(); self.audio_processor = None
        if self.audio_thread: self.audio_thread.deleteLater(); self.audio_thread = None
        self.sound_player.play("sound_stt_stop")
        self.overlay_manager.hide_stt_overlay()
        if self.voice_translation_action.isChecked(): self.voice_translation_action.setChecked(False)
        self.voice_translation_action.setText(self.tr("Start Voice Translation"))

    @Slot(bool)
    def toggle_ocr_translation(self, checked: bool):
        if checked: self.select_ocr_region()
        else: self.stop_ocr_monitoring()

    def select_ocr_region(self):
        if self.ocr_capturer and self.ocr_capturer.isVisible(): return
        self.ocr_capturer = OcrCapturer()
        self.ocr_capturer.region_selected.connect(self.start_ocr_monitoring_on_region)
        self.ocr_capturer.cancelled.connect(lambda: self.ocr_translation_action.setChecked(False))
        self.ocr_capturer.show()

    @Slot(QRect)
    def start_ocr_monitoring_on_region(self, rect: QRect):
        if rect.isNull():
            self.ocr_translation_action.setChecked(False); return
        self.stop_ocr_monitoring(play_sound=False)
        self.ocr_monitor_thread = QThread()
        self.screen_monitor = ScreenMonitor(rect, self.overlay_manager.get_stt_overlay_geometry)
        self.screen_monitor.moveToThread(self.ocr_monitor_thread)
        self.screen_monitor.image_changed.connect(self.worker.process_ocr_image)
        self.screen_monitor.finished.connect(self.ocr_monitor_thread.quit)
        self.ocr_monitor_thread.finished.connect(self.on_ocr_thread_finished)
        self.ocr_monitor_thread.started.connect(self.screen_monitor.start_monitoring)
        self.ocr_monitor_thread.start()
        self.sound_player.play("sound_ocr_start")
        self.ocr_translation_action.setText(self.tr("Stop Screen Translation"))

    def stop_ocr_monitoring(self, play_sound=True):
        if self.screen_monitor: self.screen_monitor.stop()
        else: self.on_ocr_thread_finished(play_sound=play_sound)

    @Slot(bool)
    def on_ocr_thread_finished(self, play_sound=True):
        if self.screen_monitor: self.screen_monitor.deleteLater(); self.screen_monitor = None
        if self.ocr_monitor_thread: self.ocr_monitor_thread.deleteLater(); self.ocr_monitor_thread = None
        self.overlay_manager.hide_ocr_overlay()
        if play_sound: self.sound_player.play("sound_ocr_stop")
        if self.ocr_translation_action.isChecked(): self.ocr_translation_action.setChecked(False)
        self.ocr_translation_action.setText(self.tr("Start Screen Translation"))

    @Slot(str)
    def on_worker_error(self, message: str):
        QMessageBox.warning(None, self.tr("Error"), message)
        if "STT" in message or "Audio" in message: self.voice_translation_action.setChecked(False)
        if "OCR" in message or "Screen" in message: self.ocr_translation_action.setChecked(False)

    def quit_application(self):
        self.hotkey_manager.stop()
        if self.voice_translation_action.isChecked(): self.stop_voice_translation()
        if self.ocr_translation_action.isChecked(): self.stop_ocr_monitoring()
        QTimer.singleShot(500, self._quit_threads_and_app)

    def _quit_threads_and_app(self):
        if self.worker_thread and self.worker_thread.isRunning():
            self.worker_thread.quit(); self.worker_thread.wait(1000)
        self.tray_icon.hide(); QApplication.instance().quit()

    def tr(self, text): return QCoreApplication.translate("TrayIcon", text)