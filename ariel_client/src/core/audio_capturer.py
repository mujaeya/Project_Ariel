# ariel_client/src/core/audio_capturer.py (신규 파일)

from PySide6.QtCore import QObject, Signal, Slot
import soundcard as sc
import numpy as np
import queue
import logging

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
            logging.info(f"[AudioCapturer] 타겟 장치: {default_speaker.name}")

            # blocksize를 설정하여 안정성을 높임
            with sc.get_microphone(id=str(default_speaker.name), include_loopback=True).recorder(
                samplerate=self.SAMPLE_RATE, channels=1, blocksize=self.CHUNK_SAMPLES
            ) as mic:
                logging.info("[AudioCapturer] 안정화된 오디오 캡처를 시작합니다...")
                while self._is_running:
                    data = mic.record(numframes=self.CHUNK_SAMPLES)
                    pcm_data = np.int16(data.flatten() * 32767).tobytes()
                    self.audio_queue.put(pcm_data)

        except Exception as e:
            error_message = f"오디오 캡처 실패: {e}"
            logging.error(error_message, exc_info=True)
            self.error_occurred.emit(error_message)
        finally:
            # 캡처 루프가 어떤 상황에서든 종료되면 항상 None을 큐에 넣어 
            # 소비자 스레드(AudioProcessor)가 종료되도록 신호를 보냅니다.
            self.audio_queue.put(None)
            logging.info("[AudioCapturer] 캡처가 중지되었습니다.")


    @Slot()
    def stop_capturing(self):
        """오디오 캡처 중지를 요청하는 슬롯"""
        logging.info("[AudioCapturer] 캡처 중지를 요청합니다.")
        self._is_running = False