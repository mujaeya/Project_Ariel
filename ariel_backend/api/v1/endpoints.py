# ariel_backend/api/v1/endpoints.py
import logging
from fastapi import APIRouter, UploadFile, File, HTTPException, Form

# pydantic은 FastAPI에서 자동으로 import 되므로 명시적 import는 필요 없음
from pydantic import BaseModel
from typing import Optional

# OCR 서비스는 그대로 유지
from ariel_backend.services import ocr_service 
# 새로운 STT 매니저를 import
from ariel_backend.services.stt_manager import stt_manager

router = APIRouter()
logger = logging.getLogger("root")

# --- 응답 모델 정의 ---
class OcrResponse(BaseModel):
    text: str

class STTResponse(BaseModel):
    text: str

# --- API 엔드포인트 ---
@router.post("/ocr", response_model=OcrResponse)
async def ocr_image_endpoint(image_file: UploadFile = File(...)):
    """이미지 파일에서 텍스트를 추출합니다."""
    image_bytes = await image_file.read()
    try:
        extracted_text = ocr_service.process_image_with_ocr(image_bytes)
        return {"text": extracted_text}
    except Exception as e:
        logger.error(f"OCR Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"An error occurred during OCR processing: {e}")

@router.post("/stt", response_model=STTResponse)
async def stt_audio_endpoint(
    audio_file: UploadFile = File(...),
    language: str = Form("ko", description="Language for transcription (e.g., 'en', 'ko', 'ja').")
):
    """
    오디오 파일을 받아 지정된 언어로 음성 인식을 수행합니다.
    - language: 'ko', 'en', 'ja' 등 STT 매니저에 의해 지원되는 언어 코드
    """
    logger.debug(f"STT request received for language '{language}'.")
    audio_bytes = await audio_file.read()
    
    try:
        transcribed_text = stt_manager.process_stt_request(
            audio_data=audio_bytes,
            language=language
        )
        return {"text": transcribed_text}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"STT Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"An error occurred during STT processing: {e}")