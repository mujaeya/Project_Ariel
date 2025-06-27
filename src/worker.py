# src/worker.py (최종 아키텍처 완성본)
from PySide6.QtCore import QObject, Signal, Slot, QThread, QTimer
import queue
from collections import deque

# 이 파일들은 모두 올바르게 구현되어 있다고 가정합니다.
from config_manager import ConfigManager
from audio_capturer import AudioCapturer
from stt_engine import STTEngine
from mt_engine import MTEngine

class Worker(QObject):
    """
    메인 GUI 스레드에서 실행되며, 실제 작업 스레드들을 총괄 지휘하는 컨트롤 타워.
    QTimer를 사용하여 '스마트 문장 조합' 로직을 안정적으로 수행합니다.
    """
    translation_ready = Signal(str, str)
    status_update = Signal(str)
    error_occurred = Signal(str)

    def __init__(self, config_manager: ConfigManager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self._is_running = False

        # 스마트 문장 조합을 위한 변수들
        self.sentence_buffer = []
        self.commit_timer = QTimer(self) # 부모를 self(QObject)로 지정
        self.commit_timer.setSingleShot(True)
        delay = self.config_manager.get("sentence_commit_delay_ms", 700)        
        self.commit_timer.setInterval(1200) # 1.2초 후 최종 번역 실행
        self.commit_timer.timeout.connect(self.commit_translation)

        # 번역 문맥을 위한 변수
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
        
        print("[Manager] 모든 처리 스레드를 시작합니다.")
        self._is_running = True
        self.status_update.emit("초기화 중...")
        self.context_history.clear()
        self.sentence_buffer.clear()

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
            print("[Manager] 모든 스레드가 성공적으로 시작되었습니다.")

        except Exception as e:
            error_msg = f"작업자 초기화 실패: {e}"
            print(error_msg)
            self.error_occurred.emit(error_msg)

    @Slot()
    def stop_processing(self):
        """모든 번역 관련 스레드를 안전하게 중지합니다."""
        if not self._is_running: return
            
        print("[Manager] 모든 처리 스레드를 중지합니다.")
        self._is_running = False
        self.commit_timer.stop()

        if self.stt_engine: self.stt_engine.stop_transcription()
        if self.stt_thread: self.stt_thread.quit(); self.stt_thread.wait(2000)
        if self.audio_capturer: self.audio_capturer.stop_capturing()
        if self.audio_thread: self.audio_thread.quit(); self.audio_thread.wait(2000)
        
        print("[Manager] 모든 스레드가 안전하게 종료되었습니다.")

    @Slot(str, bool)
    def on_transcript_updated(self, transcript, is_final):
        """STT 엔진으로부터 텍스트를 받으면 호출됩니다."""
        if is_final and transcript.strip():
            self.sentence_buffer.append(transcript.strip())
            self.commit_timer.start() # 메인 스레드에 있는 타이머이므로 안전
            self.status_update.emit("문장 조합 중...")

    @Slot()
    def commit_translation(self):
        """
        타이머가 만료되어, 현재까지 조합된 문장을 최종 번역합니다.
        """
        if not self.sentence_buffer: return

        full_sentence = " ".join(self.sentence_buffer)
        self.sentence_buffer.clear()
        
        self.status_update.emit("번역 중...")
        
        context_text = "\n".join(self.context_history)
        target_languages = self.config_manager.get("target_languages", [])
        if not target_languages:
            self.status_update.emit("오류: 번역할 언어가 선택되지 않았습니다.")
            return

        formality = self.config_manager.get("translation_formality", "default")
        
        translated_results = self.mt_engine.translate_text_multi(
            full_sentence, 
            target_langs=target_languages, 
            context=context_text,
            formality=formality
        )
        
        formatted_translation = "\n".join(
            f"[{lang.upper()}] {translated_results.get(lang, '...')}" for lang in target_languages
        )

        self.translation_ready.emit(full_sentence, formatted_translation)
        self.context_history.append(full_sentence)
        self.status_update.emit("번역 대기 중...")