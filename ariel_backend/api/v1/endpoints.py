# ariel_backend/api/v1/endpoints.py (이 코드로 전체 교체)
import logging
from fastapi import APIRouter, UploadFile, File, HTTPException
from services import ocr_service, stt_service

router = APIRouter()

@router.post("/ocr", response_model=dict)
async def ocr_image_endpoint(image_file: UploadFile = File(...)):
    image_bytes = await image_file.read()
    extracted_text = ocr_service.process_image_with_ocr(image_bytes)
    return {"text": extracted_text}

@router.post("/stt", response_model=dict)
async def stt_audio_endpoint(audio_file: UploadFile = File(...)):
    """
    오디오 파일을 받아 STT를 수행하고 결과를 반환합니다.
    """
    # [핵심 수정] 파일의 내용(bytes)과 파일 이름(str)을 모두 읽어서 전달
    audio_bytes = await audio_file.read()
    extracted_text = stt_service.transcribe_audio_with_whisper(
        audio_file_name=audio_file.filename, 
        audio_bytes=audio_bytes
    )
    return {"text": extracted_text}