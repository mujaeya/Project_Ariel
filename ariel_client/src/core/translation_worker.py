import pandas as pd
from PySide6.QtCore import QObject, Slot, Signal, QRect
from PySide6.QtGui import QPixmap
from PIL import Image
import io
import pytesseract
import logging

from ..config_manager import ConfigManager
from ..mt_engine import MTEngine
from ..api_client import APIClient 

logger = logging.getLogger(__name__)

def aggregate_line_data(group):
    text = ' '.join(group['text'].astype(str))
    
    x0 = group['left'].min()
    y0 = group['top'].min()
    x1 = (group['left'] + group['width']).max()
    y1 = (group['top'] + group['height']).max()
    
    return pd.Series({
        'text': text,
        'x0': x0,
        'y0': y0,
        'x1': x1,
        'y1': y1
    })


class TranslationWorker(QObject):
    # [수정] 시그널 이름을 tray_icon.py에서 사용하는 이름과 일치시키고 타입을 정확히 명시합니다.
    stt_translation_ready = Signal(str, dict)
    ocr_translation_ready = Signal(str, str)  
    ocr_patches_ready = Signal(list)   
    error_occurred = Signal(str)
    
    # [추가] 코드 내에서 사용되고 있지만 정의가 누락된 시그널을 추가합니다.
    status_updated = Signal(str)

    def __init__(self, config_manager: ConfigManager, parent: QObject | None = None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.mt_engine = MTEngine(self.config_manager)
        self.api_client = APIClient(base_url=self.config_manager.get("api_base_url"))

    @Slot(bytes)
    def process_stt_audio(self, audio_bytes: bytes):
        try:
            self.status_updated.emit("Converting speech to text...")
            # [수정] stt 메서드 호출 시 model 인자 전달 부분은 api_client 구현에 따라 달라질 수 있음 (원본 유지)
            original_text = self.api_client.stt(audio_bytes, self.config_manager.get("stt_model", "whisper-1"))
            if not original_text or not original_text.strip():
                self.status_updated.emit("No speech detected.")
                return

            self.status_updated.emit("Translating text...")
            target_langs = self.config_manager.get("target_languages", ["KO"])
            translated_results = self.mt_engine.translate_text_multi(original_text, target_langs)
            
            if not any(translated_results.values()):
                 # [수정] 정의된 시그널 이름으로 emit 호출
                 self.error_occurred.emit("Translation failed for all languages.")
                 return
            
            # [수정] 정의된 시그널 이름과 타입에 맞게 emit 호출
            self.stt_translation_ready.emit(original_text, translated_results)
            self.status_updated.emit("Listening for voice...") # Reset status
        except Exception as e:
            logger.error(f"Error processing STT audio: {e}", exc_info=True)
            # [수정] 정의된 시그널 이름으로 emit 호출
            self.error_occurred.emit("An error occurred during STT processing.")

    @Slot(bytes, QRect)
    def process_ocr_image(self, image_bytes: bytes, original_rect: QRect):
        try:
            ocr_mode = self.config_manager.get('ocr_mode', 'Standard Overlay')
            source_lang = self.config_manager.get('ocr_source_lang', 'Auto Detect')
            target_lang = self.config_manager.get('ocr_target_lang', 'Korean')

            image = Image.open(io.BytesIO(image_bytes))
            # [참고] tesseract 언어팩(eng, jpn, kor)이 설치되어 있어야 합니다.
            ocr_data = pytesseract.image_to_data(image, lang='eng+jpn+kor', output_type=pytesseract.Output.DATAFRAME)
            ocr_data = ocr_data[ocr_data.conf > 50]

            if ocr_data.empty:
                logger.info("OCR: No text detected.")
                return

            if ocr_mode == 'Standard Overlay':
                full_text = " ".join(ocr_data['text'].dropna().astype(str))
                if full_text.strip():
                    translated_text = self.mt_engine.translate_text(full_text, source_lang, target_lang)
                    if translated_text:
                        # [수정] ocr_result_ready -> ocr_translation_ready 로 이름 일관성 확보
                        self.ocr_translation_ready.emit(full_text, translated_text)
            
            elif ocr_mode == 'Patch Mode':
                line_data = ocr_data.groupby(['page_num', 'block_num', 'par_num', 'line_num']).apply(aggregate_line_data).reset_index(drop=True)
                if line_data.empty: return

                patches_data = []
                for idx, row in line_data.iterrows():
                    text_to_translate = row['text']
                    if text_to_translate and not text_to_translate.isspace():
                        translated_text = self.mt_engine.translate_text(text_to_translate, source_lang, target_lang)
                        if translated_text:
                            rect = QRect(int(row['x0']), int(row['y0']), int(row['x1'] - row['x0']), int(row['y1'] - row['y0']))
                            patches_data.append({
                                "original": text_to_translate,
                                "translated": translated_text,
                                "rect": rect.translated(original_rect.topLeft())
                            })
                if patches_data:
                    self.ocr_patches_ready.emit(patches_data)

        except Exception as e:
            logger.error(f"OCR image processing error: {e}", exc_info=True)
            # [수정] 정의된 시그널 이름으로 emit 호출
            self.error_occurred.emit("An error occurred during OCR processing.")