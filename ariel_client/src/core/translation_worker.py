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

def aggregate_line_data(group):
    """Pandas 그룹의 텍스트를 합치고 경계 상자와 신뢰도를 계산합니다."""
    text = ' '.join(group['text'].astype(str))
    conf = group['conf'].mean()
    x0 = group['left'].min()
    y0 = group['top'].min()
    x1 = (group['left'] + group['width']).max()
    y1 = (group['top'] + group['height']).max()
    
    # 유효한 사각형인지 확인
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
        """MTEngine 인스턴스를 지연 로딩합니다."""
        if not self._mt_engine:
            logger.debug("MTEngine 인스턴스를 생성합니다.")
            self._mt_engine = MTEngine(self.config_manager)
        return self._mt_engine

    @property
    def api_client(self):
        """APIClient 인스턴스를 지연 로딩합니다."""
        if not self._api_client:
            api_url = self.config_manager.get("api_base_url")
            logger.debug(f"APIClient 인스턴스를 생성합니다. (URL: {api_url})")
            self._api_client = APIClient(base_url=api_url)
        return self._api_client

    def _resolve_target_language(self, lang_code_from_config: str) -> str:
        """'auto'로 설정된 대상 언어를 시스템 언어 코드로 변환합니다."""
        if lang_code_from_config == "auto":
            sys_lang = QLocale.system().name().split('_')[0].upper()
            logger.debug(f"대상 언어 'auto'를 시스템 언어 '{sys_lang}'로 확인했습니다.")
            return sys_lang
        return lang_code_from_config.upper()

    @Slot(bytes)
    def process_stt_audio(self, audio_bytes: bytes):
        try:
            model = self.config_manager.get("stt_model", "whisper-1")
            logger.info(f"STT 오디오 처리 시작 (크기: {len(audio_bytes)} bytes, 모델: {model})")
            self.status_updated.emit("음성을 텍스트로 변환 중...")
            
            original_text = self.api_client.stt(audio_bytes, model)
            if not original_text or not original_text.strip():
                logger.warning("STT 결과가 비어있습니다.")
                self.status_updated.emit("음성 듣는 중...")
                return

            logger.info(f"STT 변환 결과: '{original_text}'")
            self.status_updated.emit("텍스트 번역 중...")

            target_lang_code = self._resolve_target_language(self.config_manager.get('stt_target_language', 'auto'))
            source_lang_code = self.config_manager.get('stt_source_language', 'auto')

            # [수정] 'auto' 소스 언어를 None으로 변환하여 API 오류 방지
            source_lang_param = source_lang_code if source_lang_code != 'auto' else None
            
            logger.debug(f"STT 번역 요청: '{original_text}' ({source_lang_param or 'auto'} -> {target_lang_code})")
            translated_text = self.mt_engine.translate_text(original_text, source_lang_param, target_lang_code)

            if translated_text is None:
                 logger.error("STT 번역 결과가 None입니다.")
                 self.error_occurred.emit("STT 번역에 실패했습니다.")
                 return
            
            logger.info(f"STT 번역 성공: '{translated_text}'")
            self.stt_translation_ready.emit(original_text, {target_lang_code: translated_text})
            self.status_updated.emit("음성 듣는 중...")

        except Exception as e:
            logger.error(f"STT 오디오 처리 중 예외 발생: {e}", exc_info=True)
            self.error_occurred.emit(f"STT Error: {e}")

    @Slot(bytes)
    def process_ocr_image(self, image_bytes: bytes):
        try:
            source_lang = self.config_manager.get("ocr_source_lang", "auto")
            target_lang = self._resolve_target_language(self.config_manager.get('ocr_target_language', 'auto'))
            
            logger.info(f"OCR 이미지 데이터 수신 (크기: {len(image_bytes)} bytes), Lang: {source_lang}->{target_lang}")
            self.status_updated.emit("이미지에서 텍스트 추출 중...")

            image = Image.open(io.BytesIO(image_bytes))
            
            # Tesseract에 여러 언어를 동시에 지정하여 검출률 향상
            tess_langs = 'eng+jpn+kor' 
            ocr_data = pytesseract.image_to_data(image, lang=tess_langs, output_type=pytesseract.Output.DATAFRAME)
            
            min_conf = self.config_manager.get("ocr_min_confidence", 30)
            ocr_data = ocr_data[ocr_data.conf > min_conf]

            if ocr_data.empty:
                logger.warning(f"OCR 결과, 신뢰도 {min_conf} 이상의 유효한 텍스트를 찾지 못했습니다.")
                self.status_updated.emit("")
                self.ocr_patches_ready.emit([]) # 빈 리스트 방출
                return

            # 줄 단위로 텍스트 묶기
            line_data = ocr_data.groupby(['page_num', 'block_num', 'par_num', 'line_num']).apply(aggregate_line_data).dropna().reset_index(drop=True)

            if line_data.empty:
                logger.warning("신뢰도 필터링 후 남은 텍스트가 없습니다.")
                self.status_updated.emit("")
                self.ocr_patches_ready.emit([]) # 빈 리스트 방출
                return
            
            logger.info(f"OCR 성공. {len(line_data)}개의 텍스트 라인 감지.")
            self.status_updated.emit(f"{len(line_data)}줄 번역 중...")

            texts_to_translate = line_data['text'].tolist()
            
            # [수정] 'auto' 소스 언어를 None으로 변환하여 API 오류 방지
            source_lang_param = source_lang if source_lang != 'auto' else None
            
            logger.debug(f"번역 요청: {len(texts_to_translate)}개 텍스트, {source_lang_param or 'auto'} -> {target_lang}")
            translated_texts = self.mt_engine.translate_text(texts_to_translate, source_lang_param, target_lang)

            if not translated_texts:
                logger.error("번역 엔진이 결과를 반환하지 않았습니다.")
                self.error_occurred.emit("번역에 실패했습니다. API 키와 사용량을 확인하세요.")
                return

            patches = []
            for index, row in line_data.iterrows():
                if index < len(translated_texts) and translated_texts[index]:
                    patches.append({
                        'original': row['text'],
                        'translated': translated_texts[index],
                        'rect': row['rect']
                    })
            
            logger.info(f"{len(patches)}개의 번역 패치 생성 완료.")
            self.ocr_patches_ready.emit(patches)
            self.status_updated.emit("") # 작업 완료 후 상태 메시지 초기화

        except Exception as e:
            logger.error(f"OCR 이미지 처리 중 예외 발생: {e}", exc_info=True)
            self.error_occurred.emit(f"OCR Error: {e}")