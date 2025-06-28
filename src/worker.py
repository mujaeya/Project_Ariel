# src/worker.py (이 코드로 전체를 교체해주세요)
import logging
from PySide6.QtCore import QObject, Signal, Slot, QThread, QTimer
import queue
from collections import deque

from config_manager import ConfigManager
from audio_capturer import AudioCapturer
from stt_engine import STTEngine
from mt_engine import MTEngine

logger = logging.getLogger(__name__)

# 중간 번역을 위한 설정값 추가
MAX_BUFFER_SIZE = 3 # 문장 조각이 3개 이상 쌓이면 중간 번역 실행

class Worker(QObject):
    """
    메인 GUI 스레드에서 실행되며, 실제 작업 스레드들을 총괄 지휘하는 컨트롤 타워.
    긴 문장 번역 지연 문제를 해결하는 로직이 포함되었습니다.
    """
    translation_ready = Signal(str, str)
    status_update = Signal(str)
    error_occurred = Signal(str)

    def __init__(self, config_manager: ConfigManager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self._is_running = False

        self.sentence_buffer = []
        self.commit_timer = QTimer(self)
        self.commit_timer.setSingleShot(True)
        self.commit_timer.timeout.connect(self.commit_translation)

        self.context_history = deque(maxlen=3)

        self.audio_thread = None
        self.audio_capturer = None
        self.stt_thread = None
        self.stt_engine = None
        self.mt_engine = None
        self.audio_queue = queue.Queue()

    @Slot()
    def start_processing(self):
        """모든 번역 관련 스레드를 시작합니다."""
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
            self.stt_engine.transcript_updated.connect(self.on_transcript_updated)
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
        """모든 번역 관련 스레드를 안전하게 중지합니다."""
        if not self._is_running: return
            
        logger.info("[Worker] 모든 처리 스레드를 중지합니다.")
        self._is_running = False
        self.commit_timer.stop()

        if self.stt_engine: self.stt_engine.stop_transcription()
        if self.stt_thread and self.stt_thread.isRunning(): self.stt_thread.quit(); self.stt_thread.wait(2000)
        if self.audio_capturer: self.audio_capturer.stop_capturing()
        if self.audio_thread and self.audio_thread.isRunning(): self.audio_thread.quit(); self.audio_thread.wait(2000)
        
        logger.info("[Worker] 모든 스레드가 안전하게 종료되었습니다.")

    @Slot(str, bool)
    def on_transcript_updated(self, transcript, is_final):
        """STT 엔진으로부터 텍스트를 받으면 호출됩니다. (중간 번역 로직 추가)"""
        if not self._is_running: return
        
        if is_final and transcript.strip():
            self.sentence_buffer.append(transcript.strip())
            
            if len(self.sentence_buffer) >= MAX_BUFFER_SIZE:
                logger.info(f"버퍼가 가득 차 중간 번역을 실행합니다. (현재 버퍼 크기: {len(self.sentence_buffer)})")
                self.commit_timer.stop()
                self.commit_translation()
            else:
                self.commit_timer.start()
                self.status_update.emit("문장 조합 중...")

    @Slot()
    def commit_translation(self):
        """
        타이머가 만료되거나 버퍼가 가득 차면, 현재까지 조합된 문장을 최종 번역합니다.
        """
        if not self.sentence_buffer: return

        full_sentence = " ".join(self.sentence_buffer)
        self.sentence_buffer.clear()
        
        logger.info(f"최종 번역 문장: '{full_sentence}'")
        self.status_update.emit("번역 중...")
        
        context_text = "\n".join(self.context_history)
        
        source_languages = self.config_manager.get("source_languages", ["en-US"])
        if not source_languages:
            logger.error("원본 언어가 설정되지 않았습니다.")
            self.status_update.emit("오류: 원본 언어가 설정되지 않음")
            return
        source_lang_code = source_languages[0].split('-')[0].upper()
        
        target_languages = self.config_manager.get("target_languages", [])
        if not target_languages:
            logger.warning("번역 대상 언어가 설정되지 않아 번역을 건너뜁니다.")
            self.status_update.emit("오류: 번역할 언어가 선택되지 않음")
            return
            
        langs_to_translate = [lang for lang in target_languages if lang.split('-')[0].upper() != source_lang_code]
        
        translated_results = {}
        if langs_to_translate:
            logger.info(f"{langs_to_translate} 언어로 번역 API를 호출합니다.")
            # 번역 톤은 DeepL 기본값(default)으로 고정
            api_results = self.mt_engine.translate_text_multi(
                full_sentence, 
                target_langs=langs_to_translate, 
                context=context_text,
                formality="default"
            )
            translated_results.update(api_results)
        else:
            logger.info("번역 대상 언어가 원본 언어와 동일하여 API 호출을 생략합니다.")

        final_formatted = []
        for lang in target_languages:
            lang_code_upper = lang.split('-')[0].upper()
            if lang_code_upper == source_lang_code:
                text = full_sentence
            else:
                text = translated_results.get(lang, '...')
            final_formatted.append(f"[{lang.upper()}] {text}")

        formatted_translation = "\n".join(final_formatted)

        self.translation_ready.emit(full_sentence, formatted_translation)
        self.context_history.append(full_sentence)
        self.status_update.emit("번역 대기 중...")