# ariel_backend/api/v1/endpoints.py (이 코드로 전체 교체)

import logging
from fastapi import APIRouter, UploadFile, File, HTTPException, Request
from services import ocr_service, stt_service

router = APIRouter()

@router.post("/ocr", response_model=dict)
async def ocr_image_endpoint(image_file: UploadFile = File(...)):
    # OCR은 클라이언트에서 파일 형태로 보낼 가능성이 높으므로 그대로 둡니다.
    image_bytes = await image_file.read()
    extracted_text = ocr_service.process_image_with_ocr(image_bytes)
    return {"text": extracted_text}

@router.post("/stt", response_model=dict)
async def stt_audio_endpoint(request: Request):
    """
    클라이언트로부터 순수 오디오 바이트(raw bytes)를 받아 STT를 수행합니다.
    """
    # [핵심 수정] UploadFile 대신 Request 객체를 직접 받아 body()로 전체 내용을 읽습니다.
    audio_bytes = await request.body()
    
    # [핵심 수정] 이제 stt_service에는 audio_bytes 하나만 전달합니다.
    extracted_text = await stt_service.transcribe_audio_with_whisper(
        audio_bytes=audio_bytes
    )
    
    if extracted_text is None:
        raise HTTPException(status_code=500, detail="STT 처리 중 서버 내부 오류 발생")
        
    return {"text": extracted_text}