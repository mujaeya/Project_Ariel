# ariel_client/src/core/translation_worker.py (이 코드로 전체 교체)

import pandas as pd
from PySide6.QtCore import QObject, Slot, Signal, QRect, QLocale, QCoreApplication
from PIL import Image
import io
import pytesseract
import logging

from ..config_manager import ConfigManager
from ..mt_engine import MTEngine
from ..api_client import APIClient

logger = logging.getLogger(__name__)

DEEPL_TO_TESSERACT = {
    'EN': 'eng', 'KO': 'kor', 'JA': 'jpn', 'ZH': 'chi_sim',
    'DE': 'deu', 'FR': 'fra', 'ES': 'spa',
}

def aggregate_line_data(group):
    # ... (aggregate_line_data 함수는 변경 없음) ...
    text = ' '.join(group['text'].astype(str))
    conf = group['conf'].mean()
    x0 = group['left'].min(); y0 = group['top'].min()
    x1 = (group['left'] + group['width']).max()
    y1 = (group['top'] + group['height']).max()

    if x1 > x0 and y1 > y0:
        return pd.Series({'text': text, 'conf': conf, 'rect': QRect(x0, y0, x1 - x0, y1 - y0)})
    return None

class TranslationWorker(QObject):
    stt_translation_ready = Signal(str, str)
    ocr_patches_ready = Signal(list)
    error_occurred = Signal(str)
    
    stt_status_updated = Signal(str)
    ocr_status_updated = Signal(str)

    def __init__(self, config_manager: ConfigManager):
        super().__init__(None)
        self.config_manager = config_manager
        self._mt_engine = None
        self._api_client = None
        self._is_stt_processing = False
        logger.info("TranslationWorker 초기화 완료.")

    @property
    def mt_engine(self):
        if not self._mt_engine:
            logger.debug("MTEngine 인스턴스를 생성합니다.")
            self._mt_engine = MTEngine(self.config_manager)
        return self._mt_engine

    @property
    def api_client(self):
        if not self._api_client:
            api_url = self.config_manager.get("api_base_url")
            logger.debug(f"APIClient 인스턴스를 생성합니다. (URL: {api_url})")
            self._api_client = APIClient(base_url=api_url)
        return self._api_client
    
    def _resolve_target_language(self, lang_code_from_config: str) -> str:
        # ... (_resolve_target_language 함수는 변경 없음) ...
        if lang_code_from_config == "auto":
            sys_lang = QLocale.system().name().split('_')[0].upper()
            supported_langs = ["BG", "CS", "DA", "DE", "EL", "EN", "ES", "ET", "FI", "FR", "HU", "ID", "IT", "JA", "KO", "LT", "LV", "NB", "NL", "PL", "PT", "RO", "RU", "SK", "SL", "SV", "TR", "UK", "ZH"]
            return sys_lang if sys_lang in supported_langs else "EN"
        return lang_code_from_config.upper()

    @Slot(bytes, int)
    def process_stt_audio(self, audio_bytes: bytes, channels: int):
        if self._is_stt_processing:
            logger.debug("STT 처리 중... 새로운 오디오 요청을 무시합니다.")
            return

        self._is_stt_processing = True
        try:
            logger.info(f"STT 오디오 처리 시작 (크기: {len(audio_bytes)} bytes)")
            self.stt_status_updated.emit(self.tr("Converting voice to text..."))

            stt_source_lang = self.config_manager.get('stt_source_language', 'auto')
            stt_source_param = stt_source_lang if stt_source_lang != 'auto' else None
            
            # [스프린트 1 수정] api_client.stt는 이제 JSON(dict)를 반환합니다.
            stt_response = self.api_client.stt(audio_bytes, channels, language=stt_source_param)

            if not stt_response:
                logger.warning("STT API로부터 응답이 없습니다.")
                self.error_occurred.emit(self.tr("No response from STT service."))
                return

            original_text = stt_response.get("text", "")
            detected_lang = stt_response.get("language") # 예: "ko"

            # [핵심 수정] STT 결과가 비어 있거나 공백뿐인 경우, 여기서 처리를 완전히 중단합니다.
            if not original_text or not original_text.strip():
                logger.warning("STT 결과가 비어있어 처리를 중단합니다. (신호 방출 없음)")
                # 아무런 신호도 보내지 않고 조용히 종료합니다.
                return

            self.stt_status_updated.emit(self.tr("Translating text..."))
            target_lang_code = self._resolve_target_language(self.config_manager.get('stt_target_language', 'auto'))

            # [스프린트 1 수정] 지능적 번역: 감지된 언어와 목표 언어가 같으면 번역을 건너뜁니다.
            # DeepL 언어 코드는 대문자여야 합니다 (예: 'KO').
            if detected_lang and detected_lang.upper() == target_lang_code:
                logger.info(f"Source language ({detected_lang.upper()}) and target language ({target_lang_code}) are the same. Skipping translation.")
                translated_text = original_text
            else:
                translated_text = self.mt_engine.translate_text(original_text, stt_source_param, target_lang_code)

            if translated_text is None:
                self.error_occurred.emit(self.tr("STT translation failed."))
                return

            self.stt_translation_ready.emit(original_text, translated_text)
            
        except Exception as e:
            logger.error(f"STT 오디오 처리 중 예외 발생: {e}", exc_info=True)
            self.error_occurred.emit(f"STT Error: {e}")
            self.stt_status_updated.emit(self.tr("An error occurred."))
        finally:
            self.stt_status_updated.emit(self.tr("Listening..."))
            self._is_stt_processing = False

    @Slot(bytes)
    def process_ocr_image(self, image_bytes: bytes):
        # ... (process_ocr_image 함수는 변경 없음) ...
        try:
            ocr_source_lang_deepl = self.config_manager.get("ocr_source_language", "auto")
            tess_lang = DEEPL_TO_TESSERACT.get(ocr_source_lang_deepl, 'eng+kor') if ocr_source_lang_deepl != 'auto' else 'eng+kor'
            target_lang = self._resolve_target_language(self.config_manager.get('ocr_target_language', 'auto'))

            logger.info(f"OCR 이미지 처리 시작 (Tesseract lang: {tess_lang}, DeepL Target: {target_lang})")
            self.ocr_status_updated.emit(self.tr("Extracting text from image..."))

            image = Image.open(io.BytesIO(image_bytes))
            ocr_data = pytesseract.image_to_data(image, lang=tess_lang, output_type=pytesseract.Output.DATAFRAME)

            min_conf = self.config_manager.get("ocr_min_confidence", 30)
            ocr_data = ocr_data[ocr_data.conf > min_conf]

            if ocr_data.empty:
                logger.warning(f"OCR 결과, 신뢰도 {min_conf} 이상의 유효한 텍스트를 찾지 못했습니다.")
                self.ocr_patches_ready.emit([])
                self.ocr_status_updated.emit("")
                return

            line_data = ocr_data.groupby(['page_num', 'block_num', 'par_num', 'line_num']).apply(aggregate_line_data, include_groups=False).dropna().reset_index(drop=True)

            if line_data.empty:
                self.ocr_patches_ready.emit([])
                self.ocr_status_updated.emit("")
                return

            self.ocr_status_updated.emit(self.tr("Translating {n} lines...").format(n=len(line_data)))

            texts_to_translate = line_data['text'].tolist()
            source_lang_param = ocr_source_lang_deepl if ocr_source_lang_deepl != 'auto' else None
            translated_texts = self.mt_engine.translate_text(texts_to_translate, source_lang_param, target_lang)

            if not translated_texts:
                self.error_occurred.emit(self.tr("Translation failed. Check API key and usage."))
                return

            patches = [{'original': row['text'], 'translated': translated_texts[i], 'rect': row['rect']}
                       for i, row in line_data.iterrows() if i < len(translated_texts) and translated_texts[i]]

            self.ocr_patches_ready.emit(patches)
            self.ocr_status_updated.emit("")

        except Exception as e:
            logger.error(f"OCR 이미지 처리 중 예외 발생: {e}", exc_info=True)
            self.error_occurred.emit(f"OCR Error: {e}")

    def tr(self, text: str) -> str:
        return QCoreApplication.translate("TranslationWorker", text)