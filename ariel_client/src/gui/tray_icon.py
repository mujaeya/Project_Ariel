import logging
from PySide6.QtWidgets import QSystemTrayIcon, QMenu, QMessageBox, QApplication
from PySide6.QtGui import QIcon, QAction
from PySide6.QtCore import Slot, QObject, QRect, QThread, QTimer, QCoreApplication, QLocale, QTranslator

from ..config_manager import ConfigManager
from .setup_window import SetupWindow
from .overlay_manager import OverlayManager
from .ocr_capturer import OcrCapturer
from ..core.screen_monitor import ScreenMonitor
from ..core.translation_worker import TranslationWorker
from ..core.hotkey_manager import HotkeyManager
from ..core.audio_processor import AudioProcessor
from ..core.sound_player import SoundPlayer
from ..utils import resource_path

logger = logging.getLogger(__name__)

def get_system_language():
    lang = QLocale.system().name().split('_')[0]
    supported_langs = {"en", "ko"}
    return lang if lang in supported_langs else "en"

class TrayIcon(QObject):
    def __init__(self, config_manager: ConfigManager, icon: QIcon, app: QApplication):
        super().__init__()
        self.app = app
        self.config_manager = config_manager
        
        self.apply_ui_language()

        self.sound_player = SoundPlayer(self.config_manager, self)
        self.tray_icon = QSystemTrayIcon(icon, self)
        self.tray_icon.setToolTip("Ariel by Seeth")

        self.worker_thread = QThread()
        self.worker = TranslationWorker(self.config_manager)
        self.worker.moveToThread(self.worker_thread)

        self.hotkey_manager = HotkeyManager(self.config_manager, self)
        self.overlay_manager = OverlayManager(config_manager, self)
        
        self.audio_thread, self.audio_processor = None, None
        self.setup_window, self.ocr_capturer = None, None
        self.ocr_monitor_thread, self.screen_monitor = None, None

        self.create_menu()
        self.tray_icon.setContextMenu(self.menu)
        self.connect_signals()

        self.tray_icon.show()
        self.worker_thread.start()
        self.hotkey_manager.start()
        self.sound_player.play("sound_app_start")

        logger.info("트레이 아이콘 및 핵심 컴포넌트 준비 완료.")
        if self.config_manager.get("is_first_run"):
            logger.warning("첫 실행으로 감지되어 설정 창을 먼저 실행합니다.")
            QTimer.singleShot(100, self.open_setup_window)

    def apply_ui_language(self):
        app_lang_code = self.config_manager.get("app_language", "auto")
        if app_lang_code == "auto":
            app_lang_code = get_system_language()

        self.translator = QTranslator(self.app)
        translation_path = resource_path(f'translations/ariel_{app_lang_code}.qm')
        
        if self.translator.load(translation_path):
            self.app.installTranslator(self.translator)
            logger.info(f"UI 언어 '{app_lang_code}'를 적용했습니다.")
        elif app_lang_code != 'en':
            logger.warning(f"번역 파일({translation_path}) 로드 실패. 영어로 대체합니다.")
            if self.translator.load(resource_path('translations/ariel_en.qm')):
                self.app.installTranslator(self.translator)

    def connect_signals(self):
        self.worker.stt_translation_ready.connect(self.overlay_manager.add_stt_translation)
        self.worker.ocr_patches_ready.connect(self.overlay_manager.show_ocr_patches)
        self.worker.error_occurred.connect(self.on_worker_error)
        self.worker.status_updated.connect(self.overlay_manager.add_system_message_to_stt)
        
        self.worker_thread.finished.connect(self.worker.deleteLater)
        self.worker_thread.finished.connect(self.worker_thread.deleteLater)
        
        self.hotkey_manager.hotkey_pressed.connect(self.on_hotkey_pressed)
        
        self.config_manager.settings_changed.connect(self.hotkey_manager.reload_hotkeys)
        self.config_manager.settings_changed.connect(self.sound_player.update_volume)
    
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

    def open_setup_window(self):
        if not self.setup_window or not self.setup_window.isVisible():
            self.setup_window = SetupWindow(self.config_manager)
            self.setup_window.show()
        self.setup_window.activateWindow()

    @Slot(str)
    def on_hotkey_pressed(self, action_name: str):
        logger.debug(f"단축키 '{action_name}' 감지")
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
        logger.info(f"음성 번역 토글: {'시작' if checked else '중지'}")
        if checked:
            self.start_voice_translation()
        else:
            self.stop_voice_translation()

    def start_voice_translation(self):
        if self.audio_thread and self.audio_thread.isRunning():
            logger.warning("음성 번역 스레드가 이미 실행 중입니다.")
            return

        logger.info("음성 번역 서비스 시작...")
        self.audio_thread = QThread()
        
        # ❗️ 핵심 수정: AudioProcessor 생성 시 parent=None을 다시 한번 확인합니다.
        self.audio_processor = AudioProcessor(self.config_manager, parent=None)
        
        # ❗️❗️ 디버깅 강화: moveToThread 전에 부모가 없는지 확인하는 방어 코드 추가
        if self.audio_processor.parent() is not None:
            logger.critical("치명적 오류: AudioProcessor가 부모를 가진 상태에서 스레드로 이동하려고 합니다! 부모 객체: %s", self.audio_processor.parent())
            # 여기서 실행을 중단하여 더 큰 문제를 방지할 수 있습니다.
            # 예를 들어, return self.on_audio_thread_finished() 와 같이 정리 함수를 호출하고 빠져나갑니다.
            self.audio_processor = None
            self.audio_thread = None
            return

        self.audio_processor.moveToThread(self.audio_thread)
        
        # 올바른 신호-슬롯 연결
        self.audio_processor.audio_chunk_ready.connect(self.worker.process_stt_audio)
        self.audio_processor.status_updated.connect(lambda msg: self.overlay_manager.add_system_message_to_stt(f"Audio: {msg}"))
        self.audio_processor.finished.connect(self.audio_thread.quit)
        self.audio_thread.finished.connect(self.on_audio_thread_finished)
        self.audio_thread.started.connect(self.audio_processor.run)
        
        self.audio_thread.start()
        
        self.sound_player.play("sound_stt_start")
        self.overlay_manager.show_stt_overlay()
        self.voice_translation_action.setText(self.tr("Stop Voice Translation"))

    def stop_voice_translation(self):
        logger.info("음성 번역 서비스 중지 요청...")
        if self.audio_processor:
            # 워커에게만 정중히 중지를 요청합니다. 나머지는 신호-슬롯 연쇄 반응으로 자동 처리됩니다.
            self.audio_processor.stop()
        else:
            # 정리할 프로세서가 없는 경우에도 UI와 상태를 확실히 정리합니다.
            self.on_audio_thread_finished()
            
    @Slot()
    def on_audio_thread_finished(self):
        """QThread.finished 시그널에 연결된 최종 정리 슬롯. 가장 안전한 호출 시점입니다."""
        logger.debug("AudioThread가 완전히 종료됨. 리소스 정리 시작.")
        
        # deleteLater()를 통해 안전하게 메모리에서 해제
        if self.audio_processor:
            self.audio_processor.deleteLater()
            self.audio_processor = None
        if self.audio_thread:
            self.audio_thread.deleteLater()
            self.audio_thread = None
        
        # 모든 정리가 끝난 후 UI 업데이트
        self.sound_player.play("sound_stt_stop")
        self.overlay_manager.hide_stt_overlay()
        if self.voice_translation_action.isChecked():
            self.voice_translation_action.setChecked(False)
        self.voice_translation_action.setText(self.tr("Start Voice Translation"))
        logger.info("음성 번역 서비스가 완전히 정리되었습니다.")

    @Slot(bool)
    def toggle_ocr_translation(self, checked: bool):
        logger.info(f"화면 번역 토글: {'시작' if checked else '중지'}")
        if checked:
            self.select_ocr_region()
        else:
            self.stop_ocr_monitoring()

    def select_ocr_region(self):
        if self.ocr_capturer and self.ocr_capturer.isVisible(): return
        
        logger.debug("OCR 영역 선택기 표시")
        self.ocr_capturer = OcrCapturer()
        self.ocr_capturer.region_selected.connect(self.start_ocr_monitoring_on_region)
        self.ocr_capturer.cancelled.connect(lambda: self.ocr_translation_action.setChecked(False))
        self.ocr_capturer.show()

    @Slot(QRect)
    def start_ocr_monitoring_on_region(self, rect: QRect):
        if rect.isNull():
            logger.warning("OCR 영역 선택이 취소되었거나 유효하지 않습니다.")
            self.ocr_translation_action.setChecked(False)
            return
        
        self.stop_ocr_monitoring(play_sound=False)
        logger.info(f"새 OCR 영역({rect})에 대한 모니터링 시작.")

        self.ocr_monitor_thread = QThread()
        self.screen_monitor = ScreenMonitor(rect, self.overlay_manager.get_stt_overlay_geometry)
        self.screen_monitor.moveToThread(self.ocr_monitor_thread)
        
        # ⭐️ OCR도 음성 번역과 동일한 안전한 패턴으로 수정
        self.screen_monitor.image_changed.connect(self.worker.process_ocr_image)
        # ScreenMonitor의 신호 이름을 진단 내용에 맞춰 'finished'로 통일 (또는 'stopped'를 그대로 사용해도 무방)
        self.screen_monitor.finished.connect(self.ocr_monitor_thread.quit) # 워커가 끝나면 스레드 종료
        
        # ❗️❗️ 스레드가 진짜로 종료되었을 때만 정리 함수 호출
        self.ocr_monitor_thread.finished.connect(self.on_ocr_thread_finished)
        
        self.ocr_monitor_thread.started.connect(self.screen_monitor.start_monitoring)
        self.ocr_monitor_thread.start()
        
        self.sound_player.play("sound_ocr_start")
        self.ocr_translation_action.setText(self.tr("Stop Screen Translation"))

    def stop_ocr_monitoring(self, play_sound=True):
        logger.info("화면 번역 서비스 중지 요청...")
        if self.screen_monitor:
            self.screen_monitor.stop()
        else:
            self.on_ocr_thread_finished(play_sound=play_sound)

    @Slot()
    def on_ocr_thread_finished(self, play_sound=True):
        """QThread.finished 시그널에 연결된 OCR 최종 정리 슬롯."""
        logger.debug("OCR Monitor Thread가 완전히 종료됨. 리소스 정리 시작.")
        if self.screen_monitor:
            self.screen_monitor.deleteLater()
            self.screen_monitor = None
        if self.ocr_monitor_thread:
            self.ocr_monitor_thread.deleteLater()
            self.ocr_monitor_thread = None

        self.overlay_manager.hide_ocr_overlay()
        if play_sound: self.sound_player.play("sound_ocr_stop")
        
        if self.ocr_translation_action.isChecked():
            self.ocr_translation_action.setChecked(False)
        self.ocr_translation_action.setText(self.tr("Start Screen Translation"))
        logger.info("화면 번역 서비스가 완전히 정리되었습니다.")

    @Slot(str)
    def on_worker_error(self, message: str):
        logger.error(f"Worker로부터 오류 수신: {message}")
        QMessageBox.warning(None, self.tr("Error"), message)
        if "STT" in message or "Audio" in message:
            if self.voice_translation_action.isChecked(): self.voice_translation_action.setChecked(False)
        if "OCR" in message or "Screen" in message:
            if self.ocr_translation_action.isChecked(): self.ocr_translation_action.setChecked(False)

    def quit_application(self):
        logger.info("애플리케이션 종료 절차 시작...")
        self.hotkey_manager.stop()
        # 종료 시에도 안전한 stop 메소드 호출
        if self.voice_translation_action.isChecked(): self.stop_voice_translation()
        if self.ocr_translation_action.isChecked(): self.stop_ocr_monitoring()
        QTimer.singleShot(500, self._quit_threads_and_app)

    def _quit_threads_and_app(self):
        logger.info("백그라운드 스레드를 종료하고 앱을 나갑니다.")
        if self.worker_thread and self.worker_thread.isRunning():
            self.worker_thread.quit()
            self.worker_thread.wait(1000)
        self.tray_icon.hide()
        QApplication.instance().quit()

    def tr(self, text):
        return QCoreApplication.translate("TrayIcon", text)