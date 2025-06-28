# src/audio_capturer.py (AttributeError 수정 최종본)
from PySide6.QtCore import QObject, Signal, Slot
import soundcard as sc
import numpy as np
import queue
import time

class AudioCapturer(QObject):
    """
    독립된 스레드에서 실행되며, 안정적인 방식으로 시스템 오디오를 캡처하여
    공유 큐(audio_queue)에 넣는 역할만 전담합니다.
    """
    error_occurred = Signal(str)

    def __init__(self, audio_queue: queue.Queue, parent=None):
        super().__init__(parent)
        self.SAMPLE_RATE = 16000
        self.CHUNK_SAMPLES = int(self.SAMPLE_RATE * 0.1)  # 100ms
        self._is_running = False
        self.audio_queue = audio_queue

    @Slot()
    def start_capturing(self):
        """오디오 캡처를 시작하는 메인 로직"""
        self._is_running = True
        try:
            default_speaker = sc.default_speaker()
            print(f"[AudioCapturer] 타겟 장치: {default_speaker.name}")

            # blocksize를 설정하여 'data discontinuity' 경고를 방지하고,
            # mic.record()를 사용하여 올바르게 오디오를 녹음합니다.
            with sc.get_microphone(id=str(default_speaker.name), include_loopback=True).recorder(
                samplerate=self.SAMPLE_RATE, channels=1, blocksize=self.CHUNK_SAMPLES * 2
            ) as mic:
                print("[AudioCapturer] 안정화된 오디오 캡처를 시작합니다...")
                while self._is_running:
                    # mic.read()가 아닌, mic.record()가 올바른 사용법입니다.
                    data = mic.record(numframes=self.CHUNK_SAMPLES)
                    
                    pcm_data = (data.flatten() * 32767).astype(np.int16).tobytes()
                    self.audio_queue.put(pcm_data)

        except Exception as e:
            error_message = f"오디오 캡처 실패: {e}"
            print(error_message)
            self.error_occurred.emit(error_message)
            self.audio_queue.put(None)

        print("[AudioCapturer] 캡처가 중지되었습니다.")

    @Slot()
    def stop_capturing(self):
        """오디오 캡처를 중지하는 슬롯"""
        print("[AudioCapturer] 캡처 중지를 요청합니다.")
        self._is_running = False
        # 큐에 종료 신호를 보내 다른 스레드가 안전하게 종료되도록 합니다.
        self.audio_queue.put(None)