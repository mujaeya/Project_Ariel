# ariel_backend/services/stt_service.py (이 코드로 전체 교체)
import logging
import numpy as np
from faster_whisper import WhisperModel
import torch

# 로거 설정
logger = logging.getLogger("root")

class STTService:
    """
    faster-whisper 모델을 사용하여 STT를 수행하는 서비스 클래스.
    모델은 애플리케이션 시작 시 한 번만 로드됩니다.
    """
    def __init__(self, model_size="base", device="cpu", compute_type="int8"):
        """
        서비스 초기화 시 faster-whisper 모델을 로드합니다.
        
        Args:
            model_size (str): 사용할 Whisper 모델 크기 (예: "tiny", "base", "small").
            device (str): 모델을 실행할 장치 ("cpu" 또는 "cuda").
            compute_type (str): 계산에 사용할 타입 (예: "int8", "float16"). CPU에서는 int8이 효율적입니다.
        """
        self.model = None
        try:
            # 사용 가능한 경우 CUDA를 확인하고, 그렇지 않으면 CPU를 사용합니다.
            if device == "cuda" and not torch.cuda.is_available():
                logger.warning("CUDA is not available, falling back to CPU.")
                device = "cpu"

            logger.info(f"Loading faster-whisper model '{model_size}' on '{device}'...")
            self.model = WhisperModel(model_size, device=device, compute_type=compute_type)
            logger.info(f"Model '{model_size}' loaded successfully.")
        except Exception as e:
            logger.critical(f"Failed to load faster-whisper model: {e}", exc_info=True)
            # 모델 로드 실패 시 애플리케이션이 시작되지 않도록 예외를 다시 발생시킬 수 있습니다.
            raise e

    def _convert_stereo_to_mono(self, stereo_bytes: bytes) -> bytes:
        """2채널, 16비트 오디오 바이트를 1채널 모노로 변환합니다."""
        try:
            stereo_audio = np.frombuffer(stereo_bytes, dtype=np.int16)
            # 두 채널을 평균내어 모노로 변환
            mono_audio = (stereo_audio[0::2].astype(np.int32) + stereo_audio[1::2].astype(np.int32)) // 2
            return mono_audio.astype(np.int16).tobytes()
        except Exception as e:
            logger.error(f"Error converting stereo to mono: {e}")
            return stereo_bytes

    async def transcribe(self, audio_bytes: bytes, channels: int, language: str) -> str:
        """
        오디오 바이트 데이터를 받아 STT를 수행합니다.

        Args:
            audio_bytes (bytes): 오디오 데이터.
            channels (int): 오디오 채널 수 (1 또는 2).
            language (str): 인식할 언어 코드 (예: "ko", "en"). "auto"일 경우 자동 감지.

        Returns:
            str: 인식된 텍스트.
        """
        if not self.model:
            logger.error("STT Service is not available because the model failed to load.")
            return ""

        processed_audio_bytes = audio_bytes
        if channels == 2:
            processed_audio_bytes = self._convert_stereo_to_mono(processed_audio_bytes)
        
        # 바이트를 float32 NumPy 배열로 변환 (faster-whisper 요구사항)
        audio_np = np.frombuffer(processed_audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0

        try:
            lang_option = language if language and language != "auto" else None
            
            # VAD 필터를 사용하여 음성 구간만 인식 (정확도 및 성능 향상)
            segments, info = self.model.transcribe(audio_np, language=lang_option, vad_filter=True)
            
            if lang_option is None:
                logger.info(f"Detected language '{info.language}' with probability {info.language_probability:.2f}")

            # 모든 인식된 텍스트 조각을 하나로 합침
            result_text = "".join(segment.text for segment in segments).strip()
            
            logger.info(f"Transcription result: {result_text}")
            return result_text

        except Exception as e:
            logger.error(f"Error during transcription: {e}", exc_info=True)
            return ""

# STTService의 싱글톤 인스턴스 생성
# FastAPI 애플리케이션이 이 인스턴스를 공유하여 사용합니다.
stt_service = STTService()