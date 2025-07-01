# src/audio_capturer.py (최종 병합 및 개선 버전)
from PySide6.QtCore import QObject, Signal, Slot
import soundcard as sc
import numpy as np
import queue
import logging # logging 모듈 사용

class AudioCapturer(QObject):
    """
    독립된 스레드에서 실행되며, 안정적인 방식으로 시스템 오디오를 캡처하여
    공유 큐(audio_queue)에 넣는 역할만 전담합니다.
    """
    error_occurred = Signal(str)

    def __init__(self, audio_queue: queue.Queue, parent=None):
        super().__init__(parent)
        self.SAMPLE_RATE = 16000
        # 100ms 청크 크기
        self.CHUNK_SAMPLES = int(self.SAMPLE_RATE * 0.1)
        self._is_running = False
        self.audio_queue = audio_queue

    @Slot()
    def start_capturing(self):
        """오디오 캡처를 시작하는 메인 로직"""
        self._is_running = True
        try:
            default_speaker = sc.default_speaker()
            # print() 대신 logging.info() 사용으로 변경
            logging.info(f"[AudioCapturer] 타겟 장치: {default_speaker.name}")

            # blocksize를 설정하여 안정성을 높임
            with sc.get_microphone(id=str(default_speaker.name), include_loopback=True).recorder(
                samplerate=self.SAMPLE_RATE, channels=1, blocksize=self.CHUNK_SAMPLES * 2
            ) as mic:
                logging.info("[AudioCapturer] 안정화된 오디오 캡처를 시작합니다...")
                while self._is_running:
                    data = mic.record(numframes=self.CHUNK_SAMPLES)
                    
                    # [핵심 수정] numpy 호환성 문제 해결
                    # 최신 numpy에서 권장하는 .tobytes()를 사용하고,
                    # 데이터를 int16 타입으로 명확히 변환하여 frombuffer 관련 오류를 해결합니다.
                    pcm_data = np.int16(data.flatten() * 32767).tobytes()
                    self.audio_queue.put(pcm_data)

        except Exception as e:
            error_message = f"오디오 캡처 실패: {e}"
            # print() 대신 logging.error() 사용으로 변경
            logging.error(error_message)
            self.error_occurred.emit(error_message)
        finally:
            # [개선된 종료 로직]
            # 캡처 루프가 정상적으로든(stop_capturing 호출) 예외로든
            # 종료되면 항상 None을 큐에 넣어 소비자 스레드가 종료되도록 신호를 보냅니다.
            # 이 로직은 finally 블록에 위치하여 어떤 상황에서도 실행이 보장됩니다.
            self.audio_queue.put(None)

        logging.info("[AudioCapturer] 캡처가 중지되었습니다.")

    @Slot()
    def stop_capturing(self):
        """오디오 캡처 중지를 요청하는 슬롯"""
        logging.info("[AudioCapturer] 캡처 중지를 요청합니다.")
        # 플래그만 False로 설정합니다. 실제 캡처 루프가 종료된 후
        # start_capturing 메서드의 finally 블록에서 종료 신호(None)를 보냅니다.
        self._is_running = False