from PySide6.QtCore import QObject, Signal, Slot
from google.cloud import speech
import queue

class STTEngine(QObject): 
    """
    독립된 스레드에서 실행되며, 공유 큐에서 오디오 데이터를 가져와
    실시간으로 Google STT API로 전송하고, 그 결과를 다시 시그널로
    상위 매니저(Worker)에게 전달하는 역할만 전담합니다.
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
            client = speech.SpeechClient.from_service_account_json(
                self.config_manager.get("google_credentials_path")
            )
            config = speech.RecognitionConfig(
                encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
                sample_rate_hertz=16000,
                language_code=self.config_manager.get("source_language", "en-US"),
                enable_automatic_punctuation=True,
                model='video' if self.config_manager.get("use_video_model", False) else None,
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
                chunk = self.audio_queue.get()
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
                self.transcript_updated.emit(transcript, False)
    
    @Slot()
    def stop_transcription(self):
        """STT 스트리밍을 중지하는 슬롯"""
        print("[STTEngine] 스트리밍 중지를 요청합니다.")
        self._is_running = False