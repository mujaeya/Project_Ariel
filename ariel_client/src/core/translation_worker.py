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
            # Pandas is now a requirement, so we can use DATAFRAME
            ocr_data = pytesseract.image_to_data(image, lang='eng+jpn+kor', output_type=pytesseract.Output.DATAFRAME)
            ocr_data = ocr_data[ocr_data.conf > 50]

            if ocr_data.empty: return

            lines = ocr_data.groupby(['page_num', 'block_num', 'par_num', 'line_num'])['text'].apply(lambda x: ' '.join(map(str, x))).tolist()
            line_bounds = ocr_data.groupby(['page_num', 'block_num', 'par_num', 'line_num']).apply(
                lambda x: (
                    x['left'].min(),
                    x['top'].min(),
                    x['left'].max() + x['width'].max() - x['left'].min(),
                    x['top'].max() + x['height'].max() - x['top'].min()
                )
            ).tolist()

            full_text = "\n".join(lines)
            if not full_text.strip(): return
            
            target_lang = self.config_manager.get("target_languages", ["KO"])[0]
            # Use the multi-translate function for consistency
            translated_full = self.mt_engine.translate_text_multi(full_text, [target_lang])
            translated_lines = translated_full.get(target_lang, "").split('\n')
            
            patches_data = []
            for i, (x, y, w, h) in enumerate(line_bounds):
                if i < len(translated_lines) and i < len(lines):
                    absolute_rect = QRect(original_rect.x() + x, original_rect.y() + y, w, h)
                    
                    patch_info = {
                        "original": lines[i],
                        "translated": translated_lines[i],
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
            # The log shows "Missing pandas package", so we emit a specific error
            if "Missing pandas package" in str(e):
                 self.error_occurred.emit("OCR processing failed. The 'pandas' package is missing.")
            else:
                 self.error_occurred.emit("An error occurred during OCR processing.")