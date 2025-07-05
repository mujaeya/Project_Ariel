import logging
import numpy as np
from PySide6.QtCore import QObject, Signal, Slot, QRect
import pytesseract

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
        self.config = config_manager.get_active_profile()
        self.api_client = APIClient(base_url=self.config.get("api_base_url"))
        self.mt_engine = MTEngine(self.config)

    @Slot(bytes)
    def process_stt_audio(self, audio_bytes: bytes):
        try:
            self.status_updated.emit("음성을 텍스트로 변환 중...")
            original_text = self.api_client.stt(audio_bytes, self.config.get("stt_model", "whisper-1"))
            if not original_text: return
            self.status_updated.emit("텍스트 번역 중...")
            translated_results = {}
            for lang in self.config.get("target_languages", ["KO"]):
                translated_results[lang] = self.mt_engine.translate(original_text, lang)
            self.stt_translation_ready.emit(original_text, translated_results)
        except Exception as e:
            logger.error(f"STT 오디오 처리 중 오류: {e}", exc_info=True)
            self.error_occurred.emit("STT 처리 중 오류가 발생했습니다.")

    @Slot(np.ndarray, QRect)
    def process_ocr_image(self, image: np.ndarray, original_rect: QRect):
        try:
            # Tesseract를 사용하여 이미지에서 텍스트 데이터 추출
            ocr_data = pytesseract.image_to_data(image, lang='eng+jpn+kor', output_type=pytesseract.Output.DATAFRAME)
            # 신뢰도가 50 이상인 데이터만 필터링
            ocr_data = ocr_data[ocr_data.conf > 50]
            if ocr_data.empty: return

            # 텍스트 라인별로 그룹화
            lines = ocr_data.groupby(['page_num', 'block_num', 'par_num', 'line_num'])['text'].apply(lambda x: ' '.join(list(x))).tolist()
            # 각 라인의 경계 상자 계산
            line_bounds = ocr_data.groupby(['page_num', 'block_num', 'par_num', 'line_num']).apply(
                lambda x: (x.left.min(), x.top.min(), x.width.sum(), x.height.max())
            ).tolist()

            # 전체 텍스트를 한 번에 번역
            full_text = "\n".join(lines)
            target_lang = self.config.get("target_languages", ["KO"])[0]
            translated_text = self.mt_engine.translate(full_text, target_lang)
            translated_lines = translated_text.split('\n')
            
            # 번역된 각 라인을 원래 위치에 매핑하여 패치 데이터 생성
            patches_data = []
            for i, (x, y, w, h) in enumerate(line_bounds):
                if i < len(translated_lines) and i < len(lines):
                    # QRect(캡처 영역 시작 x + 텍스트 x, 캡처 영역 시작 y + 텍스트 y, 너비, 높이)
                    absolute_rect = QRect(original_rect.x() + x, original_rect.y() + y, w, h)
                    
                    # 원문과 번역문을 함께 담는 딕셔너리로 구조 변경
                    patch_info = {
                        "original": lines[i],
                        "translated": translated_lines[i],
                        "rect": absolute_rect
                    }
                    patches_data.append(patch_info)
                    
            if patches_data:
                self.ocr_translation_ready.emit(patches_data)
        except Exception as e:
            logger.error(f"OCR 이미지 처리 중 오류: {e}", exc_info=True)
            self.error_occurred.emit("OCR 처리 중 오류가 발생했습니다.")