import logging
from PySide6.QtWidgets import QSystemTrayIcon, QMenu, QMessageBox, QApplication
from PySide6.QtGui import QIcon, QAction
from PySide6.QtCore import Slot, QObject, QRect, QThread, QTimer, QCoreApplication

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

logger = logging.getLogger(__name__)

class TrayIcon(QObject):
    def __init__(self, config_manager: ConfigManager, icon: QIcon, app: QApplication):
        super().__init__()
        self.app, self.config_manager = app, config_manager
        self.is_setup_required = self.check_if_setup_is_required()

        self.tray_icon = QSystemTrayIcon(icon, self)
        self.tray_icon.setToolTip("Ariel by Seeth")

        self.worker = None
        self.worker_thread = None
        self.audio_thread = None
        self.audio_processor = None
        self.hotkey_manager = HotkeyManager(self.config_manager, self)
        self.overlay_manager = OverlayManager(config_manager, self)
        self.sound_player = SoundPlayer(self)
        
        self.setup_window, self.ocr_capturer = None, None
        self.ocr_monitor_thread, self.screen_monitor = None, None
        
        self.create_menu()
        self.tray_icon.setContextMenu(self.menu)
        self.hotkey_manager.hotkey_pressed.connect(self.on_hotkey_pressed)
        
        self.tray_icon.show()
        logger.info("트레이 아이콘 및 핵심 컴포넌트 준비 완료.")
        
        self.hotkey_manager.start()
        
        if self.is_setup_required:
            logger.warning("필수 설정이 누락되어 설정 창을 먼저 실행합니다.")
            QTimer.singleShot(100, self.open_setup_window)
        else:
            self.initialize_worker_and_start()

    def check_if_setup_is_required(self):
        api_key = self.config_manager.get("deepl_api_key")
        return self.config_manager.get("is_first_run") or not api_key

    def initialize_worker_and_start(self):
        if self.worker and self.worker_thread and self.worker_thread.isRunning():
            return
        
        logger.info("필수 설정 확인 완료. 번역 엔진을 초기화합니다.")
        try:
            # QThread 객체를 생성하여 self.worker_thread에 할당합니다.
            self.worker_thread = QThread()
            
            # TranslationWorker 객체를 생성합니다.
            self.worker = TranslationWorker(self.config_manager)
            
            # 워커를 새로 만든 스레드로 이동시킵니다.
            self.worker.moveToThread(self.worker_thread)
            
            # 시그널과 슬롯을 연결합니다.
            self.worker.stt_translation_ready.connect(self.overlay_manager.add_stt_translation)
            self.worker.ocr_translation_ready.connect(self.overlay_manager.show_ocr_patches)
            self.worker.error_occurred.connect(self.on_worker_error)
            self.worker.status_updated.connect(self.overlay_manager.add_system_message_to_stt)

            # 스레드 관련 시그널을 연결하여 안전하게 종료될 수 있도록 합니다.
            self.worker_thread.finished.connect(self.worker.deleteLater)
            self.worker_thread.finished.connect(self.worker_thread.deleteLater)

            # 모든 준비가 끝나면 스레드를 시작합니다.
            self.worker_thread.start()
            
            logger.info("번역 엔진 스레드가 성공적으로 시작되었습니다.")
        except Exception as e:
            logger.critical(f"번역 엔진 초기화 실패: {e}", exc_info=True)
            
            # [수정] 복잡한 f-string을 여러 줄로 나누어 가독성을 높이고 잠재적 오류를 방지합니다.
            title = self.tr("Initialization Failed")
            message = self.tr('Failed to initialize translation engine.')
            details = self.tr('Exiting program.')
            full_message = f"{message}\n\n{e}\n\n{details}"
            QMessageBox.critical(None, title, full_message)
            
            self.quit_application()

    def create_menu(self):
        self.menu = QMenu()
        self.voice_translation_action = QAction(self.tr("Start Voice Translation"), self, checkable=True)
        self.ocr_translation_action = QAction(self.tr("Start Screen Translation"), self, checkable=True)
        self.setup_action = QAction(self.tr("Settings..."), self)
        self.quit_action = QAction(self.tr("Quit"), self)
        self.menu.addAction(self.voice_translation_action)
        self.menu.addAction(self.ocr_translation_action)
        self.menu.addSeparator()
        self.menu.addAction(self.setup_action)
        self.menu.addAction(self.quit_action)
        self.voice_translation_action.toggled.connect(self.toggle_voice_translation)
        self.ocr_translation_action.toggled.connect(self.toggle_ocr_translation)
        self.setup_action.triggered.connect(self.open_setup_window)
        self.quit_action.triggered.connect(self.quit_application)

    @Slot()
    def on_setup_window_closed(self):
        logger.info("설정 창이 닫혔습니다. 설정을 다시 확인하고 적용합니다.")
        self.hotkey_manager.reload_hotkeys()
        self.hotkey_manager.start()
        is_setup_now_complete = not self.check_if_setup_is_required()
        if self.is_setup_required and is_setup_now_complete:
            self.is_setup_required = False
            self.initialize_worker_and_start()
        self.setup_window = None

    def open_setup_window(self):
        if self.setup_window and self.setup_window.isVisible():
            self.setup_window.activateWindow()
            return
        self.setup_window = SetupWindow(self.config_manager)
        self.setup_window.closed.connect(self.on_setup_window_closed)
        self.setup_window.show()
        self.setup_window.activateWindow()

    @Slot(str)
    def on_hotkey_pressed(self, action_name: str):
        actions = {
            "hotkey_toggle_stt": self.voice_translation_action.toggle,
            "hotkey_toggle_ocr": self.ocr_translation_action.toggle,
            "hotkey_toggle_setup": self.toggle_setup_window,
            "hotkey_quit_app": self.quit_application
        }
        if (action := actions.get(action_name)):
            logger.info(f"단축키 액션 '{action_name}'을 실행합니다.")
            action()

    def toggle_setup_window(self):
        if not self.setup_window or not self.setup_window.isVisible():
            self.open_setup_window()
        else:
            self.setup_window.close()
            
    @Slot(bool)
    def toggle_voice_translation(self, checked: bool):
        if self.is_setup_required or not self.worker:
            QMessageBox.warning(None, self.tr("Preparation Needed"), self.tr("The translation engine is not ready yet.\nPlease enter your API key in the settings first."))
            self.voice_translation_action.setChecked(False)
            return
        
        self.voice_translation_action.setText(self.tr("Stop Voice Translation") if checked else self.tr("Start Voice Translation"))
        if checked:
            self.start_voice_translation()
        else:
            self.stop_voice_translation()

    def start_voice_translation(self):
        if self.audio_thread and self.audio_thread.isRunning():
            return

        logging.info("음성 번역 스레드 시작")
        self.audio_thread = QThread()
        self.audio_processor = AudioProcessor()
        self.audio_processor.moveToThread(self.audio_thread)

        self.audio_processor.audio_chunk_ready.connect(self.worker.process_stt_audio)
        self.audio_processor.error.connect(self.on_audio_error)
        self.audio_thread.started.connect(self.audio_processor.start)
        
        self.audio_thread.start()
        self.sound_player.play_start_sound()

    def stop_voice_translation(self):
        if not self.audio_thread or not self.audio_thread.isRunning():
            return

        logging.info("음성 번역 스레드 종료 요청")
        if self.audio_processor:
            self.audio_processor.stop()

        self.audio_thread.quit()
        if not self.audio_thread.wait(5000):
            logging.warning("음성 번역 스레드가 제때 종료되지 않아 강제 종료합니다.")
            self.audio_thread.terminate()
            self.audio_thread.wait()

        self.audio_thread = None
        self.audio_processor = None
        
        logging.info("음성 번역 스레드 완전히 종료됨")
        self.sound_player.play_stop_sound()

    @Slot(bool)
    def toggle_ocr_translation(self, checked: bool):
        if self.is_setup_required or not self.worker:
            QMessageBox.warning(None, self.tr("Preparation Needed"), self.tr("The translation engine is not ready yet.\nPlease enter your API key in the settings first."))
            self.ocr_translation_action.setChecked(False)
            return
        
        self.ocr_translation_action.setText(self.tr("Stop Screen Translation") if checked else self.tr("Start Screen Translation"))
        if checked:
            self.select_ocr_region()
        else:
            self.stop_ocr_monitoring()

    def select_ocr_region(self):
        if self.ocr_capturer:
            self.ocr_capturer.activateWindow()
            return
        self.ocr_capturer = OcrCapturer()
        self.ocr_capturer.region_selected.connect(self.start_ocr_monitoring_on_region)
        self.ocr_capturer.cancelled.connect(lambda: self.ocr_translation_action.setChecked(False))
        self.ocr_capturer.finished.connect(lambda: setattr(self, 'ocr_capturer', None))
        self.ocr_capturer.show()

    @Slot(QRect)
    def start_ocr_monitoring_on_region(self, rect: QRect):
        if rect.isNull():
            self.ocr_translation_action.setChecked(False)
            return
            
        self.ocr_monitor_thread = QThread(self)
        self.screen_monitor = ScreenMonitor(rect, self.overlay_manager.get_stt_overlay_geometry)
        self.screen_monitor.moveToThread(self.ocr_monitor_thread)
        self.ocr_monitor_thread.started.connect(self.screen_monitor.start_monitoring)
        self.screen_monitor.image_changed.connect(self.worker.process_ocr_image)
        self.screen_monitor.stopped.connect(self.ocr_monitor_thread.quit)
        self.ocr_monitor_thread.finished.connect(self.screen_monitor.deleteLater)
        self.ocr_monitor_thread.start()
        self.sound_player.play_start_sound()

    def stop_ocr_monitoring(self):
        if self.screen_monitor:
            self.screen_monitor.stop()
        self.overlay_manager.hide_ocr_overlay()
        self.sound_player.play_stop_sound()

    @Slot(str)
    def on_worker_error(self, message: str):
        QMessageBox.warning(None, self.tr("Error"), message)
        if "STT" in message or "Audio" in message:
            self.voice_translation_action.setChecked(False)
        if "OCR" in message or "Screen" in message:
            self.ocr_translation_action.setChecked(False)

    @Slot(str)
    def on_audio_error(self, message: str):
        self.on_worker_error(f"Audio Error: {message}")

    def quit_application(self):
        logger.info("애플리케이션 종료 절차를 시작합니다.")
        self.hotkey_manager.stop()
        if self.audio_thread and self.audio_thread.isRunning():
            self.stop_voice_translation()
        if self.ocr_monitor_thread and self.ocr_monitor_thread.isRunning():
            self.stop_ocr_monitoring()
        
        QTimer.singleShot(500, self._quit_threads_and_app)

    def _quit_threads_and_app(self):
        if self.worker_thread:
            self.worker_thread.quit()
            self.worker_thread.wait()
        self.tray_icon.hide()
        QApplication.instance().quit()

    def tr(self, text):
        return QCoreApplication.translate("TrayIcon", text)