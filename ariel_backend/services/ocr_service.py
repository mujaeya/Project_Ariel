# ariel_backend/services/ocr_service.py
import pytesseract
from PIL import Image
import io
import logging

def process_image_with_ocr(image_bytes: bytes) -> str:
    """
    Bytes 형식의 이미지를 받아 OCR을 수행하고 텍스트를 반환합니다.
    """
    try:
        image = Image.open(io.BytesIO(image_bytes))
        # 필요 시, 여기서 이미지 전처리(흑백 변환 등)를 수행하면 인식률이 향상됩니다.
        text = pytesseract.image_to_string(image, lang='kor+eng')
        logging.info(f"OCR 추출 성공: {text.strip()}")
        return text.strip()
    except Exception as e:
        logging.error(f"OCR 처리 중 오류 발생: {e}", exc_info=True)
        return ""