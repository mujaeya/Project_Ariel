# ariel_backend/api/v1/endpoints.py (이 코드로 전체 교체)
import logging
from fastapi import APIRouter, UploadFile, File, HTTPException, Form
from pydantic import BaseModel
from typing import Optional

from ariel_backend.services import ocr_service
from ariel_backend.services.stt_service import stt_service

router = APIRouter()
logger = logging.getLogger("root")

class STTResponse(BaseModel):
    text: str
    language: Optional[str] = None
    language_probability: Optional[float] = None

@router.post("/ocr", response_model=dict)
async def ocr_image_endpoint(image_file: UploadFile = File(...)):
    image_bytes = await image_file.read()
    try:
        extracted_text = ocr_service.process_image_with_ocr(image_bytes)
        return {"text": extracted_text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred during OCR processing: {e}")


@router.post("/stt", response_model=STTResponse)
async def stt_audio_endpoint(
    # [핵심 수정] 요청 폼에 model_size와 client_id 추가
    audio_file: UploadFile = File(...),
    channels: int = Form(...),
    language: Optional[str] = Form(None, description="Language for transcription, e.g., 'en', 'ko'. 'auto' or null for detection."),
    model_size: str = Form("medium", description="The whisper model size to use (e.g., 'tiny', 'base', 'small', 'medium')."),
    client_id: str = Form("unknown", description="A unique identifier for the client.")
):
    """
    [V12.2 수정] 오디오 파일과 함께 사용할 모델 크기, 클라이언트 ID를 받아
    STT를 수행하고 결과를 반환합니다.
    """
    logger.debug(f"STT request received from client '{client_id}' with model '{model_size}' and language '{language}'.")
    audio_bytes = await audio_file.read()

    lang_param = language if language and language.lower() != "auto" else None
    
    # [핵심 수정] stt_service.transcribe 호출 시 model_size 전달
    text, detected_lang, lang_prob = await stt_service.transcribe(
        audio_bytes=audio_bytes,
        channels=channels,
        language=lang_param,
        model_size=model_size
    )

    return {
        "text": text,
        "language": detected_lang,
        "language_probability": lang_prob
    }