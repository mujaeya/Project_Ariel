# ariel_backend/services/stt_service.py (이 코드로 전체 교체)
import logging
from openai import OpenAI
import io
import wave
import time
import numpy as np

client = OpenAI() # 환경 변수에서 API 키를 자동으로 읽습니다.
logger = logging.getLogger("root")

def convert_stereo_to_mono_bytes(stereo_bytes: bytes) -> bytes:
    """2채널, 16비트 오디오 바이트를 1채널 모노로 변환합니다."""
    try:
        # 16비트 정수형(int16)으로 바이트 데이터를 읽음
        stereo_audio = np.frombuffer(stereo_bytes, dtype=np.int16)
        
        # 스테레오 데이터를 왼쪽과 오른쪽 채널로 분리
        left_channel = stereo_audio[0::2]
        right_channel = stereo_audio[1::2]
        
        # 두 채널을 평균내어 모노 데이터 생성 (정수형으로 유지)
        mono_audio = (left_channel.astype(np.int32) + right_channel.astype(np.int32)) // 2
        mono_audio = mono_audio.astype(np.int16)
        
        # 모노 데이터를 다시 바이트로 변환
        return mono_audio.tobytes()
    except Exception as e:
        logger.error(f"스테레오->모노 변환 중 오류: {e}")
        # 변환 실패 시 원본 데이터 반환
        return stereo_bytes

async def transcribe_audio_with_whisper(audio_bytes: bytes, channels: int) -> str:
    """
    오디오 바이트 데이터를 받아 Whisper API로 텍스트를 추출합니다.
    [수정] 채널 수(channels)를 인자로 받아, 2채널이면 모노로 변환합니다.
    """
    processed_audio_bytes = audio_bytes
    
    # 채널 수가 2인 경우에만 모노로 변환
    if channels == 2:
        logger.info(f"입력 오디오가 2채널(스테레오)이므로 모노로 변환을 시도합니다. (원본 크기: {len(audio_bytes)} bytes)")
        processed_audio_bytes = convert_stereo_to_mono_bytes(audio_bytes)
        logger.info(f"모노 변환 완료. (변환된 크기: {len(processed_audio_bytes)} bytes)")

    try:
        # 메모리 상에서 WAV 파일로 변환
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, 'wb') as wf:
            wf.setnchannels(1)  # 모노로 변환했으므로 1로 고정
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(16000)
            wf.writeframes(processed_audio_bytes)
        
        wav_buffer.seek(0)
        
        audio_file_tuple = ("audio.wav", wav_buffer)

        transcription = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file_tuple,
            language="ko" # 필요 시 'None'으로 설정하여 자동 감지
        )
        logger.info(f"Whisper API 결과: {transcription.text}")
        return transcription.text

    except Exception as e:
        logger.error(f"Whisper API 호출 중 오류 발생: {e}", exc_info=True)
        return ""