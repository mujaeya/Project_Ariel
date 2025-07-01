# src/worker.py (OCR 입력 추가 버전)
import logging
from PySide6.QtCore import QObject, Signal, Slot, QThread, QTimer
import queue
from collections import deque

from config_manager import ConfigManager
from audio_capturer import AudioCapturer
from stt_engine import STTEngine
from mt_engine import MTEngine

logger = logging.getLogger(__name__)

MAX_BUFFER_SIZE = 3

class Worker(QObject):
    """
    STT(음성)와 OCR(이미지) 두 가지 소스로부터 텍스트를 받아 번역합니다.
    """
    translation_ready = Signal(str, dict)
    status_update = Signal(str)
    error_occurred = Signal(str)

    def __init__(self, config_manager: ConfigManager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self._is_running = False

        self.sentence_buffer = []
        self.commit_timer = QTimer(self)
        self.commit_timer.setSingleShot(True)
        self.commit_timer.timeout.connect(self.commit_stt_translation)

        self.context_history = deque(maxlen=3)

        self.audio_thread = None
        self.audio_capturer = None
        self.stt_thread = None
        self.stt_engine = None
        self.mt_engine = None
        self.audio_queue = queue.Queue()

    # <<<<<<< 핵심 수정: 번역 로직을 별도 함수로 분리 >>>>>>>>>
    def translate_text(self, text_to_translate):
        """주어진 텍스트를 현재 설정으로 번역하고 결과를 시그널로 보냅니다."""
        if not text_to_translate:
            return

        logger.info(f"번역 요청 텍스트: '{text_to_translate}'")
        self.status_update.emit("번역 중...")

        context_text = "\n".join(self.context_history)
        target_languages = self.config_manager.get("target_languages", [])
        
        if not target_languages:
            logger.warning("번역 대상 언어가 설정되지 않아 번역을 건너뜁니다.")
            self.status_update.emit("오류: 번역할 언어가 선택되지 않음")
            return
        
        api_results = self.mt_engine.translate_text_multi(
            text_to_translate,
            target_langs=target_languages,
            context=context_text,
            formality="default"
        )

        self.translation_ready.emit(text_to_translate, api_results)
        self.context_history.append(text_to_translate)
        self.status_update.emit("번역 대기 중...")


    @Slot()
    def start_processing(self):
        # ... (이전과 동일)
        if self._is_running: return
        logger.info("[Worker] 모든 처리 스레드를 시작합니다.")
        self._is_running = True
        self.status_update.emit("초기화 중...")
        self.context_history.clear()
        self.sentence_buffer.clear()
        
        delay = self.config_manager.get("sentence_commit_delay_ms", 700)
        self.commit_timer.setInterval(delay)

        try:
            self.mt_engine = MTEngine(self.config_manager)
            self.audio_capturer = AudioCapturer(self.audio_queue)
            
            self.audio_thread = QThread()
            self.audio_capturer.moveToThread(self.audio_thread)
            self.audio_capturer.error_occurred.connect(self.error_occurred)
            self.audio_thread.started.connect(self.audio_capturer.start_capturing)
            self.audio_thread.start()

            self.stt_engine = STTEngine(self.config_manager, self.audio_queue)
            self.stt_thread = QThread()
            self.stt_engine.moveToThread(self.stt_thread)
            self.stt_engine.transcript_updated.connect(self.on_stt_transcript_updated)
            self.stt_engine.error_occurred.connect(self.error_occurred)
            self.stt_thread.started.connect(self.stt_engine.start_transcription)
            self.stt_thread.start()
            
            self.status_update.emit("번역 대기 중...")
            logger.info("[Worker] 모든 스레드가 성공적으로 시작되었습니다.")

        except Exception as e:
            error_msg = f"작업자 초기화 실패: {e}"
            logger.error(error_msg, exc_info=True)
            self.error_occurred.emit(error_msg)


    @Slot()
    def stop_processing(self):
        # ... (이전과 동일)
        if not self._is_running: return
        logger.info("[Worker] 모든 처리 스레드를 중지합니다.")
        self._is_running = False
        self.commit_timer.stop()
        if self.stt_engine: self.stt_engine.stop_transcription()
        if self.stt_thread: self.stt_thread.quit(); self.stt_thread.wait(2000)
        if self.audio_capturer: self.audio_capturer.stop_capturing()
        if self.audio_thread: self.audio_thread.quit(); self.audio_thread.wait(2000)
        logger.info("[Worker] 모든 스레드가 안전하게 종료되었습니다.")


    @Slot(str, bool)
    def on_stt_transcript_updated(self, transcript, is_final):
        if not self._is_running: return
        if is_final and transcript.strip():
            self.sentence_buffer.append(transcript.strip())
            if len(self.sentence_buffer) >= MAX_BUFFER_SIZE:
                self.commit_timer.stop()
                self.commit_stt_translation()
            else:
                self.commit_timer.start()
                self.status_update.emit("문장 조합 중...")

    @Slot()
    def commit_stt_translation(self):
        """STT(음성)로부터 수집된 문장을 번역합니다."""
        if not self.sentence_buffer: return
        full_sentence = " ".join(self.sentence_buffer)
        self.sentence_buffer.clear()
        self.translate_text(full_sentence)

    # <<<<<<< 핵심 수정: OCR 텍스트를 처리할 새로운 슬롯 >>>>>>>>>
    @Slot(str)
    def on_ocr_text_captured(self, ocr_text):
        """OCR(이미지)로부터 추출된 텍스트를 번역합니다."""
        if not self._is_running:
            # 번역기가 꺼져있으면, 먼저 켜고 번역
            print("OCR 요청: 번역기가 꺼져있어 먼저 활성화합니다.")
            # TrayIcon의 start_translation을 간접적으로 호출하는 효과
            self.parent().start_translation()
            QTimer.singleShot(500, lambda: self.translate_text(ocr_text)) # 0.5초 후 번역 실행
        else:
            self.translate_text(ocr_text)