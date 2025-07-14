import logging
import numpy as np
import pandas as pd
from PySide6.QtCore import QObject, Signal, Slot, QRect
import pytesseract
from PIL import Image
import io

from ..api_client import APIClient
from ..mt_engine import MTEngine

logger = logging.getLogger(__name__)

def aggregate_line_data(group: pd.DataFrame) -> pd.Series:
    """
    [핵심 수정] OCR 데이터 그룹을 받아 경계 상자와 텍스트를 계산하고,
    안정적인 pandas.Series 객체로 반환합니다.
    """
    x0 = group['left'].min()
    y0 = group['top'].min()
    # 경계는 각 단어의 오른쪽 끝(left+width)과 아래쪽 끝(top+height) 중 가장 큰 값으로 계산합니다.
    x1 = (group['left'] + group['width']).max()
    y1 = (group['top'] + group['height']).max()
    
    # 단어(text)들을 공백으로 연결하여 한 줄의 문장을 만듭니다.
    text = ' '.join(group['text'].astype(str))
    
    return pd.Series([x0, y0, x1, y1, text], index=['x0', 'y0', 'x1', 'y1', 'text'])


class TranslationWorker(QObject):
    stt_translation_ready = Signal(str, dict)
    ocr_translation_ready = Signal(list)
    error_occurred = Signal(str)
    status_updated = Signal(str)

    def __init__(self, config_manager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.api_client = APIClient(base_url=self.config_manager.get("api_base_url"))
        self.mt_engine = MTEngine(config_manager)

    @Slot(bytes)
    def process_stt_audio(self, audio_bytes: bytes):
        try:
            self.status_updated.emit("Converting speech to text...")
            original_text = self.api_client.stt(audio_bytes, self.config_manager.get("stt_model", "whisper-1"))
            if not original_text.strip():
                self.status_updated.emit("No speech detected.")
                return

            self.status_updated.emit("Translating text...")
            target_langs = self.config_manager.get("target_languages", ["KO"])
            translated_results = self.mt_engine.translate_text_multi(original_text, target_langs)
            
            if not any(translated_results.values()):
                 self.error_occurred.emit("Translation failed for all languages.")
                 return

            self.stt_translation_ready.emit(original_text, translated_results)
            self.status_updated.emit("Listening for voice...") # Reset status
        except Exception as e:
            logger.error(f"Error processing STT audio: {e}", exc_info=True)
            self.error_occurred.emit("An error occurred during STT processing.")

    @Slot(bytes, QRect)
    def process_ocr_image(self, image_bytes: bytes, original_rect: QRect):
        try:
            image = Image.open(io.BytesIO(image_bytes))
            ocr_data = pytesseract.image_to_data(image, lang='eng+jpn+kor', output_type=pytesseract.Output.DATAFRAME)
            
            # 신뢰도 50 이상인 단어만 필터링
            ocr_data = ocr_data[ocr_data.conf > 50]

            if ocr_data.empty: return

            # [핵심 수정] 라인별로 텍스트와 경계를 한 번에 계산
            line_data = ocr_data.groupby(['page_num', 'block_num', 'par_num', 'line_num']).apply(aggregate_line_data).reset_index(drop=True)

            if line_data.empty or line_data['text'].str.strip().eq('').all():
                return

            texts_to_translate = line_data['text'].tolist()
            target_lang = self.config_manager.get("target_languages", ["KO"])[0]
            
            # 텍스트 리스트를 번역
            translated_texts = self.mt_engine.translate_text(texts_to_translate, target_lang)
            
            patches_data = []
            for idx, row in line_data.iterrows():
                if idx < len(translated_texts):
                    # 계산된 좌표로 QRect 생성
                    width = row['x1'] - row['x0']
                    height = row['y1'] - row['y0']
                    patch_rect = QRect(int(row['x0']), int(row['y0']), int(width), int(height))
                    
                    # 스크린샷 영역의 시작점을 더해 절대 좌표로 변환
                    absolute_rect = patch_rect.translated(original_rect.topLeft())
                    
                    patch_info = {
                        "original": row['text'],
                        "translated": translated_texts[idx],
                        "rect": absolute_rect
                    }
                    patches_data.append(patch_info)
                    
            if patches_data:
                self.ocr_translation_ready.emit(patches_data)

        except pytesseract.TesseractNotFoundError:
            logger.error("Tesseract is not installed or it's not in your PATH.")
            self.error_occurred.emit("Tesseract OCR is not installed.")
        except Exception as e:
            logger.error(f"Error processing OCR image: {e}", exc_info=True)
            if "Missing pandas package" in str(e):
                 self.error_occurred.emit("OCR processing failed. The 'pandas' package is missing.")
            else:
                 self.error_occurred.emit("An error occurred during OCR processing.")