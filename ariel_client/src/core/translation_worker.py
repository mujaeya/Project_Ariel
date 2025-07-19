# ariel_client/src/core/translation_worker.py (수정 후)
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

# [추가] DeepL 언어 코드를 Tesseract 코드로 매핑
DEEPL_TO_TESSERACT = {
    'EN': 'eng', 'KO': 'kor', 'JA': 'jpn', 'ZH': 'chi_sim',
    'DE': 'deu', 'FR': 'fra', 'ES': 'spa',
    # 필요 시 다른 언어 추가
}

def aggregate_line_data(group):
    """Pandas 그룹의 텍스트를 합치고 경계 상자와 신뢰도를 계산합니다."""
    text = ' '.join(group['text'].astype(str))
    conf = group['conf'].mean()
    x0 = group['left'].min()
    y0 = group['top'].min()
    x1 = (group['left'] + group['width']).max()
    y1 = (group['top'] + group['height']).max()
    
    if x1 > x0 and y1 > y0:
        rect = QRect(x0, y0, x1 - x0, y1 - y0)
        return pd.Series({'text': text, 'conf': conf, 'rect': rect})
    return None

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
        if lang_code_from_config == "auto":
            sys_lang = QLocale.system().name().split('_')[0].upper()
            return sys_lang
        return lang_code_from_config.upper()

    @Slot(bytes, int) # [수정] 채널(int)도 함께 받도록 시그널 슬롯 변경
    def process_stt_audio(self, audio_bytes: bytes, channels: int):
        try:
            logger.info(f"STT 오디오 처리 시작 (크기: {len(audio_bytes)} bytes, 채널: {channels})")
            self.status_updated.emit("음성을 텍스트로 변환 중...")
            
            # [수정] API 호출 시 채널 정보 전달
            original_text = self.api_client.stt(audio_bytes, channels)
            
            if not original_text or not original_text.strip():
                logger.warning("STT 결과가 비어있습니다.")
                self.status_updated.emit("음성 듣는 중...")
                return

            self.status_updated.emit("텍스트 번역 중...")

            target_lang_code = self._resolve_target_language(self.config_manager.get('stt_target_language', 'auto'))
            source_lang_code = self.config_manager.get('stt_source_language', 'auto')
            source_lang_param = source_lang_code if source_lang_code != 'auto' else None
            
            translated_text = self.mt_engine.translate_text(original_text, source_lang_param, target_lang_code)

            if translated_text is None:
                 self.error_occurred.emit("STT 번역에 실패했습니다.")
                 return
            
            self.stt_translation_ready.emit(original_text, {target_lang_code: translated_text})
            self.status_updated.emit("음성 듣는 중...")

        except Exception as e:
            logger.error(f"STT 오디오 처리 중 예외 발생: {e}", exc_info=True)
            self.error_occurred.emit(f"STT Error: {e}")

    @Slot(bytes)
    def process_ocr_image(self, image_bytes: bytes):
        try:
            # [수정] OCR 원본 언어 설정 가져오기
            ocr_source_lang_deepl = self.config_manager.get("ocr_source_language", "auto")
            
            # [수정] Tesseract가 사용할 언어 코드 결정
            if ocr_source_lang_deepl != 'auto':
                tess_lang = DEEPL_TO_TESSERACT.get(ocr_source_lang_deepl, 'eng+kor')
            else:
                tess_lang = 'eng+kor' # 자동 감지 시 기본값

            target_lang = self._resolve_target_language(self.config_manager.get('ocr_target_language', 'auto'))
            
            logger.info(f"OCR 이미지 처리 시작 (Tesseract lang: {tess_lang}, DeepL Target: {target_lang})")
            self.status_updated.emit("이미지에서 텍스트 추출 중...")

            image = Image.open(io.BytesIO(image_bytes))
            
            # [수정] 동적으로 결정된 언어 코드로 Tesseract 호출
            ocr_data = pytesseract.image_to_data(image, lang=tess_lang, output_type=pytesseract.Output.DATAFRAME)
            
            min_conf = self.config_manager.get("ocr_min_confidence", 30)
            ocr_data = ocr_data[ocr_data.conf > min_conf]

            if ocr_data.empty:
                logger.warning(f"OCR 결과, 신뢰도 {min_conf} 이상의 유효한 텍스트를 찾지 못했습니다.")
                self.ocr_patches_ready.emit([])
                return

            line_data = ocr_data.groupby(['page_num', 'block_num', 'par_num', 'line_num']).apply(aggregate_line_data).dropna().reset_index(drop=True)

            if line_data.empty:
                self.ocr_patches_ready.emit([])
                return
            
            self.status_updated.emit(f"{len(line_data)}줄 번역 중...")

            texts_to_translate = line_data['text'].tolist()
            source_lang_param = ocr_source_lang_deepl if ocr_source_lang_deepl != 'auto' else None
            
            translated_texts = self.mt_engine.translate_text(texts_to_translate, source_lang_param, target_lang)

            if not translated_texts:
                self.error_occurred.emit("번역에 실패했습니다. API 키와 사용량을 확인하세요.")
                return

            patches = [{'original': row['text'], 'translated': translated_texts[i], 'rect': row['rect']}
                       for i, row in line_data.iterrows() if i < len(translated_texts) and translated_texts[i]]
            
            self.ocr_patches_ready.emit(patches)
            self.status_updated.emit("")

        except Exception as e:
            logger.error(f"OCR 이미지 처리 중 예외 발생: {e}", exc_info=True)
            self.error_occurred.emit(f"OCR Error: {e}")