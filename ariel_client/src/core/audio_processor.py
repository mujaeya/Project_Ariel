# ariel_client/src/core/audio_processor.py (이 코드로 전체 교체)
import logging
import sounddevice as sd
import numpy as np
import webrtcvad
from scipy.io.wavfile import write
import io
from collections import deque
from PySide6.QtCore import QObject, Signal, QThread

# [수정] ConfigManager를 사용하기 위해 import 구문을 추가합니다.
from ..config_manager import ConfigManager

class AudioProcessor(QObject):
    """
    음성 활동을 감지하여 문장 단위로 오디오를 녹음하고,
    완성된 오디오 청크(WAV 파일 데이터)를 시그널로 보냅니다.
    """
    audio_chunk_ready = Signal(bytes)
    stopped = Signal()

    def __init__(self, config_manager: ConfigManager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self._is_running = False
        
        # --- 오디오 및 VAD 설정 ---
        self.SAMPLE_RATE = 16000
        self.CHUNK_DURATION_MS = 30
        self.CHUNK_SAMPLES = int(self.SAMPLE_RATE * self.CHUNK_DURATION_MS / 1000)
        self.VAD_AGGRESSIVENESS = 3
        
        self.SILENCE_CHUNKS = int(1.2 * 1000 / self.CHUNK_DURATION_MS) # 1.2초
        
        self.vad = webrtcvad.Vad(self.VAD_AGGRESSIVENESS)
        self.stream = None

        self.is_speaking = False
        self.frames_buffer = deque()
        self.silence_counter = 0

    def start_processing(self):
        """음성 감지 및 녹음 루프를 시작합니다."""
        if self._is_running: return
        self._is_running = True
        logging.info("지능형 음성 감지를 시작합니다.")

        try:
            # 설정에서 사용자가 최종 선택한 장치 인덱스를 가져옴
            # 만약 사용자가 '자동 선택'을 골랐다면, 그 장치의 인덱스가 저장되어 있을 것임.
            device_index = self.config_manager.get("audio_input_device_index")
            
            if device_index is None:
                logging.warning("선택된 오디오 장치가 없습니다. 기본 장치를 사용합니다.")
            else:
                 logging.info(f"사용자가 선택한 오디오 장치({device_index})로 녹음을 시작합니다.")

            self.stream = sd.InputStream(
                samplerate=self.SAMPLE_RATE,
                channels=1,
                dtype='int16',
                blocksize=self.CHUNK_SAMPLES,
                device=device_index, # 사용자가 선택한 장치 (None이면 시스템 기본값)
                callback=self.audio_callback
            )
            self.stream.start()
            
            while self._is_running:
                QThread.msleep(100)

        except Exception as e:
            logging.error(f"오디오 스트림 시작 실패: {e}", exc_info=True)
            # (여기에 사용자에게 오류를 알리는 로직 추가 필요)
        finally:
            if self.stream:
                self.stream.stop()
                self.stream.close()
            logging.info("음성 감지가 중지되었습니다.")
            self.stopped.emit()


    def stop(self):
        self._is_running = False

    def audio_callback(self, indata, frames, time, status):
        """오디오 스트림에서 호출되는 콜백 함수. VAD 로직의 핵심."""
        if not self._is_running: return

        try:
            is_speech = self.vad.is_speech(indata.tobytes(), self.SAMPLE_RATE)
        except Exception:
            is_speech = False

        if self.is_speaking:
            if is_speech:
                self.frames_buffer.append(indata.copy())
                self.silence_counter = 0
            else:
                self.silence_counter += 1
                if self.silence_counter > self.SILENCE_CHUNKS:
                    self.process_recorded_audio()
                    self.is_speaking = False
                    self.frames_buffer.clear()
        elif is_speech:
            self.is_speaking = True
            self.frames_buffer.append(indata.copy())
            self.silence_counter = 0
            
    def process_recorded_audio(self):
        """버퍼에 쌓인 오디오를 WAV 파일(bytes)로 변환하고 시그널을 보냅니다."""
        if not self.frames_buffer: return

        full_audio_data = np.concatenate(list(self.frames_buffer))
        
        duration_in_seconds = len(full_audio_data) / self.SAMPLE_RATE
        if duration_in_seconds < 0.2:
            logging.info(f"녹음된 오디오가 너무 짧아({duration_in_seconds:.2f}s) 무시합니다.")
            self.frames_buffer.clear()
            return
            
        logging.info(f"문장 감지 완료. 오디오 처리 시작 (길이: {duration_in_seconds:.2f}s)")

        wav_buffer = io.BytesIO()
        write(wav_buffer, self.SAMPLE_RATE, full_audio_data)
        wav_buffer.seek(0)
        
        self.audio_chunk_ready.emit(wav_buffer.read())
        self.frames_buffer.clear()