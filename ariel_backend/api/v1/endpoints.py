# ariel_backend/api/v1/endpoints.py (수정 후)

import logging
from fastapi import APIRouter, UploadFile, File, HTTPException
from services import ocr_service, stt_service

router = APIRouter()

@router.post("/ocr", response_model=dict)
async def ocr_image_endpoint(image_file: UploadFile = File(...)):
    # OCR은 클라이언트에서 파일 형태로 보내므로 기존 코드를 유지합니다.
    image_bytes = await image_file.read()
    extracted_text = ocr_service.process_image_with_ocr(image_bytes)
    return {"text": extracted_text}

@router.post("/stt", response_model=dict)
async def stt_audio_endpoint(audio_file: UploadFile = File(...)):
    """
    [수정] 클라이언트로부터 multipart/form-data 형태의 오디오 파일을 받아 STT를 수행합니다.
    Request 객체에서 직접 body를 읽는 대신 UploadFile을 사용하여 파일 데이터를 처리합니다.
    """
    # UploadFile 객체에서 오디오 바이트를 직접 읽습니다.
    audio_bytes = await audio_file.read()

    # 서비스 계층 함수에는 오디오 바이트만 전달합니다.
    extracted_text = await stt_service.transcribe_audio_with_whisper(
        audio_bytes=audio_bytes
    )

    if extracted_text is None:
        raise HTTPException(status_code=500, detail="STT 처리 중 서버 내부 오류가 발생했습니다.")
        
    return {"text": extracted_text}