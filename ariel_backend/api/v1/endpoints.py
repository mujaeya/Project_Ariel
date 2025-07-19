# ariel_backend/api/v1/endpoints.py (이 코드로 전체 교체)
import logging
from fastapi import APIRouter, UploadFile, File, HTTPException, Form
from services import ocr_service, stt_service

router = APIRouter()

@router.post("/ocr", response_model=dict)
async def ocr_image_endpoint(image_file: UploadFile = File(...)):
    image_bytes = await image_file.read()
    extracted_text = ocr_service.process_image_with_ocr(image_bytes)
    return {"text": extracted_text}

@router.post("/stt", response_model=dict)
async def stt_audio_endpoint(
    audio_file: UploadFile = File(...),
    channels: int = Form(1) # [추가] 오디오 채널 수를 form 데이터로 받음
):
    """
    오디오 파일과 채널 수를 받아 STT를 수행합니다.
    """
    audio_bytes = await audio_file.read()

    # 서비스 계층 함수에 오디오 바이트와 채널 수를 전달합니다.
    extracted_text = await stt_service.transcribe_audio_with_whisper(
        audio_bytes=audio_bytes,
        channels=channels
    )

    if extracted_text is None:
        raise HTTPException(status_code=500, detail="STT 처리 중 서버 내부 오류가 발생했습니다.")
        
    return {"text": extracted_text}