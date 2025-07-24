# ariel_client/src/core/translation_worker.py (이 코드로 전체 교체)
import pandas as pd
from PySide6.QtCore import QObject, Slot, Signal, QRect, QLocale, QCoreApplication
import logging

from ..config_manager import ConfigManager
from ..mt_engine import MTEngine
from ..api_client import APIClient

logger = logging.getLogger(__name__)

class TranslationWorker(QObject):
    stt_chunk_translated = Signal(str, str)
    ocr_patches_ready = Signal(list)
    error_occurred = Signal(str)
    
    stt_status_updated = Signal(str)
    ocr_status_updated = Signal(str)

    def __init__(self, config_manager: ConfigManager):
        super().__init__(None)
        self.config_manager = config_manager
        self._mt_engine = None
        self._api_client = None
        
        self.is_stt_enabled = False
        self.current_stt_language = "auto"

        logger.info("TranslationWorker 초기화 완료 (실시간 청크 방식).")

    @property
    def mt_engine(self):
        if not self._mt_engine:
            self._mt_engine = MTEngine(self.config_manager)
        return self._mt_engine

    @property
    def api_client(self):
        if not self._api_client:
            api_url = self.config_manager.get("api_base_url", "http://127.0.0.1:8000")
            self._api_client = APIClient(base_url=api_url)
        return self._api_client
    
    @Slot(bool)
    def set_stt_enabled(self, enabled: bool):
        self.is_stt_enabled = enabled
        status = self.tr("Enabled") if enabled else self.tr("Disabled")
        logger.info(f"TranslationWorker STT status changed to: {status}")

    @Slot(str)
    def set_stt_language(self, language: str):
        self.current_stt_language = language
        logger.info(f"TranslationWorker STT language set to: {language}")

    def _resolve_target_language(self, lang_code_from_config: str) -> str:
        if lang_code_from_config == "auto":
            sys_lang = QLocale.system().name().split('_')[0].upper()
            supported_langs = ["BG", "CS", "DA", "DE", "EL", "EN", "ES", "ET", "FI", "FR", "HU", "ID", "IT", "JA", "KO", "LT", "LV", "NB", "NL", "PL", "PT", "RO", "RU", "SK", "SL", "SV", "TR", "UK", "ZH"]
            return sys_lang if sys_lang in supported_langs else "EN"
        return lang_code_from_config.upper()

    @Slot(bytes)
    def process_stt_chunk(self, audio_chunk: bytes):
        if not self.is_stt_enabled:
            return

        if not self.api_client:
            logger.error("API 클라이언트가 초기화되지 않았습니다.")
            return

        try:
            # [핵심 수정] ConfigManager에서 model_size와 client_id를 가져옴
            model_size = self.config_manager.get("stt_model_size", "medium")
            client_id = self.config_manager.get("client_id", "unknown_client")
            
            stt_response = self.api_client.stt(
                audio_bytes=audio_chunk,
                sample_rate=16000,
                channels=1,
                model_size=model_size,      # [추가]
                client_id=client_id,        # [추가]
                language=self.current_stt_language
            )

            if stt_response and stt_response.get("text"):
                original_text = stt_response.get("text", "").strip()
                if original_text:
                    target_lang = self._resolve_target_language(self.config_manager.get('stt_target_language', 'auto'))
                    
                    source_lang_from_cfg = self.config_manager.get("stt_source_language", "auto")
                    source_lang_for_api = None if source_lang_from_cfg == 'auto' else source_lang_from_cfg
                    
                    translated_text = self.mt_engine.translate_text(original_text, source_lang_for_api, target_lang)
                    
                    if translated_text:
                        logger.info(f"STT: '{original_text}' -> '{translated_text}'")
                        self.stt_chunk_translated.emit(original_text, translated_text)
                    else:
                        logger.warning(f"번역 실패: 원문='{original_text}', 번역기 응답 없음.")

        except Exception as e:
            logger.error(f"STT 오디오 청크 처리 중 예외 발생: {e}", exc_info=True)
            self.error_occurred.emit(f"STT Error: {e}")

    @Slot(bytes)
    def process_ocr_image(self, image_bytes: bytes):
        try:
            target_lang = self._resolve_target_language(self.config_manager.get('ocr_target_language', 'auto'))
            self.ocr_status_updated.emit(self.tr("Extracting text from image..."))
            ocr_response = self.api_client.ocr(image_bytes)
            if ocr_response is None or not ocr_response.get("text"):
                self.ocr_patches_ready.emit([])
                self.ocr_status_updated.emit("")
                return
            original_text = ocr_response.get("text")
            self.ocr_status_updated.emit(self.tr("Translating text..."))
            
            # [핵심 수정] OCR 부분에도 동일한 로직 적용
            source_lang_from_cfg = self.config_manager.get("ocr_source_language", "auto")
            source_lang_for_api = None if source_lang_from_cfg == 'auto' else source_lang_from_cfg
            
            translated_text = self.mt_engine.translate_text(original_text, source_lang_for_api, target_lang)
            
            if not translated_text:
                self.error_occurred.emit(self.tr("Translation failed. Check API key and usage."))
                return
                
            mock_rect = QRect(0, 0, 100, 50)
            patches = [{'original': original_text, 'translated': translated_text, 'rect': mock_rect}]
            self.ocr_patches_ready.emit(patches)
            self.ocr_status_updated.emit("")
        except Exception as e:
            logger.error(f"OCR 이미지 처리 중 예외 발생: {e}", exc_info=True)
            self.error_occurred.emit(f"OCR Error: {e}")

    def tr(self, text: str) -> str:
        return QCoreApplication.translate("TranslationWorker", text)