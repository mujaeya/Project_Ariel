# ariel_client/src/core/translation_worker.py (이 코드로 전체 교체)
import logging
from PySide6.QtCore import QObject, Signal, Slot, QTimer

from ..config_manager import ConfigManager
from ..api_client import ApiClient
from ..mt_engine import MTEngine

class TranslationWorker(QObject):
    translation_ready = Signal(str, dict, str)
    error_occurred = Signal(str)
    # [추가] 상태 업데이트를 위한 새로운 신호
    status_updated = Signal(str)

    def __init__(self, config_manager: ConfigManager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        
        try:
            server_url = self.config_manager.get("server_url")
            self.api_client = ApiClient(base_url=server_url)
            # DeepL 엔진 초기화는 필요할 때만 하도록 변경 (오류 방지)
            self.mt_engine = None
        except Exception as e:
            logging.error(f"Worker 초기화 실패: {e}", exc_info=True)
            QTimer.singleShot(100, lambda: self.error_occurred.emit(str(e)))

    def _initialize_mt_engine(self):
        """필요한 시점에 DeepL 번역 엔진을 초기화합니다."""
        if self.mt_engine is None:
            try:
                self.mt_engine = MTEngine(self.config_manager)
            except Exception as e:
                logging.error(f"DeepL 엔진 초기화 실패: {e}")
                self.error_occurred.emit(f"DeepL API 키를 확인해주세요: {e}")
                return False
        return True

    @Slot(bytes)
    def process_ocr_image(self, image_bytes: bytes):
        """OCR 이미지를 받아 처리하고 번역 결과를 보냅니다."""
        self.status_updated.emit("화면 인식 중...")
        ocr_text = self.api_client.send_image_for_ocr(image_bytes)
        if ocr_text:
            self.translate_and_emit(ocr_text, source="ocr")
        else:
            self.status_updated.emit("") # 인식 실패 시 상태 메시지 초기화

    @Slot(bytes)
    def process_stt_audio(self, audio_bytes: bytes):
        """STT 오디오를 받아 처리하고 번역 결과를 보냅니다."""
        self.status_updated.emit("음성 인식 중...")
        stt_text = self.api_client.send_audio_for_stt(audio_bytes)
        if stt_text:
            self.translate_and_emit(stt_text, source="stt")
        else:
            self.status_updated.emit("")

    def translate_and_emit(self, original_text: str, source: str):
        """주어진 텍스트를 번역하고 GUI로 시그널을 보냅니다."""
        target_langs = self.config_manager.get("target_languages", [])
        if not target_langs:
            self.status_updated.emit("")
            self.translation_ready.emit(original_text, {}, source)
            return
            
        if not self._initialize_mt_engine():
            self.status_updated.emit("DeepL API 오류")
            return

        self.status_updated.emit("번역 중...")
        try:
            translated_results = self.mt_engine.translate_text_multi(
                text=original_text, 
                target_langs=target_langs
            )
            self.status_updated.emit("") # 번역 완료 후 상태 메시지 초기화
            self.translation_ready.emit(original_text, translated_results, source)
        except Exception as e:
            logging.error(f"번역 중 오류 발생: {e}", exc_info=True)
            self.error_occurred.emit(f"번역 실패: {e}")
            self.status_updated.emit("번역 실패")