import os
from google.cloud import speech
from google.api_core.exceptions import GoogleAPICallError, PermissionDenied

class STTEngine:
    """
    오디오 청크를 받아 Google Cloud Speech-to-Text API로 전송하고,
    화자 분리 결과를 파싱하여 반환하는 클래스.
    """
    def __init__(self, config_manager):
        self.config_manager = config_manager
        
        # --- API 클라이언트 초기화 ---
        google_creds_path = self.config_manager.get("google_credentials_path")
        if not google_creds_path or not os.path.exists(google_creds_path):
            raise FileNotFoundError(
                "Google Cloud 인증 파일 경로가 설정되지 않았거나 파일이 존재하지 않습니다."
                "config.json 파일을 확인해주세요."
            )
        
        # 명시적으로 인증 파일 경로를 사용하여 클라이언트 생성
        self.client = speech.SpeechClient.from_service_account_json(google_creds_path)
        
        # --- 인식 설정 ---
        self.source_language = self.config_manager.get("source_language")
        self.speaker_count = self.config_manager.get("speaker_count")
        
        # 화자 분리 설정
        diarization_config = speech.SpeakerDiarizationConfig(
            enable_speaker_diarization=True,
            min_speaker_count=1,
            max_speaker_count=self.speaker_count,
        )

        # 최종 인식 요청 설정
        self.recognition_config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=16000,
            language_code=self.source_language,
            diarization_config=diarization_config,
            enable_automatic_punctuation=True, # 문장 부호 자동 추가
        )

    def transcribe_chunk(self, audio_chunk: bytes) -> list[dict]:
        """
        단일 오디오 청크를 받아 화자 분리가 적용된 번역을 수행합니다.
        
        반환값 예시:
        [
            {'speaker': 1, 'transcript': 'Hello, how are you?'},
            {'speaker': 2, 'transcript': 'I am fine, thank you.'}
        ]
        """
        if not audio_chunk:
            print("STT Engine: 빈 오디오 청크를 받아 처리를 건너뜁니다.")
            return []

        audio = speech.RecognitionAudio(content=audio_chunk)

        try:
            print("Google STT API에 화자 분리 요청을 보냅니다...")
            response = self.client.recognize(
                config=self.recognition_config,
                audio=audio,
            )
        except PermissionDenied:
            print("오류: Google Cloud STT API 권한이 거부되었습니다. 인증 키를 확인하세요.")
            return [{"speaker": 0, "transcript": "오류: STT API 권한 없음"}]
        except GoogleAPICallError as e:
            print(f"오류: Google Cloud STT API 호출 실패: {e}")
            return [{"speaker": 0, "transcript": f"오류: STT API 호출 실패"}]

        if not response.results or not response.results[0].alternatives:
            print("STT API로부터 결과를 받지 못했습니다.")
            return []

        # 화자 분리 결과는 마지막 result에 들어 있음
        result = response.results[-1]
        words_info = result.alternatives[0].words

        if not words_info:
            print("단어 정보를 찾을 수 없습니다. (음성 미감지)")
            return []
            
        print("API 응답 수신 완료. 결과를 문장으로 재구성합니다...")
        return self._reconstruct_sentences(words_info)

    def _reconstruct_sentences(self, words_info) -> list[dict]:
        """단어 정보 리스트를 받아 화자별 문장으로 재구성합니다."""
        sentences_by_speaker = []
        current_speaker_tag = None
        current_sentence = ''

        for word_info in words_info:
            speaker_tag = word_info.speaker_tag
            word = word_info.word

            if current_speaker_tag is None:
                current_speaker_tag = speaker_tag

            # 화자가 바뀌었으면, 이전까지의 문장을 저장
            if current_speaker_tag != speaker_tag:
                if current_sentence:
                    sentences_by_speaker.append({
                        'speaker': current_speaker_tag,
                        'transcript': current_sentence.strip()
                    })
                # 새로운 문장 시작
                current_speaker_tag = speaker_tag
                current_sentence = word
            else:
                current_sentence += f" {word}"

        # 마지막 문장 추가
        if current_sentence:
            sentences_by_speaker.append({
                'speaker': current_speaker_tag,
                'transcript': current_sentence.strip()
            })
            
        return sentences_by_speaker


# --- 이 파일을 직접 실행하여 테스트하는 부분 ---
if __name__ == '__main__':
    from config_manager import ConfigManager
    from audio_capturer import AudioCapturer
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import QObject, Slot
    import sys
    import time

    # Qt 환경 구성
    app = QApplication(sys.argv)
    
    try:
        config = ConfigManager()
        stt_engine = STTEngine(config)
    except FileNotFoundError as e:
        print(f"초기화 오류: {e}")
        sys.exit(1)

    device_name = config.get("audio_input_device_name")
    buffer_seconds = config.get("buffer_seconds")
    capturer = AudioCapturer(device_name=device_name, buffer_seconds=buffer_seconds)

    class TestHandler(QObject):
        @Slot(bytes)
        def process_audio_chunk(self, audio_chunk):
            print(f"\n--- {buffer_seconds}초 분량의 오디오 청크로 STT 시작 ---")
            results = stt_engine.transcribe_chunk(audio_chunk)
            
            if results:
                print("\n✅ 화자 분리 결과:")
                for result in results:
                    print(f"  [화자 {result['speaker']}] {result['transcript']}")
            else:
                print("\n❌ 인식된 음성 없음.")
            print("-" * 20)


    handler = TestHandler()
    capturer.chunk_ready.connect(handler.process_audio_chunk)
    capturer.error_occurred.connect(lambda msg: print(f"캡처 오류: {msg}"))
    
    print("="*50)
    print("화자 분리 STT 엔진 테스트를 시작합니다.")
    print("테스트 방법:")
    print("1. 윈도우 사운드 출력을 'CABLE Input'으로 설정하세요.")
    print("2. 두 명 이상이 대화하는 영상(인터뷰, 영화 등)을 재생하세요.")
    print(f"3. {buffer_seconds}초마다 자동으로 음성을 인식하고 화자를 분리합니다.")
    print("4. 종료하려면 터미널에서 Ctrl+C를 누르세요.")
    print("="*50)
    
    try:
        capturer.start()
        # app.exec()는 blocking이므로 while loop 사용
        while capturer.isRunning():
            app.processEvents()
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\n사용자에 의해 종료 요청됨.")
    finally:
        if capturer.isRunning():
            capturer.stop()
        print("테스트 종료.")