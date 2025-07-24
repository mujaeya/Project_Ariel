# ariel_backend/services/stt_service.py (이 코드로 전체 교체)
import logging
import numpy as np
from faster_whisper import WhisperModel
import torch
from typing import Optional, Tuple, Dict, List

# 로거 설정
logger = logging.getLogger("root")

class STTService:
    """
    [V12.2 수정] 다양한 faster-whisper 모델을 관리하고,
    사용자 요청에 따라 적절한 모델을 선택하여 STT를 수행하는 서비스 클래스.
    모델들은 애플리케이션 시작 시 한 번만 로드됩니다.
    """
    _instance = None
    
    # [핵심 수정] 단일 모델 -> 모델 딕셔너리
    models: Dict[str, WhisperModel] = {}
    default_model_size: str = "medium"

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(STTService, cls).__new__(cls)
        return cls._instance

    def load_models(self, model_sizes: List[str] = ["tiny", "base", "small", "medium"], device: str = "auto", compute_type: str = "auto"):
        """
        [핵심 수정] 지정된 크기의 모든 STT 모델을 로드하여 딕셔너리에 저장합니다.
        """
        if self.models:
            logger.info("Models are already loaded. Skipping model loading.")
            return

        effective_device = device
        effective_compute_type = compute_type

        if device == "auto":
            effective_device = "cuda" if torch.cuda.is_available() else "cpu"
        if compute_type == "auto":
            effective_compute_type = "float16" if effective_device == "cuda" else "int8"
        if effective_device == "cuda" and not torch.cuda.is_available():
            logger.warning("CUDA specified but not available, falling back to CPU.")
            effective_device = "cpu"
            effective_compute_type = "int8"

        for size in model_sizes:
            try:
                logger.info(f"Loading faster-whisper model '{size}' on '{effective_device}' with compute_type '{effective_compute_type}'...")
                model = WhisperModel(size, device=effective_device, compute_type=effective_compute_type)
                self.models[size] = model
                logger.info(f"Model '{size}' loaded successfully.")
            except Exception as e:
                logger.error(f"Failed to load faster-whisper model '{size}': {e}", exc_info=True)
                # 하나가 실패해도 계속 진행
        
        if not self.models:
            logger.critical("No STT models could be loaded. STT service will be unavailable.")
            raise RuntimeError("Failed to load any STT models.")

    def _convert_stereo_to_mono(self, stereo_bytes: bytes) -> bytes:
        """2채널, 16비트 오디오 바이트를 1채널 모노로 변환합니다."""
        try:
            stereo_audio = np.frombuffer(stereo_bytes, dtype=np.int16)
            mono_audio_int32 = (stereo_audio[0::2].astype(np.int32) + stereo_audio[1::2].astype(np.int32)) // 2
            mono_audio = np.clip(mono_audio_int32, -32768, 32767).astype(np.int16)
            return mono_audio.tobytes()
        except Exception as e:
            logger.error(f"Error converting stereo to mono: {e}")
            return stereo_bytes

    async def transcribe(
        self,
        audio_bytes: bytes,
        channels: int,
        language: Optional[str],
        model_size: str  # [핵심 수정] 사용할 모델 크기를 명시적으로 받음
    ) -> Tuple[str, Optional[str], Optional[float]]:
        """
        [핵심 수정] 지정된 모델 크기를 사용하여 오디오 바이트 데이터의 STT를 수행합니다.
        """
        # [핵심 수정] 요청된 모델 또는 기본 모델 선택
        target_model = self.models.get(model_size)
        if not target_model:
            logger.warning(f"Requested model '{model_size}' not found. Falling back to available models.")
            # 사용 가능한 모델 중 아무거나 하나 선택 (예: 첫 번째 모델)
            if not self.models:
                 logger.error("STT Service is not available because no models are loaded.")
                 return "", None, None
            fallback_size = next(iter(self.models))
            target_model = self.models[fallback_size]
            logger.warning(f"Using fallback model: '{fallback_size}'")

        processed_audio_bytes = audio_bytes
        if channels == 2:
            processed_audio_bytes = self._convert_stereo_to_mono(processed_audio_bytes)
        
        if len(processed_audio_bytes) < 16000 * 2 * 0.1:
            return "", None, None
            
        audio_np = np.frombuffer(processed_audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0

        try:
            lang_option = language.lower() if language and language.lower() != "auto" else None
            
            segments, info = target_model.transcribe(
                audio_np,
                language=lang_option,
                vad_filter=True,
                log_prob_threshold=-1.0,
                no_speech_threshold=0.6,
                condition_on_previous_text=True,
                temperature=0,
            )
            
            detected_lang = info.language
            detected_lang_prob = info.language_probability

            result_text = "".join(segment.text for segment in segments).strip()
            
            if result_text:
                logger.info(f"[{model_size}] Transcription result: {result_text}")
            
            return result_text, detected_lang, detected_lang_prob

        except Exception as e:
            logger.debug(f"[{model_size}] Transcription resulted in an exception (likely silence): {e}")
            return "", None, None

stt_service = STTService()