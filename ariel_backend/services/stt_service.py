# ariel_backend/services/stt_service.py (이 코드로 전체 교체)

import logging
from openai import OpenAI
import os
import io
import wave
import time # 파일 이름 구분을 위해 추가


client = OpenAI() # 환경 변수에서 API 키를 자동으로 읽습니다.
logger = logging.getLogger("root")

async def transcribe_audio_with_whisper(audio_bytes: bytes) -> str:


    try:
        # 녹음된 오디오를 파일로 저장해서 직접 들어보자
        timestamp = int(time.time())
        debug_filename = f"debug_audio_{timestamp}.wav"
        
        with wave.open(debug_filename, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            wf.writeframes(audio_bytes)
        
        logger.info(f"✅ 디버깅용 오디오 파일 저장 완료: {debug_filename}")
    except Exception as e:
        logger.error(f"디버깅용 파일 저장 실패: {e}")

    
    """
    순수한 오디오 바이트 데이터를 받아 메모리 상에서 WAV 파일로 변환한 후,
    Whisper API로 텍스트를 추출합니다.
    """
    try:
        # 1. 받은 raw audio bytes를 메모리 상에서 WAV 파일로 변환
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            wf.writeframes(audio_bytes)
        
        wav_buffer.seek(0)
        
        # 2. OpenAI API에 보낼 파일 튜플 생성
        audio_file_tuple = ("audio.wav", wav_buffer)

        # 3. 수정된 파일 튜플로 API 호출
        transcription = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file_tuple,
            language="ko"
        )
        logger.info(f"Whisper API 결과: {transcription.text}")
        return transcription.text

    except Exception as e:
        logger.error(f"Whisper API 호출 중 오류 발생: {e}", exc_info=True)
        return "" # 오류 발생 시 빈 문자열 반환 (또는 None을 반환하여 엔드포인트에서 처리)