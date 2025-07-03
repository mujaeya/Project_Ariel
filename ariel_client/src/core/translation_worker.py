# ariel_client/src/core/translation_worker.py (이 코드로 전체 교체)
import logging
from PySide6.QtCore import QObject, Signal, Slot, QTimer

from ..config_manager import ConfigManager
from ..api_client import ApiClient
from ..mt_engine import MTEngine

class TranslationWorker(QObject):
    """
    모든 백엔드 통신(OCR, STT)과 번역(DeepL)을 처리하는 백그라운드 작업자.
    GUI 스레드를 차단하지 않도록 설계되었습니다.
    """
    translation_ready = Signal(str, dict, str)
    error_occurred = Signal(str)
    status_updated = Signal(str) # [핵심 추가] 상태 알림을 위한 시그널

    def __init__(self, config_manager: ConfigManager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.api_client = None
        self.mt_engine = None

    def _initialize_api_client(self):
        """필요할 때 API 클라이언트를 초기화합니다."""
        if self.api_client is None:
            try:
                server_url = self.config_manager.get("server_url")
                self.api_client = ApiClient(base_url=server_url)
            except Exception as e:
                logging.error(f"API 클라이언트 초기화 실패: {e}", exc_info=True)
                self.error_occurred.emit(f"백엔드 서버({server_url})에 연결할 수 없습니다. 주소를 확인해주세요.")
                return False
        return True

    def _initialize_mt_engine(self):
        """필요할 때 DeepL 번역 엔진을 초기화합니다."""
        if self.mt_engine is None:
            try:
                self.mt_engine = MTEngine(self.config_manager)
            except Exception as e:
                logging.error(f"DeepL 엔진 초기화 실패: {e}")
                self.error_occurred.emit(f"DeepL API 키가 유효하지 않거나 사용량을 초과했습니다. 설정을 확인해주세요.")
                return False
        return True

    @Slot(bytes)
    def process_ocr_image(self, image_bytes: bytes):
        """OCR 이미지를 처리하고 번역 결과를 보냅니다."""
        if not self._initialize_api_client(): return
        
        self.status_updated.emit("화면 분석 중...")
        ocr_text = self.api_client.send_image_for_ocr(image_bytes)
        
        if ocr_text:
            self.translate_and_emit(ocr_text, source="ocr")
        else:
            self.status_updated.emit("") # 인식 실패 시 상태 메시지 초기화

    @Slot(bytes)
    def process_stt_audio(self, audio_bytes: bytes):
        """STT 오디오를 처리하고 번역 결과를 보냅니다."""
        if not self._initialize_api_client(): return

        self.status_updated.emit("음성 인식 중...")
        stt_text = self.api_client.send_audio_for_stt(audio_bytes)
        
        if stt_text:
            self.translate_and_emit(stt_text, source="stt")
        else:
            self.status_updated.emit("")

    def translate_and_emit(self, original_text: str, source: str):
        """주어진 텍스트를 번역하고 GUI로 시그널을 보냅니다."""
        target_langs = self.config_manager.get("target_languages", ["KO"])
        
        if not self._initialize_mt_engine():
            self.status_updated.emit("번역 엔진 오류")
            return

        self.status_updated.emit("텍스트 번역 중...")
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