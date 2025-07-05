# F:/projects/Project_Ariel/ariel_client/src/gui/tray_icon.py

import sys
import logging
logging.getLogger(__name__).info(f"--- [모듈 로딩] {__name__} 파일이 로드됩니다. ---")
from PySide6.QtWidgets import QSystemTrayIcon, QMenu, QMessageBox, QApplication
from PySide6.QtGui import QIcon, QAction
from PySide6.QtCore import Slot, QObject, QRect, QThread

# --- 프로젝트 내부 모듈 임포트 ---
from ..utils import resource_path
from ..config_manager import ConfigManager
from .setup_window import SetupWindow
from .overlay_manager import OverlayManager
from .ocr_capturer import OcrCapturer
from ..core.screen_monitor import ScreenMonitor
from ..core.translation_worker import TranslationWorker
from ..core.hotkey_manager import HotkeyManager
from ..core.audio_processor import AudioProcessor # 우리가 수정한 새 AudioProcessor
from ..core.sound_player import SoundPlayer

logger = logging.getLogger(__name__)

class TrayIcon(QObject):
    """
    애플리케이션의 모든 핵심 컴포넌트를 생성하고 관리하는 메인 컨트롤러.
    사용자 입력(단축키, 메뉴 클릭)을 받아 각 기능을 시작/중지하고,
    컴포넌트 간의 데이터 흐름(시그널/슬롯)을 조율합니다.
    """
    def __init__(self, config_manager: ConfigManager, icon_path: str, app: QApplication):
        super().__init__()
        self.app = app
        self.config_manager = config_manager
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(QIcon(icon_path))
        self.tray_icon.setToolTip("Ariel by Seeth")

        # --- 핵심 컴포넌트 초기화 ---
        self.worker_thread = QThread(self)
        self.worker = TranslationWorker(self.config_manager)
        self.worker.moveToThread(self.worker_thread)

        self.hotkey_manager = HotkeyManager(self.config_manager, self)
        self.overlay_manager = OverlayManager(self.config_manager, self)
        self.sound_player = SoundPlayer(self)

        # 윈도우 및 기능별 스레드/객체는 필요할 때 생성되므로 None으로 초기화
        self.setup_window = None
        self.ocr_capturer = None
        self.ocr_monitor_thread, self.screen_monitor = None, None
        self.stt_processor_thread, self.audio_processor = None, None

        self.create_menu()
        self.tray_icon.setContextMenu(self.menu)
        
        # --- 시그널 연결 ---
        self.hotkey_manager.hotkey_pressed.connect(self.on_hotkey_pressed)
        self.worker.translation_ready.connect(self.on_translation_ready)
        self.worker.error_occurred.connect(self.on_worker_error)
        
        # --- 시작 ---
        self.worker_thread.start()
        self.tray_icon.show()
        logger.info("트레이 아이콘 및 핵심 컴포넌트 준비 완료.")

        # 시작음 재생
        volume = self.config_manager.get("sound_master_volume", 80) / 100.0
        self.sound_player.play(self.config_manager.get("sound_app_start"), volume)
        
        # 최초 실행 시 설정 창 자동 열기
        if self.config_manager.get("is_first_run", True):
            logger.info("최초 실행을 감지했습니다. 설정 창을 자동으로 엽니다.")
            self.open_setup_window()
            self.config_manager.set("is_first_run", False)

    def create_menu(self):
        """트레이 아이콘의 컨텍스트 메뉴를 생성합니다."""
        self.menu = QMenu()
        self.voice_translation_action = self.menu.addAction("음성 번역 시작/중지")
        self.voice_translation_action.setCheckable(True)

        self.ocr_translation_action = self.menu.addAction("화면 번역 시작/중지")
        self.ocr_translation_action.setCheckable(True)

        self.menu.addSeparator()
        self.setup_action = self.menu.addAction("설정...")
        self.quit_action = self.menu.addAction("종료")

        # 메뉴 액션에 대한 시그널 연결
        self.voice_translation_action.toggled.connect(self.toggle_voice_translation)
        self.ocr_translation_action.toggled.connect(self.toggle_ocr_translation)
        self.setup_action.triggered.connect(self.open_setup_window)
        self.quit_action.triggered.connect(self.quit_application)

    @Slot(str, dict, str, QRect)
    def on_translation_ready(self, original: str, results: dict, source: str, geometry: QRect = None):
        """TranslationWorker로부터 번역 결과를 받아 처리하는 중앙 슬롯."""
        volume = self.config_manager.get("sound_master_volume", 80) / 100.0
        if source == 'stt':
            self.overlay_manager.add_translation(original, results, source)
            self.sound_player.play(self.config_manager.get("sound_stt_result"), volume)
        elif source == 'ocr' and geometry:
            self.overlay_manager.show_ocr_translation_at(original, results, geometry)
            self.sound_player.play(self.config_manager.get("sound_ocr_result"), volume)

    @Slot(str)
    def on_hotkey_pressed(self, action_name: str):
        """HotkeyManager로부터 받은 단축키 액션을 처리합니다."""
        logger.info(f"단축키 액션 '{action_name}' 수신")
        if action_name == "toggle_stt": self.voice_translation_action.toggle()
        elif action_name == "toggle_ocr": self.ocr_translation_action.toggle()
        elif action_name == "toggle_setup": self.toggle_setup_window()
        elif action_name == "quit_app": self.quit_application()

    # --- 음성 번역 (STT) 로직 ---

    @Slot(bool)
    def toggle_voice_translation(self, checked: bool):
        if checked:
            self.start_voice_translation()
        else:
            self.stop_voice_translation()

    def start_voice_translation(self):
        if self.stt_processor_thread and self.stt_processor_thread.isRunning():
            logger.warning("음성 번역이 이미 실행 중입니다. 중복 실행을 방지합니다.")
            return

        self.stop_voice_translation()

        self.stt_processor_thread = QThread(self)
        self.audio_processor = AudioProcessor(self.config_manager)
        self.audio_processor.moveToThread(self.stt_processor_thread)

        # 시그널 연결 (기존 코드와 거의 동일하나, 안정성을 위해 순서를 명확히 함)
        self.stt_processor_thread.started.connect(self.audio_processor.start_processing)
        self.audio_processor.audio_chunk_ready.connect(self.worker.process_stt_audio)
        self.audio_processor.status_updated.connect(self.overlay_manager.add_system_message_to_stt) # add_system_message_to_stt가 OverlayManager에 구현되어 있다고 가정
        
        # [수정] 스레드 종료 로직을 더 명확하게 변경
        self.audio_processor.finished.connect(self.stt_processor_thread.quit) # 프로세서가 끝나면 스레드를 종료
        self.stt_processor_thread.finished.connect(self.audio_processor.deleteLater)
        self.stt_processor_thread.finished.connect(self.stt_processor_thread.deleteLater)

        self.stt_processor_thread.start()
        # self.overlay_manager.add_system_message_to_stt("음성 번역 시작") # AudioProcessor가 시작 후 직접 메시지를 보냄

        volume = self.config_manager.get("sound_master_volume", 80) / 100.0
        self.sound_player.play(self.config_manager.get("sound_stt_start"), volume)
        self.voice_translation_action.setChecked(True)

    def stop_voice_translation(self):
        if not self.stt_processor_thread:
            return

        was_running = self.voice_translation_action.isChecked()
        
        if self.audio_processor:
            # [수정] stop()을 직접 호출하여 정리 프로세스를 시작시킵니다.
            # stop() 메서드는 내부적으로 finished 시그널을 보내 스레드를 종료시킵니다.
            self.audio_processor.stop()

        # wait()를 사용해 스레드가 완전히 종료될 때까지 대기
        if self.stt_processor_thread.isRunning():
            self.stt_processor_thread.wait(500) 
        
        self.audio_processor = None
        self.stt_processor_thread = None

        if was_running:
            self.overlay_manager.hide_stt_overlay()
            self.voice_translation_action.setChecked(False)
            volume = self.config_manager.get("sound_master_volume", 80) / 100.0
            self.sound_player.play(self.config_manager.get("sound_stt_stop"), volume)
    
    # --- 화면 번역 (OCR) 로직 ---

    @Slot(bool)
    def toggle_ocr_translation(self, checked: bool):
        if checked:
            self.stop_ocr_monitoring() # 기존 모니터링 중지
            self.ocr_capturer = OcrCapturer()
            self.ocr_capturer.region_selected.connect(self.start_ocr_monitoring_on_region)
            self.ocr_capturer.cancelled.connect(lambda: self.ocr_translation_action.setChecked(False))
            self.ocr_capturer.finished.connect(self.on_ocr_capturer_finished)
            self.ocr_capturer.show()
        else:
            self.stop_ocr_monitoring()

    @Slot(QRect)
    def start_ocr_monitoring_on_region(self, selected_rect: QRect):
        self.ocr_monitor_thread = QThread(self)
        # STT 오버레이 창은 OCR 영역에서 제외
        self.screen_monitor = ScreenMonitor(rect=selected_rect, ignored_rect_func=self.overlay_manager.get_stt_overlay_geometry)
        self.screen_monitor.moveToThread(self.ocr_monitor_thread)

        self.ocr_monitor_thread.started.connect(self.screen_monitor.start_monitoring)
        # 이미지 변경 시 -> 이미지와 좌표를 TranslationWorker로 전송
        self.screen_monitor.image_changed.connect(self.worker.process_ocr_image)
        self.screen_monitor.stopped.connect(self.ocr_monitor_thread.quit)
        self.ocr_monitor_thread.finished.connect(self.screen_monitor.deleteLater)
        self.ocr_monitor_thread.finished.connect(self.ocr_monitor_thread.deleteLater)
        
        self.ocr_monitor_thread.start()
        self.overlay_manager.show_ocr_translation_at("화면 번역 시작", {"SYSTEM": "화면 변화 감시 중..."}, selected_rect)
        volume = self.config_manager.get("sound_master_volume", 80) / 100.0
        self.sound_player.play(self.config_manager.get("sound_ocr_start"), volume)
        self.ocr_translation_action.setChecked(True)

    def stop_ocr_monitoring(self):
        if not self.ocr_monitor_thread:
            return

        was_running = self.ocr_translation_action.isChecked()
        if self.screen_monitor: self.screen_monitor.stop()
        
        self.ocr_monitor_thread.wait(500)
        self.screen_monitor = None
        self.ocr_monitor_thread = None

        if was_running:
            self.overlay_manager.hide_ocr_overlay()
            self.ocr_translation_action.setChecked(False)
            volume = self.config_manager.get("sound_master_volume", 80) / 100.0
            self.sound_player.play(self.config_manager.get("sound_ocr_stop"), volume)

    @Slot()
    def on_ocr_capturer_finished(self):
        """OCR 캡처 창이 닫힐 때 호출됩니다."""
        self.ocr_capturer = None

    # --- 공통 및 유틸리티 메서드 ---

    @Slot(str)
    def on_worker_error(self, message: str):
        QMessageBox.critical(None, "작업 오류", message)
        if self.voice_translation_action.isChecked(): self.stop_voice_translation()
        if self.ocr_translation_action.isChecked(): self.stop_ocr_monitoring()

    def open_setup_window(self):
        if not self.setup_window or not self.setup_window.isVisible():
            self.setup_window = SetupWindow(self.config_manager)
            self.setup_window.closed.connect(self.on_setup_window_closed)
            self.setup_window.show()
        self.setup_window.activateWindow()
        self.setup_window.raise_()

    @Slot()
    def on_setup_window_closed(self):
        logger.info("설정 창이 닫혔습니다. 단축키를 다시 로드합니다.")
        self.hotkey_manager.reload_hotkeys()
        self.setup_window = None

    def toggle_setup_window(self):
        if not self.setup_window or not self.setup_window.isVisible():
            self.open_setup_window()
        else:
            self.setup_window.close()

    def quit_application(self):
        logger.info("애플리케이션 종료 절차 시작...")
        self.stop_ocr_monitoring()
        self.stop_voice_translation()
        if self.hotkey_manager: self.hotkey_manager.stop()
        self.worker_thread.quit()
        self.worker_thread.wait(500)
        logger.info("모든 리소스 정리 완료. 애플리케이션을 종료합니다.")
        self.app.quit()