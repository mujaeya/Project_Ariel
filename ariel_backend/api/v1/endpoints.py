# ariel_backend/api/v1/endpoints.py (이 코드로 전체 교체)
import logging
from fastapi import APIRouter, UploadFile, File, HTTPException, Form
from services import ocr_service
# STTService 클래스가 아닌, 생성된 stt_service 인스턴스를 임포트합니다.
from services.stt_service import stt_service

router = APIRouter()

@router.post("/ocr", response_model=dict)
async def ocr_image_endpoint(image_file: UploadFile = File(...)):
    image_bytes = await image_file.read()
    extracted_text = ocr_service.process_image_with_ocr(image_bytes)
    return {"text": extracted_text}

@router.post("/stt", response_model=dict)
async def stt_audio_endpoint(
    audio_file: UploadFile = File(...),
    channels: int = Form(1),
    language: str = Form("auto") # [수정] STT 언어 코드를 Form 데이터로 받음
):
    """
    오디오 파일, 채널 수, 언어 코드를 받아 STT를 수행합니다.
    """
    audio_bytes = await audio_file.read()

    # 수정된 STT 서비스의 transcribe 메서드를 호출합니다.
    extracted_text = await stt_service.transcribe(
        audio_bytes=audio_bytes,
        channels=channels,
        language=language
    )

    # 서비스에서 오류 발생 시 빈 문자열을 반환하므로, None 체크는 제거해도 됩니다.
    return {"text": extracted_text}