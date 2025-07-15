# ariel_client/src/core/translation_worker.py (이 코드로 전체 교체)
import pandas as pd
from PySide6.QtCore import QObject, Slot, Signal, QRect, QLocale
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
    return pd.Series({'text': text, 'x0': x0, 'y0': y0, 'x1': x1, 'y1': y1})

class TranslationWorker(QObject):
    stt_translation_ready = Signal(str, dict)
    ocr_patches_ready = Signal(list)
    error_occurred = Signal(str)
    status_updated = Signal(str)

    def __init__(self, config_manager: ConfigManager, parent: QObject | None = None):
        super().__init__(parent)
        self.config_manager = config_manager
        self._mt_engine = None
        self._api_client = None

    @property
    def mt_engine(self):
        if not self._mt_engine:
            self._mt_engine = MTEngine(self.config_manager)
        return self._mt_engine

    @property
    def api_client(self):
        if not self._api_client:
            self._api_client = APIClient(base_url=self.config_manager.get("api_base_url"))
        return self._api_client

    def _resolve_target_language(self, lang_code_from_config: str) -> str:
        """[추가] 'auto'로 설정된 대상 언어를 시스템 언어 코드로 변환합니다."""
        if lang_code_from_config == "auto":
            # 예: 'ko_KR' -> 'KO', 'en_US' -> 'EN'
            sys_lang = QLocale.system().name().split('_')[0].upper()
            logger.debug(f"Target language 'auto' detected. Resolved to system language: {sys_lang}")
            # DeepL free API는 대부분 2자리 코드를 사용합니다. (EN, DE, KO 등)
            return sys_lang
        return lang_code_from_config

    @Slot(bytes)
    def process_stt_audio(self, audio_bytes: bytes):
        try:
            self.status_updated.emit("음성을 텍스트로 변환 중...")
            original_text = self.api_client.stt(audio_bytes, self.config_manager.get("stt_model", "whisper-1"))
            if not original_text or not original_text.strip():
                return

            self.status_updated.emit("텍스트 번역 중...")

            # [수정] 대상 언어가 'auto'일 경우 시스템 언어로 변환하는 로직 추가
            raw_target_lang = self.config_manager.get('stt_target_language', 'auto')
            target_lang_code = self._resolve_target_language(raw_target_lang)
            source_lang_code = self.config_manager.get('stt_source_language', 'auto')

            if not target_lang_code:
                self.error_occurred.emit(f"STT: 유효하지 않은 대상 언어 코드입니다.")
                return

            translated_text = self.mt_engine.translate_text(original_text, source_lang_code, target_lang_code)

            if translated_text is None:
                 self.error_occurred.emit("STT 번역에 실패했습니다.")
                 return

            self.stt_translation_ready.emit(original_text, {target_lang_code: translated_text})
            self.status_updated.emit("음성 듣는 중...")
        except Exception as e:
            logger.error(f"STT 오디오 처리 중 오류: {e}", exc_info=True)
            self.error_occurred.emit(f"STT 처리 중 오류 발생: {e}")

    @Slot(bytes, QRect)
    def process_ocr_image(self, image_bytes: bytes, original_rect: QRect):
        try:
            # [수정] 대상 언어가 'auto'일 경우 시스템 언어로 변환하는 로직 추가
            raw_target_lang = self.config_manager.get('ocr_target_language', 'auto')
            target_lang_code = self._resolve_target_language(raw_target_lang)
            source_lang_code = self.config_manager.get('ocr_source_language', 'auto')

            if not target_lang_code:
                self.error_occurred.emit(f"OCR: 유효하지 않은 대상 언어 코드입니다.")
                return

            image = Image.open(io.BytesIO(image_bytes))
            tess_langs = 'eng+jpn+kor'
            ocr_data = pytesseract.image_to_data(image, lang=tess_langs, output_type=pytesseract.Output.DATAFRAME)
            ocr_data = ocr_data[ocr_data.conf > 50]

            if ocr_data.empty: return

            line_data = ocr_data.groupby(['page_num', 'block_num', 'par_num', 'line_num']).apply(aggregate_line_data).reset_index(drop=True)
            if line_data.empty: return

            patches_data = []
            for _, row in line_data.iterrows():
                text_to_translate = row['text']
                if text_to_translate and not text_to_translate.isspace():
                    translated_text = self.mt_engine.translate_text(text_to_translate, source_lang_code, target_lang_code)
                    if translated_text:
                        patch_rect = QRect(int(row['x0']), int(row['y0']), int(row['x1'] - row['x0']), int(row['y1'] - row['y0']))
                        absolute_rect = patch_rect.translated(original_rect.topLeft())
                        patches_data.append({
                            "original": text_to_translate,
                            "translated": translated_text,
                            "rect": absolute_rect
                        })
            if patches_data:
                self.ocr_patches_ready.emit(patches_data)

        except Exception as e:
            logger.error(f"OCR 이미지 처리 중 오류: {e}", exc_info=True)
            self.error_occurred.emit(f"OCR 처리 중 오류 발생: {e}")