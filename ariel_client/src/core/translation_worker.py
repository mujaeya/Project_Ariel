# ariel_client/src/core/translation_worker.py (이 코드로 전체 교체)
import pandas as pd
from PySide6.QtCore import QObject, Slot, Signal, QRect
from PySide6.QtGui import QPixmap, QScreen
from PIL import Image
import io
import pytesseract
import logging

from ..config_manager import ConfigManager
from ..mt_engine import MTEngine
from ..api_client import APIClient 
# [핵심 수정] 언어 코드 변환을 위해 상수 딕셔너리 임포트
from ..gui.setup_window import SUPPORTED_DEEPL_LANGUAGES, SUPPORTED_LANGUAGES

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
    # [핵심 수정] OCR 관련 시그널을 하나로 통일하여 데이터 흐름을 명확히 함
    ocr_patches_ready = Signal(list)   
    error_occurred = Signal(str)
    status_updated = Signal(str)

    def __init__(self, config_manager: ConfigManager, parent: QObject | None = None):
        super().__init__(parent)
        self.config_manager = config_manager
        
        # [개선] MTEngine, APIClient는 필요 시점에 생성되도록 변경 (lazy-loading)
        self._mt_engine = None
        self._api_client = None

        # [핵심 수정] 언어 이름 -> 코드 변환을 위한 역방향 딕셔너리 생성
        self.lang_name_to_code = {name: code for name, code in SUPPORTED_DEEPL_LANGUAGES.items()}
        self.ui_lang_name_to_code = {name: code for name, code in SUPPORTED_LANGUAGES.items()}

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

    @Slot(bytes)
    def process_stt_audio(self, audio_bytes: bytes):
        try:
            self.status_updated.emit("음성을 텍스트로 변환 중...")
            original_text = self.api_client.stt(audio_bytes, self.config_manager.get("stt_model", "whisper-1"))
            if not original_text or not original_text.strip():
                self.status_updated.emit("음성이 감지되지 않았습니다.")
                return

            self.status_updated.emit("텍스트 번역 중...")

            # [핵심 수정] 설정에 저장된 '언어 이름'을 '언어 코드'로 변환
            target_lang_name = self.config_manager.get('stt_target_lang', 'Korean')
            target_lang_code = self.lang_name_to_code.get(target_lang_name)
            
            if not target_lang_code:
                self.error_occurred.emit(f"STT: 유효하지 않은 대상 언어 '{target_lang_name}'")
                return

            translated_text = self.mt_engine.translate_text(original_text, None, target_lang_code)
            
            if translated_text is None:
                 self.error_occurred.emit("STT 번역에 실패했습니다.")
                 return
            
            self.stt_translation_ready.emit(original_text, {target_lang_code: translated_text})
            self.status_updated.emit("음성 듣는 중...")
        except Exception as e:
            logger.error(f"STT 오디오 처리 중 오류: {e}", exc_info=True)
            self.error_occurred.emit("STT 처리 중 오류가 발생했습니다.")

    @Slot(bytes, QRect)
    def process_ocr_image(self, image_bytes: bytes, original_rect: QRect):
        try:
            ocr_mode = self.config_manager.get('ocr_mode', 'Standard Overlay')
            
            # [핵심 수정] OCR 언어 이름 -> 코드로 변환
            source_lang_name = self.config_manager.get('ocr_source_lang', 'Auto Detect')
            target_lang_name = self.config_manager.get('ocr_target_lang', 'Korean')
            source_lang_code = self.lang_name_to_code.get(source_lang_name)
            target_lang_code = self.lang_name_to_code.get(target_lang_name)

            if not target_lang_code:
                self.error_occurred.emit(f"OCR: 유효하지 않은 대상 언어 '{target_lang_name}'")
                return

            image = Image.open(io.BytesIO(image_bytes))
            # [개선] tesseract가 사용할 언어 코드를 동적으로 설정 (tesseract는 3자리 코드 사용)
            tess_langs = 'eng+jpn+kor' # 기본값, 추후 설정 기반으로 변경 가능
            ocr_data = pytesseract.image_to_data(image, lang=tess_langs, output_type=pytesseract.Output.DATAFRAME)
            ocr_data = ocr_data[ocr_data.conf > 50]

            if ocr_data.empty:
                logger.info("OCR: 텍스트를 감지하지 못했습니다.")
                return

            if ocr_mode == 'Standard Overlay':
                full_text = " ".join(ocr_data['text'].dropna().astype(str))
                if full_text.strip():
                    translated_text = self.mt_engine.translate_text(full_text, source_lang_code, target_lang_code)
                    if translated_text:
                        # [핵심 수정] 단일 오버레이 모드도 '패치' 데이터 형식으로 통일하여 전달
                        patch_data = [{
                            "original": full_text,
                            "translated": translated_text,
                            "rect": original_rect # 전체 캡처 영역을 그대로 사용
                        }]
                        self.ocr_patches_ready.emit(patch_data)
            
            elif ocr_mode == 'Patch Mode':
                line_data = ocr_data.groupby(['page_num', 'block_num', 'par_num', 'line_num']).apply(aggregate_line_data).reset_index(drop=True)
                if line_data.empty: return

                patches_data = []
                for _, row in line_data.iterrows():
                    text_to_translate = row['text']
                    if text_to_translate and not text_to_translate.isspace():
                        translated_text = self.mt_engine.translate_text(text_to_translate, source_lang_code, target_lang_code)
                        if translated_text:
                            # 텍스트 블록의 상대 좌표를 전체 화면 기준 절대 좌표로 변환
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
            self.error_occurred.emit("OCR 처리 중 오류가 발생했습니다.")