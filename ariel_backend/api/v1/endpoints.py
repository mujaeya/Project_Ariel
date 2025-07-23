# ariel_backend/api/v1/endpoints.py (이 코드로 전체 교체)
import logging
from fastapi import APIRouter, UploadFile, File, HTTPException, Form
from pydantic import BaseModel
from typing import Optional

# [핵심 수정] 절대 경로 임포트 사용
from ariel_backend.services import ocr_service
from ariel_backend.services.stt_service import stt_service

router = APIRouter()
logger = logging.getLogger("root")

# [스프린트 1 수정] API 응답 모델 정의
class STTResponse(BaseModel):
    text: str
    language: Optional[str] = None
    language_probability: Optional[float] = None

@router.post("/ocr", response_model=dict)
async def ocr_image_endpoint(image_file: UploadFile = File(...)):
    """
    이미지 파일을 받아 OCR을 수행하고 텍스트를 반환합니다.
    """
    image_bytes = await image_file.read()
    try:
        extracted_text = ocr_service.process_image_with_ocr(image_bytes)
        return {"text": extracted_text}
    except AttributeError:
        logger.warning("ocr_service.process_image_with_ocr function not found. Returning empty string.")
        return {"text": ""}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred during OCR processing: {e}")


@router.post("/stt", response_model=STTResponse)
async def stt_audio_endpoint(
    audio_file: UploadFile = File(...),
    channels: int = Form(...),
    language: Optional[str] = Form(None, description="Language for transcription, e.g., 'en', 'ko'. 'auto' or null for detection.")
):
    """
    오디오 파일, 채널 수, 언어 코드를 받아 STT를 수행하고,
    인식된 텍스트와 언어 정보를 포함한 JSON 객체를 반환합니다.
    """
    audio_bytes = await audio_file.read()

    lang_param = language if language and language.lower() != "auto" else None

    # [스프린트 1 수정] stt_service.transcribe는 이제 튜플을 반환합니다.
    text, detected_lang, lang_prob = await stt_service.transcribe(
        audio_bytes=audio_bytes,
        channels=channels,
        language=lang_param
    )

    # [스프린트 1 수정] 응답 모델에 맞춰 딕셔너리를 반환합니다.
    return {
        "text": text,
        "language": detected_lang,
        "language_probability": lang_prob
    }