# ariel_backend/services/stt_service.py (이 코드로 전체 교체)
import logging
import numpy as np
from faster_whisper import WhisperModel
import torch
from typing import Optional, Tuple

# 로거 설정
logger = logging.getLogger("root")

class STTService:
    """
    faster-whisper 모델을 사용하여 STT를 수행하는 서비스 클래스.
    모델은 애플리케이션 시작 시 한 번만 로드됩니다.
    """
    _instance = None

    # 싱글톤 패턴을 사용하여, 설정이 변경되어도 모델이 재로드되지 않도록 방지
    # 모델 로드는 run_server.py에서 명시적으로 제어합니다.
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(STTService, cls).__new__(cls)
            cls._instance.model = None
        return cls._instance

    def load_model(self, model_size: str = "medium", device: str = "auto", compute_type: str = "auto"):
        """
        STT 모델을 동적으로 로드합니다. 이미 모델이 로드된 경우 다시 로드하지 않습니다.

        Args:
            model_size (str): 사용할 Whisper 모델 크기. 기본값 "medium".
            device (str): 모델을 실행할 장치. "auto"로 설정 시 자동 감지.
            compute_type (str): 계산 타입. "auto"로 설정 시 자동 감지.
        """
        if self.model is not None:
            logger.info("Model is already loaded. Skipping model loading.")
            return

        try:
            effective_device = device
            effective_compute_type = compute_type

            if device == "auto":
                effective_device = "cuda" if torch.cuda.is_available() else "cpu"

            if compute_type == "auto":
                # CUDA 사용 시 float16으로 최적화, CPU에서는 int8 사용
                effective_compute_type = "float16" if effective_device == "cuda" else "int8"
            
            if effective_device == "cuda" and not torch.cuda.is_available():
                logger.warning("CUDA specified but not available, falling back to CPU.")
                effective_device = "cpu"
                effective_compute_type = "int8"

            logger.info(f"Loading faster-whisper model '{model_size}' on '{effective_device}' with compute_type '{effective_compute_type}'...")
            self.model = WhisperModel(model_size, device=effective_device, compute_type=effective_compute_type)
            logger.info(f"Model '{model_size}' loaded successfully.")

        except Exception as e:
            logger.critical(f"Failed to load faster-whisper model: {e}", exc_info=True)
            self.model = None # 실패 시 모델을 None으로 유지
            raise

    def _convert_stereo_to_mono(self, stereo_bytes: bytes) -> bytes:
        """2채널, 16비트 오디오 바이트를 1채널 모노로 변환합니다."""
        try:
            stereo_audio = np.frombuffer(stereo_bytes, dtype=np.int16)
            mono_audio = (stereo_audio[0::2].astype(np.int32) + stereo_audio[1::2].astype(np.int32)) // 2
            return mono_audio.astype(np.int16).tobytes()
        except Exception as e:
            logger.error(f"Error converting stereo to mono: {e}")
            return stereo_bytes

    async def transcribe(self, audio_bytes: bytes, channels: int, language: Optional[str]) -> Tuple[str, Optional[str], Optional[float]]:
        """
        오디오 바이트 데이터를 받아 STT를 수행하고, 추가 정보를 함께 반환합니다.

        Args:
            audio_bytes (bytes): 오디오 데이터.
            channels (int): 오디오 채널 수 (1 또는 2).
            language (Optional[str]): 인식할 언어 코드 (예: "ko", "en"). "auto" 또는 None일 경우 자동 감지.

        Returns:
            Tuple[str, Optional[str], Optional[float]]: (인식된 텍스트, 감지된 언어, 감지된 언어 확률)
        """
        if not self.model:
            logger.error("STT Service is not available because the model is not loaded.")
            return "", None, None

        processed_audio_bytes = audio_bytes
        if channels == 2:
            processed_audio_bytes = self._convert_stereo_to_mono(processed_audio_bytes)
        
        audio_np = np.frombuffer(processed_audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0

        try:
            if language:
                language = language.lower()

            lang_option = language if language and language != "auto" else None
            
            segments, info = self.model.transcribe(audio_np, language=lang_option, vad_filter=True)
            
            detected_lang = info.language
            detected_lang_prob = info.language_probability

            if lang_option is None:
                logger.info(f"Detected language '{detected_lang}' with probability {detected_lang_prob:.2f}")

            result_text = "".join(segment.text for segment in segments).strip()
            
            logger.info(f"Transcription result: {result_text}")
            return result_text, detected_lang, detected_lang_prob

        except ValueError as ve:
            logger.error(f"Invalid language code provided. Error: {ve}", exc_info=True)
            return "", None, None
        except Exception as e:
            logger.error(f"Error during transcription: {e}", exc_info=True)
            return "", None, None

# STTService의 싱글톤 인스턴스 생성
# 이 인스턴스는 이제 비어 있으며, run_server.py에서 load_model을 호출하여 초기화됩니다.
stt_service = STTService()