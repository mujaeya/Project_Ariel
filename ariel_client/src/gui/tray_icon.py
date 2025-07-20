# ariel_client/src/gui/tray_icon.py (콜백 기반으로 안정화된 버전)

import logging
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
from ..core.audio_processor import AudioProcessor # 새로워진 AudioProcessor 임포트
from ..core.sound_player import SoundPlayer

logger = logging.getLogger(__name__)


class TrayIcon(QObject):
    # ... (기존 __init__, connect_base_signals, create_menu, open_setup_window, on_hotkey_pressed는 동일) ...
    """
    애플리케이션의 메인 컨트롤 타워.
    시스템 트레이 아이콘, 메뉴, 모든 백그라운드 스레드 및 UI 창을 관리합니다.
    """
    sound_request_queued = Signal(str)

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

        # 스레드 및 워커 객체 초기화
        self.audio_thread = None
        self.audio_processor = None
        self.setup_window = None
        self.ocr_capturer = None
        self.ocr_monitor_thread = None
        self.screen_monitor = None

        self.create_menu()
        self.tray_icon.setContextMenu(self.menu)
        self.connect_base_signals()
        
        self.tray_icon.show()
        self.worker_thread.start()
        self.hotkey_manager.start()
        self.sound_request_queued.emit("sound_app_start")

        if self.config_manager.get("is_first_run"):
            QTimer.singleShot(100, self.open_setup_window)

    def connect_base_signals(self):
        """앱의 생명주기 동안 유지되는 기본 시그널들을 연결합니다."""
        self.sound_request_queued.connect(self.sound_player.play)        
        # 워커 시그널 연결
        self.worker.stt_translation_ready.connect(self.overlay_manager.add_stt_translation)
        self.worker.ocr_patches_ready.connect(self.overlay_manager.show_ocr_patches)
        self.worker.error_occurred.connect(self.on_worker_error)        
        # [수정] 분리된 상태 시그널을 각자의 슬롯에 연결
        self.worker.stt_status_updated.connect(self.overlay_manager.add_system_message_to_stt)
        self.worker.ocr_status_updated.connect(self.overlay_manager.update_ocr_status)        
        self.worker_thread.finished.connect(self.worker.deleteLater)
        # 기타 관리자 시그널 연결
        self.hotkey_manager.hotkey_pressed.connect(self.on_hotkey_pressed)
        self.config_manager.settings_changed.connect(self.hotkey_manager.reload_hotkeys)
        self.config_manager.settings_changed.connect(self.sound_player.update_volume)

    def create_menu(self):
        """시스템 트레이 아이콘에 표시될 메뉴를 생성합니다."""
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
        """설정 창을 열거나, 이미 열려있으면 닫습니다."""
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

    # --- 음성 번역 토글 로직 (대폭 간소화) ---

    @Slot(bool)
    def toggle_voice_translation(self, checked: bool):
        # UI 비활성화로 중복 클릭 방지
        self.voice_translation_action.setEnabled(False) 
        if checked:
            self.start_voice_translation()
        else:
            self.stop_voice_translation()
        # [수정] 타이머를 더 짧게 설정해도 안정적임
        QTimer.singleShot(500, lambda: self.voice_translation_action.setEnabled(True))

    def start_voice_translation(self):
        if self.audio_thread is not None:
            logger.warning("오디오 스레드가 이미 실행 중입니다. 시작 요청을 무시합니다.")
            self.voice_translation_action.setChecked(False) # 상태 동기화
            return

        logger.info("음성 번역 서비스 시작 중...")
        self.audio_thread = QThread()
        self.audio_processor = AudioProcessor(self.config_manager)
        self.audio_processor.moveToThread(self.audio_thread)

        # 시그널 연결
        self.audio_processor.audio_processed.connect(self.worker.process_stt_audio)
        self.audio_processor.status_updated.connect(lambda msg: self.overlay_manager.add_system_message_to_stt(f"Audio: {msg}"))
        self.audio_processor.error_occurred.connect(self.on_worker_error)
        self.audio_processor.finished.connect(self.audio_thread.quit)
        self.audio_thread.started.connect(self.audio_processor.run)
        self.audio_thread.finished.connect(self.on_audio_thread_finished) # 정리 함수 연결

        self.audio_thread.start()
        
        self.sound_request_queued.emit("sound_stt_start")
        self.overlay_manager.show_stt_overlay()
        self.voice_translation_action.setText(self.tr("Stop Voice Translation"))
        logger.info("음성 번역 서비스 시작 완료.")

    def stop_voice_translation(self):
        logger.info("음성 번역 서비스 중지 중...")
        if self.audio_thread and self.audio_processor:
            # 1. 워커에게 루프 중단 요청 (가장 중요)
            self.audio_processor.stop()
            # 2. 이벤트 루프 종료 요청 (선택적이지만 권장)
            self.audio_thread.quit()
            # 3. [핵심] 스레드가 완전히 종료될 때까지 대기
            # 콜백 기반이므로 이제 wait()가 안정적으로 타임아웃 없이 성공합니다.
            if not self.audio_thread.wait(3000):
                logger.warning("오디오 스레드가 3초 내에 정상적으로 종료되지 않았습니다.")
            else:
                logger.info("오디오 스레드가 우아하게 종료되었습니다.")
        else:
            # 스레드가 없는 경우에도 UI 정리는 필요
            self.on_audio_thread_finished()

    @Slot()
    def on_audio_thread_finished(self):
        """스레드 종료 후 관련 객체를 안전하게 정리하는 최종 슬롯."""
        logger.debug("on_audio_thread_finished 슬롯 호출됨.")
        
        if self.audio_processor:
            self.audio_processor.deleteLater()
            self.audio_processor = None
            
        if self.audio_thread:
            # finished 시그널을 재연결할 필요가 없으므로 deleteLater만 호출
            self.audio_thread.deleteLater()
            self.audio_thread = None

        # UI 상태 업데이트
        self.sound_request_queued.emit("sound_stt_stop")
        self.overlay_manager.hide_stt_overlay()
        
        if self.voice_translation_action.isChecked():
            # 사용자가 Stop을 눌러서 종료된 게 아니라, 오류 등으로 종료된 경우 UI 동기화
            self.voice_translation_action.setChecked(False)
        self.voice_translation_action.setText(self.tr("Start Voice Translation"))
        
        logger.info("음성 번역 서비스 관련 리소스 및 UI가 모두 정리되었습니다.")


    # --- OCR 관련 로직 (기존과 거의 동일, 안정성 개선) ---
    
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
        
        # 만약을 위해 기존 스레드가 있다면 완전히 종료하고 새로 시작
        if self.ocr_monitor_thread and self.ocr_monitor_thread.isRunning():
            self.stop_ocr_monitoring()
            # 기존 스레드가 완전히 정리될 시간을 줌
            QTimer.singleShot(100, lambda: self._start_ocr_monitoring_after_stop(rect))
        else:
             self._start_ocr_monitoring_after_stop(rect)

    def _start_ocr_monitoring_after_stop(self, rect: QRect):
        if self.ocr_monitor_thread is not None:
            logger.warning("화면 감시 스레드가 아직 정리 중입니다. 시작 요청을 무시합니다.")
            self.ocr_translation_action.setChecked(False)
            return

        logger.info(f"화면 번역 서비스 시작 중... (영역: {rect})")
        self.ocr_monitor_thread = QThread()
        self.screen_monitor = ScreenMonitor(rect, self.overlay_manager.get_stt_overlay_geometry)
        self.screen_monitor.moveToThread(self.ocr_monitor_thread)

        # 시그널 연결
        self.screen_monitor.image_changed.connect(self.worker.process_ocr_image)
        self.screen_monitor.finished.connect(self.ocr_monitor_thread.quit)
        self.ocr_monitor_thread.started.connect(self.screen_monitor.start_monitoring)
        self.ocr_monitor_thread.finished.connect(lambda: self.on_ocr_thread_finished(play_sound=False))

        self.ocr_monitor_thread.start()
        self.sound_request_queued.emit("sound_ocr_start")
        self.ocr_translation_action.setText(self.tr("Stop Screen Translation"))
        logger.info("화면 번역 서비스 시작 완료.")

    def stop_ocr_monitoring(self, play_sound=True):
        logger.info("화면 번역 서비스 중지 중...")
        if self.ocr_monitor_thread and self.ocr_monitor_thread.isRunning():
            if self.screen_monitor: self.screen_monitor.stop()
            self.ocr_monitor_thread.quit()
            if not self.ocr_monitor_thread.wait(2000):
                logger.warning("화면 감시 스레드가 2초 내에 정상적으로 종료되지 않았습니다.")
            else:
                logger.info("화면 감시 스레드가 우아하게 종료되었습니다.")
        else:
            self.on_ocr_thread_finished(play_sound)

    @Slot(bool)
    def on_ocr_thread_finished(self, play_sound=True):
        logger.debug("on_ocr_thread_finished 슬롯 호출됨.")
        if self.screen_monitor:
            self.screen_monitor.deleteLater()
            self.screen_monitor = None
        if self.ocr_monitor_thread:
            self.ocr_monitor_thread.deleteLater()
            self.ocr_monitor_thread = None

        self.overlay_manager.hide_ocr_overlay()
        if play_sound: self.sound_request_queued.emit("sound_ocr_stop")
        if self.ocr_translation_action.isChecked():
            self.ocr_translation_action.setChecked(False)
        self.ocr_translation_action.setText(self.tr("Start Screen Translation"))
        logger.info("화면 번역 서비스 관련 리소스 및 UI가 모두 정리되었습니다.")

    # ... (on_worker_error, cleanup_threads, quit_application, tr 메서드는 기존과 동일) ...
    @Slot(str)
    def on_worker_error(self, message: str):
        QMessageBox.warning(None, self.tr("Error"), message)
        if "STT" in message or "Audio" in message: self.voice_translation_action.setChecked(False)
        if "OCR" in message or "Screen" in message: self.ocr_translation_action.setChecked(False)

    def cleanup_threads(self):
        """애플리케이션 종료 시 모든 스레드를 정리합니다."""
        logger.info("모든 백그라운드 스레드의 정리를 시작합니다...")
        
        # 각 서비스를 순차적으로 중지하고 종료될 때까지 기다립니다.
        if self.audio_thread and self.audio_thread.isRunning():
            logger.debug("음성 번역 서비스 정리 중...")
            self.stop_voice_translation()

        if self.ocr_monitor_thread and self.ocr_monitor_thread.isRunning():
            logger.debug("화면 번역 서비스 정리 중...")
            self.stop_ocr_monitoring(play_sound=False)
        
        if self.worker_thread and self.worker_thread.isRunning():
            logger.debug("메인 워커 스레드 정리 중...")
            self.worker_thread.quit()
            if not self.worker_thread.wait(1000):
                logger.warning("메인 워커 스레드가 정상적으로 종료되지 않았습니다.")

        logger.info("모든 스레드 정리가 완료되었습니다.")

    @Slot()
    def quit_application(self):
        """애플리케이션의 모든 리소스를 정리하고 안전하게 종료합니다."""
        logger.info("애플리케이션 종료 절차 시작...")
        self.tray_icon.hide()
        if self.setup_window:
            self.setup_window.close()
        
        self.hotkey_manager.stop()
        self.cleanup_threads()
        
        logger.info("모든 리소스 정리 완료. 애플리케이션을 종료합니다.")
        QApplication.instance().quit()
    
    def tr(self, text):
        return QCoreApplication.translate("TrayIcon", text)