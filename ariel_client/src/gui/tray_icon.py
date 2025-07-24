# ariel_client/src/gui/tray_icon.py (이 코드로 전체 교체)

import logging
import queue
import time # [핵심 수정] time 모듈 임포트 추가

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
        self._last_error_time = 0 # [수정] _last_error_time 초기화

        self.sound_player = SoundPlayer(self.config_manager, self)
        self.tray_icon = QSystemTrayIcon(icon, self)
        self.tray_icon.setToolTip("Ariel by Seeth")

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
        self.threads.append(self.worker_thread) # [추가] 메인 워커 스레드도 관리 목록에 포함
        
        self.hotkey_manager.start()
        self.sound_request_queued.emit("sound_app_start")

        if self.config_manager.get("is_first_run"):
            QTimer.singleShot(100, self.open_setup_window)

# ariel_client/src/gui/tray_icon.py

    def connect_base_signals(self):
        self.sound_request_queued.connect(self.sound_player.play)
        
        # [핵심 수정] 새로운 시그널 이름으로 변경하고, 새로운 슬롯에 연결합니다.
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
        # [핵심 수정] TranslationWorker에 STT 활성화/비활성화 상태를 전달합니다.
        self.worker.set_stt_enabled(checked)

        # UI가 즉시 비활성화되어 사용자의 중복 클릭을 방지합니다.
        self.voice_translation_action.setEnabled(False) 
        
        if checked:
            # [핵심 수정] 시작하기 전에 언어 설정을 전달합니다.
            lang = self.config_manager.get("stt_source_language", "auto")
            self.worker.set_stt_language(lang)
            self.start_voice_translation()
        else:
            self.stop_voice_translation()
        
        # 1초 후에 버튼을 다시 활성화합니다.
        QTimer.singleShot(1000, lambda: self.voice_translation_action.setEnabled(True))

# ariel_client/src/gui/tray_icon.py

    def start_voice_translation(self):
        if self.capturer_thread or self.processor_thread:
            logger.warning("오디오 스레드가 이미 실행 중입니다. 시작 요청을 무시합니다.")
            if not self.voice_translation_action.isChecked():
                self.voice_translation_action.setChecked(True)
            return

        logger.info("음성 번역 서비스 시작 중 (실시간 처리 아키텍처)...")
        
        self.processor_thread = QThread()
        self.threads.append(self.processor_thread)
        self.audio_processor = AudioProcessor(self.config_manager, self.audio_queue)
        self.audio_processor.moveToThread(self.processor_thread)

        # [핵심 수정] 새로운 시그널 이름으로 변경하고, 새로운 슬롯에 연결합니다.
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
        self.voice_translation_action.setText(self.tr("Stop Voice Translation"))
        logger.info("음성 번역 서비스 시작 완료.")

    def stop_voice_translation(self):
        logger.info("음성 번역 서비스 중지 중...")
        if self.audio_capturer:
            self.audio_capturer.stop_capturing()
        if self.audio_processor:
            self.audio_processor.stop()

    @Slot()
    def on_audio_threads_finished(self):
        logger.debug("on_audio_threads_finished 슬롯 호출됨.")
        
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
        self.voice_translation_action.setText(self.tr("Start Voice Translation"))
        
        logger.info("음성 번역 서비스 관련 모든 리소스가 정리되었습니다.")

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
            logger.warning("화면 감시 스레드가 아직 정리 중입니다. 시작 요청을 무시합니다.")
            self.ocr_translation_action.setChecked(False)
            return

        logger.info(f"화면 번역 서비스 시작 중... (영역: {rect})")
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
        self.ocr_translation_action.setText(self.tr("Stop Screen Translation"))
        logger.info("화면 번역 서비스 시작 완료.")

    def stop_ocr_monitoring(self, play_sound=True):
        logger.info("화면 번역 서비스 중지 중...")
        if self.screen_monitor:
            self.screen_monitor.stop()

    @Slot(bool)
    def on_ocr_thread_finished(self, play_sound=True):
        logger.debug("on_ocr_thread_finished 슬롯 호출됨.")
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
        self.ocr_translation_action.setText(self.tr("Start Screen Translation"))
        logger.info("화면 번역 서비스 관련 리소스 및 UI가 모두 정리되었습니다.")

    @Slot(str)
    def on_worker_error(self, message: str):
        if time.time() - self._last_error_time < 5:
            return
        self._last_error_time = time.time()

        QMessageBox.warning(None, self.tr("Error"), message)
        if "STT" in message or "Audio" in message or "VAD" in message: 
            if self.voice_translation_action.isChecked():
                self.voice_translation_action.toggle()
        if "OCR" in message or "Screen" in message: 
            if self.ocr_translation_action.isChecked():
                self.ocr_translation_action.toggle()

    def cleanup_threads(self):
        logger.info("모든 백그라운드 스레드의 정리를 시작합니다...")
        
        # 모든 워커에 종료 신호 보내기
        self.stop_voice_translation()
        self.stop_ocr_monitoring(play_sound=False)
        
        # 메인 워커 스레드 종료
        if self.worker_thread:
            self.worker_thread.quit()

        # 스레드 복사본을 만들어 순회 (리스트에서 제거되므로)
        for thread in list(self.threads):
            if thread and thread.isRunning():
                logger.info(f"스레드 종료 대기중...")
                if not thread.wait(3000):
                    logger.warning(f"스레드가 3초 내에 정상적으로 종료되지 않았습니다. 강제 종료를 시도합니다.")
                    thread.terminate()

        logger.info("모든 스레드 정리가 완료되었습니다.")

    @Slot()
    def quit_application(self):
        logger.info("애플리케이션 종료 절차 시작...")
        self.tray_icon.hide()
        if self.setup_window:
            self.setup_window.close()
        
        self.hotkey_manager.stop()
        self.cleanup_threads()
        
        logger.info("모든 리소스 정리 완료. 애플리케이션을 종료합니다.")
        QTimer.singleShot(100, QApplication.instance().quit)
    
    def tr(self, text):
        return QCoreApplication.translate("TrayIcon", text)