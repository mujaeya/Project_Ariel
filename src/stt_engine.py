# src/stt_engine.py (이 코드로 전체를 교체해주세요)
from PySide6.QtCore import QObject, Signal, Slot
from google.cloud import speech
import queue

# 'video' 모델을 지원하는 언어 목록 (BCP-47 코드 기준, 소문자로 관리하여 비교 용이)
VIDEO_MODEL_SUPPORTED_LANGUAGES = [
    'en-us', 'en-gb', 'fr-fr', 'es-es', 'de-de', 'it-it', 'ja-jp', 'pt-br', 'ru-ru', 'hi-in'
]

class STTEngine(QObject):
    """
    오디오 데이터를 받아 STT API로 전송하고 결과를 반환합니다.
    언어 코드 비교 로직을 강화하여 안정성을 더욱 높였습니다.
    """
    transcript_updated = Signal(str, bool)
    error_occurred = Signal(str)

    def __init__(self, config_manager, audio_queue: queue.Queue, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.audio_queue = audio_queue
        self._is_running = False

    @Slot()
    def start_transcription(self):
        """STT 스트리밍을 시작하는 메인 로직"""
        self._is_running = True
        try:
            language_code = self.config_manager.get("source_languages", ["en-US"])[0]
            language_code_clean = language_code.strip().lower() # 비교를 위해 소문자/공백제거 버전 생성

            # 'video' 모델 자동 적용 로직 (강화된 비교 방식)
            model_to_use = None
            if language_code_clean in VIDEO_MODEL_SUPPORTED_LANGUAGES:
                model_to_use = 'video'
                print(f"[STTEngine] 지원 언어 '{language_code}' 감지, 'video' 모델을 자동으로 사용합니다.")
            else:
                print(f"[STTEngine] 언어 '{language_code}'는 'video' 모델을 지원하지 않아 기본 모델을 사용합니다.")

            client = speech.SpeechClient.from_service_account_json(
                self.config_manager.get("google_credentials_path")
            )
            config = speech.RecognitionConfig(
                encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
                sample_rate_hertz=16000,
                language_code=language_code, # API에는 원래의 언어 코드 전달
                enable_automatic_punctuation=True,
                model=model_to_use
            )
            streaming_config = speech.StreamingRecognitionConfig(
                config=config,
                interim_results=True
            )

            audio_generator = self._audio_stream_generator()

            print("[STTEngine] Google STT 스트리밍을 시작합니다.")
            requests = (
                speech.StreamingRecognizeRequest(audio_content=content)
                for content in audio_generator
            )
            responses = client.streaming_recognize(streaming_config, requests)

            self._listen_for_responses(responses)

        except Exception as e:
            error_message = f"STT 엔진 시작 실패: {e}"
            print(error_message)
            self.error_occurred.emit(error_message)
        
        print("[STTEngine] 스트리밍이 종료되었습니다.")

    def _audio_stream_generator(self):
        """공유 큐에서 오디오 데이터를 꺼내와 STT API로 보내주는 생성기"""
        while self._is_running:
            try:
                chunk = self.audio_queue.get(timeout=0.1)
                if chunk is None:
                    return
                yield chunk
            except queue.Empty:
                continue

    def _listen_for_responses(self, responses):
        """API 응답을 처리하고 시그널을 발생시키는 루프"""
        for response in responses:
            if not self._is_running:
                break
            if not response.results:
                continue

            result = response.results[0]
            if not result.alternatives:
                continue

            transcript = result.alternatives[0].transcript

            if result.is_final:
                print(f"[STTEngine] 최종 문장 감지: {transcript}")
                self.transcript_updated.emit(transcript, True)
            else:
                pass
    
    @Slot()
    def stop_transcription(self):
        """STT 스트리밍을 중지하는 슬롯"""
        print("[STTEngine] 스트리밍 중지를 요청합니다.")
        self._is_running = False