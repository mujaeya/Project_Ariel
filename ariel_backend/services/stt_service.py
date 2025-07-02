# ariel_backend/services/stt_service.py (이 코드로 전체 교체)
import logging
from openai import OpenAI
import os

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

def transcribe_audio_with_whisper(audio_file_name: str, audio_bytes: bytes) -> str:
    """
    오디오 파일 이름과 바이트 데이터를 받아 Whisper API로 텍스트를 추출합니다.
    """
    try:
        # [핵심 수정] 파일 객체 대신 (파일이름, 파일내용) 튜플을 전달
        audio_file = (audio_file_name, audio_bytes)
        
        transcription = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
        )
        logging.info(f"Whisper API 결과: {transcription.text}")
        return transcription.text
    except Exception as e:
        logging.error(f"Whisper API 호출 중 오류 발생: {e}", exc_info=True)
        return ""