# ariel_backend/services/stt_manager.py
import logging
import os
import json
from vosk import Model, KaldiRecognizer

logger = logging.getLogger("root")

# Docker 컨테이너 내 /app/models/vosk 를 기준으로 모델 경로 정의
MODEL_BASE_DIR = "models/vosk"

# 지원할 16개 언어 및 모델 폴더명 정의
# 실제 폴더명과 일치해야 합니다.
MODEL_PATHS = {
    "ar": "vosk-model-ar-0.22-linto-1.1.0",
    "cs": "vosk-model-cs-0.6-multi",
    "de": "vosk-model-de-0.21",
    "el": "vosk-model-el-gr-0.7",
    "en": "vosk-model-en-us-0.22",
    "es": "vosk-model-es-0.42",
    "fr": "vosk-model-fr-0.22",
    "he": "vosk-model-he-0.18",
    "id": "vosk-model-id-0.4",
    "it": "vosk-model-it-0.22",
    "ja": "vosk-model-ja-0.22",
    "ko": "vosk-model-ko-0.22",
    "pt": "vosk-model-pt-0.3",
    "ru": "vosk-model-ru-0.42",
    "tr": "vosk-model-tr-0.3",
    "uk": "vosk-model-uk-0.4-lbuild",
}

class STTManager:
    """
    Vosk STT 엔진을 총괄 관리하는 서비스.
    애플리케이션 시작 시, 지원하는 모든 언어의 Vosk 모델을 로드하고
    KaldiRecognizer를 미리 생성하여 요청에 신속하게 응답합니다.
    """
    def __init__(self):
        self.models = {}
        self.recognizers = {}
        self.supported_languages = []

        logger.info("Initializing STT Manager with Vosk models...")

        for lang_code, model_name in MODEL_PATHS.items():
            model_path = os.path.join(MODEL_BASE_DIR, model_name)
            if not os.path.exists(model_path):
                logger.warning(f"Model path not found for language '{lang_code}': {model_path}. Skipping.")
                continue

            try:
                logger.info(f"Loading Vosk model for '{lang_code}' from {model_path}...")
                model = Model(model_path)
                self.models[lang_code] = model
                
                # 오디오 샘플링 레이트는 16000Hz로 고정
                recognizer = KaldiRecognizer(model, 16000)
                self.recognizers[lang_code] = recognizer
                self.supported_languages.append(lang_code)
                
                logger.info(f"Successfully loaded model and created recognizer for '{lang_code}'.")

            except Exception as e:
                logger.error(f"Failed to load model for language '{lang_code}': {e}", exc_info=True)
        
        logger.info(f"STT Manager initialized. Supported languages: {self.supported_languages}")

    def process_stt_request(self, audio_data: bytes, language: str) -> str:
        """
        bytes 형태의 오디오 데이터를 받아 지정된 언어의 STT를 수행하고 텍스트를 반환합니다.
        오디오는 16kHz, 16-bit, Mono PCM 형식이어야 합니다.
        """
        if language not in self.recognizers:
            logger.error(f"Unsupported language request: {language}. Available: {self.supported_languages}")
            raise ValueError(f"Unsupported or unloaded language: {language}")

        recognizer = self.recognizers[language]

        try:
            if recognizer.AcceptWaveform(audio_data):
                result = json.loads(recognizer.Result())
                text = result.get('text', '')
            else:
                result = json.loads(recognizer.PartialResult())
                text = result.get('partial', '')

            # 다음 인식을 위해 recognizer 상태 초기화
            recognizer.Reset()

            logger.info(f"Transcription result for '{language}': {text}")
            return text

        except Exception as e:
            logger.error(f"Error during audio processing for language '{language}': {e}", exc_info=True)
            # 문제가 발생해도 recognizer를 리셋하여 다음 요청에 영향이 없도록 함
            recognizer.Reset()
            return ""

# 애플리케이션 전역에서 사용할 싱글턴 인스턴스 생성
stt_manager = STTManager()