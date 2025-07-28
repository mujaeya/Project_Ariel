# ariel_client/src/core/audio_processor.py (V13.0: 백엔드 API 연동)

import numpy as np
import logging
import time
import queue
from PySide6.QtCore import QObject, Signal, Slot, QCoreApplication

from ..config_manager import ConfigManager
from ..api_client import APIClient

logger = logging.getLogger(__name__)

class AudioProcessor(QObject):
    """
    AudioCapturer로부터 오디오 데이터를 받아 1초 단위 청크로 조립하고,
    APIClient를 통해 백엔드에 STT 요청을 보낸 후,
    결과 텍스트를 시그널로 방출하는 'STT 요청 책임자' 역할을 수행합니다.
    """
    transcription_received = Signal(str) # STT 결과를 전달할 새로운 시그널
    status_updated = Signal(str)
    finished = Signal()
    error_occurred = Signal(str)

    def __init__(self, config_manager: ConfigManager, audio_queue: queue.Queue, api_client: APIClient):
        super().__init__(None)
        self.config_manager = config_manager
        self.audio_queue = audio_queue
        self.api_client = api_client # API 클라이언트 인스턴스 주입
        self._is_running = False
        
        self.SAMPLE_RATE = 16000
        # 1초 분량의 오디오 청크를 만듭니다. 16000Hz * 16-bit(2 bytes)
        self.CHUNK_DURATION_S = 1.0
        self.CHUNK_SIZE_BYTES = int(self.SAMPLE_RATE * 2 * self.CHUNK_DURATION_S)
        
        logger.info("AudioProcessor 초기화 완료 (백엔드 API 연동 방식).")

    @Slot()
    def stop(self):
        """오디오 처리 루프 중지를 요청합니다."""
        logger.info("AudioProcessor 중지 요청됨.")
        self._is_running = False

    @Slot()
    def run(self):
        """오디오 큐에서 데이터를 가져와 1초 단위 청크로 만든 후 STT API를 호출하는 메인 루프"""
        logger.info("AudioProcessor 스레드 실행 시작 (백엔드 API 연동 방식).")
        self._is_running = True

        audio_buffer = bytearray()
        self.status_updated.emit(self.tr("Listening..."))

        while self._is_running:
            try:
                data_from_capturer = self.audio_queue.get(timeout=0.1)

                if data_from_capturer is None:
                    logger.info("종료 신호(None) 수신. AudioProcessor 루프를 종료합니다.")
                    break
                
                audio_buffer.extend(data_from_capturer)

                while len(audio_buffer) >= self.CHUNK_SIZE_BYTES:
                    current_chunk = audio_buffer[:self.CHUNK_SIZE_BYTES]
                    audio_buffer = audio_buffer[self.CHUNK_SIZE_BYTES:]

                    self.process_chunk(bytes(current_chunk))

            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"AudioProcessor 루프 중 예외 발생: {e}", exc_info=True)
                self.error_occurred.emit(str(e))
        
        if len(audio_buffer) > 0:
            logger.info(f"종료 전, 남아있는 오디오 버퍼({len(audio_buffer)} bytes)를 처리합니다.")
            self.process_chunk(bytes(audio_buffer))
            audio_buffer.clear()

        self.status_updated.emit("")
        self.finished.emit()
        logger.info("AudioProcessor 루프가 정상적으로 종료되고 'finished' 시그널을 방출합니다.")
        
    def process_chunk(self, audio_chunk: bytes):
        """오디오 청크를 받아 STT API를 호출하고 결과를 시그널로 방출하는 메소드"""
        try:
            # 설정에서 현재 STT 언어를 가져옵니다.
            language = self.config_manager.get('stt_language', 'en')
            logger.debug(f"1초 분량 오디오 청크({len(audio_chunk)} bytes)로 STT 요청 ({language}).")
            
            response = self.api_client.stt(audio_bytes=audio_chunk, language=language)

            if response and "text" in response:
                transcribed_text = response["text"]
                if transcribed_text: # 비어있지 않은 텍스트만 전송
                    logger.info(f"전사 결과 수신: '{transcribed_text}'")
                    self.transcription_received.emit(transcribed_text)
            else:
                logger.warning("STT API로부터 유효한 텍스트 응답을 받지 못했습니다.")

        except Exception as e:
            logger.error(f"STT 청크 처리 중 예외 발생: {e}", exc_info=True)
            self.error_occurred.emit(self.tr("STT Error"))


    def tr(self, text):
        """국제화(i18n)를 위한 편의 함수"""
        return QCoreApplication.translate("AudioProcessor", text)