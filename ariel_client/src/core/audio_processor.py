# ariel_client/src/core/audio_processor.py (V12.4: 실시간 처리 방식)

import numpy as np
import logging
import time
import queue
from PySide6.QtCore import QObject, Signal, Slot, QCoreApplication

from ..config_manager import ConfigManager

logger = logging.getLogger(__name__)

class AudioProcessor(QObject):
    """
    AudioCapturer로부터 오디오 데이터를 받아, STT 처리에 적합한
    일정 크기의 '청크(Chunk)'로 만들어 시그널을 방출하는 역할만 전담합니다.
    VAD(음성 활동 감지) 로직을 제거하여 실시간성을 확보합니다.
    """
    audio_chunk_ready = Signal(bytes) # Signal 이름을 더 명확하게 변경
    status_updated = Signal(str)
    finished = Signal()
    error_occurred = Signal(str)

    def __init__(self, config_manager: ConfigManager, audio_queue: queue.Queue):
        super().__init__(None)
        self.config_manager = config_manager
        self.audio_queue = audio_queue
        self._is_running = False
        
        self.SAMPLE_RATE = 16000
        # 1초 분량의 오디오 청크를 만듭니다. 16000Hz * 16-bit(2 bytes)
        self.CHUNK_DURATION_S = 1.0
        self.CHUNK_SIZE_BYTES = int(self.SAMPLE_RATE * 2 * self.CHUNK_DURATION_S)
        
        logger.info("AudioProcessor 초기화 완료 (실시간 청크 방식).")

    @Slot()
    def stop(self):
        """오디오 처리 루프 중지를 요청합니다."""
        logger.info("AudioProcessor 중지 요청됨.")
        self._is_running = False

    @Slot()
    def run(self):
        """오디오 큐에서 데이터를 가져와 1초 단위의 청크로 만들어 방출하는 메인 루프"""
        logger.info("AudioProcessor 스레드 실행 시작 (실시간 청크 방식).")
        self._is_running = True

        audio_buffer = bytearray()
        self.status_updated.emit(self.tr("Listening..."))

        while self._is_running:
            try:
                # AudioCapturer가 보내주는 작은 데이터 조각을 기다립니다.
                # get()에 timeout을 주어, _is_running 플래그 변경에 빠르게 반응하도록 합니다.
                data_from_capturer = self.audio_queue.get(timeout=0.1)

                if data_from_capturer is None:
                    logger.info("종료 신호(None) 수신. AudioProcessor 루프를 종료합니다.")
                    break
                
                audio_buffer.extend(data_from_capturer)

                # 버퍼에 처리할 만큼의 데이터(1초 분량)가 쌓였는지 확인
                while len(audio_buffer) >= self.CHUNK_SIZE_BYTES:
                    # 정확히 1초 분량의 청크를 잘라냅니다.
                    current_chunk = audio_buffer[:self.CHUNK_SIZE_BYTES]
                    # 버퍼에서 처리한 부분을 제거합니다.
                    audio_buffer = audio_buffer[self.CHUNK_SIZE_BYTES:]

                    logger.debug(f"1초 분량 오디오 청크 생성 ({len(current_chunk)} bytes), 방출합니다.")
                    self.audio_chunk_ready.emit(bytes(current_chunk))

            except queue.Empty:
                # 큐가 비어있는 것은 정상적인 상황이므로, 계속 루프를 돕니다.
                continue
            except Exception as e:
                logger.error(f"AudioProcessor 루프 중 예외 발생: {e}", exc_info=True)
                self.error_occurred.emit(str(e))
        
        # 루프 종료 시, 버퍼에 남아있는 데이터가 있다면 처리합니다.
        if len(audio_buffer) > 0:
            logger.info(f"종료 전, 남아있는 오디오 버퍼({len(audio_buffer)} bytes)를 처리합니다.")
            self.audio_chunk_ready.emit(bytes(audio_buffer))
            audio_buffer.clear()

        self.status_updated.emit("")
        self.finished.emit()
        logger.info("AudioProcessor 루프가 정상적으로 종료되고 'finished' 시그널을 방출합니다.")

    def tr(self, text):
        """국제화(i18n)를 위한 편의 함수"""
        return QCoreApplication.translate("AudioProcessor", text)