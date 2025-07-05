import logging
from PySide6.QtWidgets import QSystemTrayIcon, QMenu, QMessageBox, QApplication
from PySide6.QtGui import QIcon
from PySide6.QtCore import Slot, QObject, QRect, QThread, QTimer

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
    def __init__(self, config_manager: ConfigManager, icon_path: str, app: QApplication):
        super().__init__()
        self.app, self.config_manager = app, config_manager
        
        active_profile = self.config_manager.get_active_profile()
        api_base_url = active_profile.get("api_base_url")
        deepl_api_key = active_profile.get("deepl_api_key")
        
        self.is_setup_required = self.config_manager.get("is_first_run") or not api_base_url or not deepl_api_key
        
        self.tray_icon = QSystemTrayIcon(QIcon(icon_path), self)
        self.tray_icon.setToolTip("Ariel by Seeth")

        self.worker_thread = None
        self.worker = None

        self.hotkey_manager = HotkeyManager(self.config_manager, self)
        self.overlay_manager = OverlayManager(self.config_manager, self)
        self.sound_player = SoundPlayer(self)

        self.setup_window, self.ocr_capturer = None, None
        self.ocr_monitor_thread, self.screen_monitor = None, None
        self.stt_processor_thread, self.audio_processor = None, None
        self.ocr_capture_rect = None

        self.create_menu()
        self.tray_icon.setContextMenu(self.menu)

        self.hotkey_manager.hotkey_pressed.connect(self.on_hotkey_pressed)
        
        self.tray_icon.show()
        logger.info("트레이 아이콘 및 핵심 컴포넌트 준비 완료.")
        
        if self.is_setup_required:
            logger.warning("필수 설정이 누락되어 설정 창을 먼저 실행합니다.")
            QTimer.singleShot(100, self.open_setup_window)
        else:
            self.initialize_worker_and_start()

    def initialize_worker_and_start(self):
        if self.worker: return

        logger.info("필수 설정 확인 완료. 번역 엔진을 초기화합니다.")
        self.worker_thread = QThread(self)
        try:
            self.worker = TranslationWorker(self.config_manager)
        except ValueError as e:
            logger.critical(f"번역 엔진 초기화 실패: {e}")
            QMessageBox.critical(None, "초기화 실패", f"번역 엔진 초기화에 실패했습니다.\n\n{e}\n\n프로그램을 종료합니다.")
            self.quit_application()
            return

        self.worker.moveToThread(self.worker_thread)
        
        self.worker.stt_translation_ready.connect(self.overlay_manager.add_stt_translation)
        self.worker.ocr_translation_ready.connect(self.overlay_manager.show_ocr_patches)
        self.worker.error_occurred.connect(self.on_worker_error)
        self.worker.status_updated.connect(self.overlay_manager.add_system_message_to_stt)
        
        self.worker_thread.start()

    def create_menu(self):
        self.menu = QMenu()
        self.voice_translation_action = self.menu.addAction("음성 번역")
        self.voice_translation_action.setCheckable(True)
        self.ocr_translation_action = self.menu.addAction("화면 번역")
        self.ocr_translation_action.setCheckable(True)
        self.menu.addSeparator()
        self.setup_action = self.menu.addAction("설정...")
        self.quit_action = self.menu.addAction("종료")
        
        self.voice_translation_action.toggled.connect(self.toggle_voice_translation)
        self.ocr_translation_action.toggled.connect(self.toggle_ocr_translation)
        self.setup_action.triggered.connect(self.open_setup_window)
        self.quit_action.triggered.connect(self.quit_application)

    @Slot(str)
    def on_hotkey_pressed(self, action_name: str):
        # [핵심 수정] 딕셔너리의 키를 ConfigManager의 단축키 이름과 완벽하게 일치시킵니다.
        actions = {
            "hotkey_toggle_stt": self.voice_translation_action.toggle,
            "hotkey_toggle_ocr": self.ocr_translation_action.toggle,
            "hotkey_toggle_setup": self.toggle_setup_window,
            "hotkey_quit_app": self.quit_application
        }
        if (action := actions.get(action_name)):
            logger.info(f"단축키 액션 '{action_name}'을 실행합니다.") # 확인을 위한 로그 추가
            action()
        else:
            logger.warning(f"수신된 단축키 액션 '{action_name}'에 해당하는 동작이 없습니다.")

    def open_setup_window(self):
        if self.setup_window and self.setup_window.isVisible():
            self.setup_window.activateWindow()
            return

        self.setup_window = SetupWindow(self.config_manager)
        self.setup_window.closed.connect(self.on_setup_window_closed)
        self.setup_window.show()
        self.setup_window.activateWindow()

    @Slot()
    def on_setup_window_closed(self):
        logger.info("설정 창이 닫혔습니다. 설정을 다시 확인합니다.")
        
        self.hotkey_manager.reload_hotkeys()
        self.setup_window = None

        if self.config_manager.get("is_first_run"):
            self.config_manager.set("is_first_run", False, is_global=True)

        if self.is_setup_required:
            active_profile = self.config_manager.get_active_profile()
            if active_profile.get("api_base_url") and active_profile.get("deepl_api_key"):
                self.is_setup_required = False
                self.initialize_worker_and_start()
            else:
                logger.error("필수 설정이 여전히 누락되어 프로그램을 안전하게 종료합니다.")
                QMessageBox.warning(None, "설정 필요", "API 키 등 필수 설정이 완료되지 않아 프로그램을 종료합니다.")
                self.quit_application()

    def toggle_setup_window(self):
        if not self.setup_window or not self.setup_window.isVisible():
            self.open_setup_window()
        else:
            self.setup_window.close()

    @Slot(bool)
    def toggle_voice_translation(self, checked: bool):
        if not self.worker:
            QMessageBox.warning(None, "준비 필요", "아직 번역 엔진이 준비되지 않았습니다.\n설정에서 API 키를 먼저 입력해주세요.")
            self.voice_translation_action.setChecked(False)
            return
        if checked: self.start_voice_translation()
        else: self.stop_voice_translation()

    def start_voice_translation(self):
        if self.stt_processor_thread: return
        self.stt_processor_thread = QThread(self)
        self.audio_processor = AudioProcessor(self.config_manager)
        self.audio_processor.moveToThread(self.stt_processor_thread)
        self.audio_processor.audio_chunk_ready.connect(self.worker.process_stt_audio)
        self.audio_processor.status_updated.connect(self.overlay_manager.add_system_message_to_stt)
        self.stt_processor_thread.started.connect(self.audio_processor.start_processing)
        self.audio_processor.finished.connect(self.stt_processor_thread.quit)
        self.stt_processor_thread.finished.connect(self.audio_processor.deleteLater)
        self.stt_processor_thread.finished.connect(self.stt_processor_thread.deleteLater)
        self.stt_processor_thread.finished.connect(lambda: setattr(self, 'audio_processor', None) or setattr(self, 'stt_processor_thread', None))
        self.stt_processor_thread.start()
        self.overlay_manager.show_stt_overlay()
        self.sound_player.play(self.config_manager.get("sound_stt_start"))

    def stop_voice_translation(self):
        if self.audio_processor: self.audio_processor.stop()
        self.overlay_manager.hide_stt_overlay()
        if self.voice_translation_action.isChecked(): self.sound_player.play(self.config_manager.get("sound_stt_stop"))
        self.voice_translation_action.setChecked(False)

    @Slot(bool)
    def toggle_ocr_translation(self, checked: bool):
        if not self.worker:
            QMessageBox.warning(None, "준비 필요", "아직 번역 엔진이 준비되지 않았습니다.\n설정에서 API 키를 먼저 입력해주세요.")
            self.ocr_translation_action.setChecked(False)
            return
        if checked:
            if self.ocr_monitor_thread: self.stop_ocr_monitoring()
            self.select_ocr_region()
        else: self.stop_ocr_monitoring()

    def select_ocr_region(self):
        if self.ocr_capturer: self.ocr_capturer.activateWindow(); return
        self.ocr_capturer = OcrCapturer()
        self.ocr_capturer.region_selected.connect(self.start_ocr_monitoring_on_region)
        self.ocr_capturer.cancelled.connect(lambda: self.ocr_translation_action.setChecked(False))
        self.ocr_capturer.finished.connect(lambda: setattr(self, 'ocr_capturer', None))
        self.ocr_capturer.show()

    @Slot(QRect)
    def start_ocr_monitoring_on_region(self, rect: QRect):
        self.ocr_capture_rect = rect
        self.ocr_monitor_thread = QThread(self)
        self.screen_monitor = ScreenMonitor(rect, self.overlay_manager.get_stt_overlay_geometry)
        self.screen_monitor.moveToThread(self.ocr_monitor_thread)
        self.ocr_monitor_thread.started.connect(self.screen_monitor.start_monitoring)
        self.screen_monitor.image_changed.connect(lambda img: self.worker.process_ocr_image(img, self.ocr_capture_rect))
        self.screen_monitor.stopped.connect(self.ocr_monitor_thread.quit)
        self.ocr_monitor_thread.finished.connect(self.screen_monitor.deleteLater)
        self.ocr_monitor_thread.finished.connect(self.ocr_monitor_thread.deleteLater)
        self.ocr_monitor_thread.finished.connect(lambda: setattr(self, 'screen_monitor', None) or setattr(self, 'ocr_monitor_thread', None))
        self.ocr_monitor_thread.start()
        self.sound_player.play(self.config_manager.get("sound_ocr_start"))

    def stop_ocr_monitoring(self):
        if self.screen_monitor: self.screen_monitor.stop()
        if self.ocr_translation_action.isChecked(): self.sound_player.play(self.config_manager.get("sound_ocr_stop"))
        self.ocr_translation_action.setChecked(False)

    @Slot(str)
    def on_worker_error(self, message: str):
        QMessageBox.warning(None, "오류", message)
        if "STT" in message or "오디오" in message: self.stop_voice_translation()
        if "OCR" in message or "화면" in message: self.stop_ocr_monitoring()

    def quit_application(self):
        self.hotkey_manager.stop()
        if self.stt_processor_thread: self.stt_processor_thread.quit()
        if self.ocr_monitor_thread: self.ocr_monitor_thread.quit()
        if self.worker_thread: self.worker_thread.quit()
        
        self.tray_icon.hide()
        logger.info("모든 리소스 정리 및 종료 절차 시작.")
        self.app.quit()