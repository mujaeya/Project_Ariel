# ariel_client/src/core/audio_processor.py (이 코드로 전체 교체)

import numpy as np
import pyaudio
import logging
import time
from queue import Queue, Empty
from collections import deque
import torch

from PySide6.QtCore import QObject, Signal, Slot, QThread, QCoreApplication

from ..config_manager import ConfigManager
from ..utils import resource_path

logger = logging.getLogger(__name__)


class AudioProcessor(QObject):
    """
    [V12.1] 시스템 오디오 출력(Loopback)을 캡처하고 Silero VAD로 음성 구간을 감지하여 처리하는 클래스.
    """
    audio_chunk_ready = Signal(bytes)
    status_updated = Signal(str)
    finished = Signal()
    error_occurred = Signal(str)

    def __init__(self, config_manager: ConfigManager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self._is_running = False
        self.p = None
        self.stream = None
        self.audio_queue = Queue()
        self.sample_rate = 16000  # Whisper & Silero VAD 호환성을 위해 16kHz로 고정
        
        # VAD 관련 초기화
        self.vad_model = None
        self.get_speech_timestamps = None
        self.load_vad_model()

        logger.info("AudioProcessor (Loopback + Silero VAD) 객체 초기화 완료.")

    def load_vad_model(self):
        """Silero VAD 모델을 로드합니다."""
        try:
            # torch.set_num_threads(1) # 필요시 스레드 수 제한
            # 모델은 ~/.cache/torch/hub/snakers4_silero-vad_master 에 저장됨
            model, utils = torch.hub.load(
                repo_or_dir='snakers4/silero-vad',
                model='silero_vad',
                force_reload=False, # True로 설정하면 매번 새로 다운로드
                trust_repo=True
            )
            self.vad_model = model
            (self.get_speech_timestamps, _, _, _, _) = utils
            logger.info("✅ Silero VAD 모델 로딩 완료.")
        except Exception as e:
            logger.error(f"Silero VAD 모델 로딩 실패: {e}", exc_info=True)
            self.error_occurred.emit(self.tr("Failed to load VAD model. Please check your internet connection and try again."))
            self.vad_model = None


    @Slot()
    def stop(self):
        """오디오 처리 중지를 요청합니다."""
        logger.info("AudioProcessor 중지 요청됨.")
        self._is_running = False

    def _cleanup(self):
        """PyAudio 관련 리소스를 안전하게 정리합니다."""
        logger.debug("오디오 리소스 정리 시작.")
        if self.stream and self.stream.is_active():
            self.stream.stop_stream()
        if self.stream:
            self.stream.close()
        self.stream = None
        if self.p:
            self.p.terminate()
        self.p = None
        logger.info("오디오 리소스 정리 완료.")

    def _audio_callback(self, in_data, frame_count, time_info, status):
        """오디오 스트림에서 호출되는 콜백 함수."""
        if self._is_running:
            self.audio_queue.put(in_data)
        return (None, pyaudio.paContinue)

# In class AudioProcessor:

    def _get_loopback_device_info(self):
        """
        [V12.2] 시스템의 루프백 오디오 장치를 찾는 개선된 로직.
        1. WASAPI 호스트에서 'loopback'을 이름에 포함하는 입력 장치를 우선 검색.
        2. 찾지 못하면, 기본 출력 장치가 입력을 지원하는지 확인 (차선책).
        """
        logger.info("시스템 루프백 오디오 장치를 검색합니다... (개선된 방식)")
        
        try:
            # 1. 명시적인 루프백 장치 검색 (1순위)
            wasapi_info = self.p.get_host_api_info_by_type(pyaudio.paWASAPI)
            logger.debug(f"시스템의 모든 장치 수: {self.p.get_device_count()}")
            
            for i in range(self.p.get_device_count()):
                device = self.p.get_device_info_by_index(i)
                # 디버깅을 위해 모든 장치 정보 출력
                logger.debug(f"  - 장치 {i}: {device.get('name')}, 호스트 API: {device.get('hostApi')}, 입력 채널: {device.get('maxInputChannels')}")
                
                is_wasapi = device.get('hostApi') == wasapi_info['index']
                is_input = device.get('maxInputChannels', 0) > 0
                is_loopback_name = 'loopback' in device.get('name', '').lower()

                if is_wasapi and is_input and is_loopback_name:
                    logger.info(f"✅ [1순위: 명시적 루프백 장치 발견] 이름: {device.get('name')}")
                    return device

            logger.warning("명시적인 루프백 장치를 찾지 못했습니다. 차선책을 시도합니다.")

            # 2. 기본 출력 장치가 입력을 지원하는지 확인 (차선책)
            default_device_index = wasapi_info.get("defaultOutputDevice")
            if default_device_index == -1:
                logger.error("WASAPI 기본 출력 장치를 찾을 수 없습니다.")
                return None
            
            device_info = self.p.get_device_info_by_index(default_device_index)
            if device_info.get("maxInputChannels", 0) > 0:
                logger.info(f"✅ [2순위: 루프백 가능 장치 발견] 이름: {device_info.get('name')}")
                return device_info
            else:
                logger.error(f"장치 '{device_info.get('name')}'는 루프백 캡처가 불가능합니다.")
                return None

        except Exception as e:
            logger.error(f"루프백 장치 검색 중 예외 발생: {e}", exc_info=True)
            return None

    @Slot()
    def run(self):
        """오디오 캡처 및 VAD 기반 음성 구간 감지 메인 루프."""
        if self._is_running:
            return
        if not self.vad_model:
            self.error_occurred.emit(self.tr("VAD model is not loaded. Cannot start STT."))
            return

        logger.info("AudioProcessor 스레드 실행 시작 (루프백 + VAD 모드).")
        self._is_running = True

        try:
            self.p = pyaudio.PyAudio()
            device_info = self._get_loopback_device_info()
            if not device_info:
                raise RuntimeError(self.tr("Could not find a valid audio device for system sound capture."))

            channels = int(device_info.get('maxInputChannels', 1))

            self.stream = self.p.open(
                format=pyaudio.paInt16, channels=channels, rate=self.sample_rate,
                input=True, input_device_index=device_info["index"],
                frames_per_buffer=512, # VAD 성능을 위해 버퍼 크기 조절
                stream_callback=self._audio_callback, as_loopback=True
            )
            self.stream.start_stream()
            self.status_updated.emit(self.tr("Listening to system sound..."))
            logger.info("오디오 스트림 시작 및 VAD 처리 루프 진입.")
            
            # VAD 처리 루프
            self._vad_processing_loop()

        except Exception as e:
            error_message = f"Audio Capture/Processing Error: {e}"
            logger.error(error_message, exc_info=True)
            self.error_occurred.emit(self.tr(str(e)))
        finally:
            self._cleanup()
            self._is_running = False
            self.status_updated.emit("")
            logger.info("오디오 처리 루프가 종료되고 'finished' 시그널을 방출합니다.")
            self.finished.emit()

    def _vad_processing_loop(self):
        """VAD를 사용하여 음성 구간을 감지하고 처리하는 메인 로직."""
        vad_threshold = self.config_manager.get('vad_threshold', 0.5)
        min_silence_duration_ms = self.config_manager.get('vad_min_silence_duration_ms', 800)
        speech_pad_ms = self.config_manager.get('vad_speech_pad_ms', 400)
        
        window_size_samples = 512 # 스트림 버퍼 크기와 일치
        speech_buffer = deque()
        is_speaking = False
        silence_start_time = None

        while self._is_running:
            try:
                chunk = self.audio_queue.get(timeout=0.1)
                audio_float32 = np.frombuffer(chunk, dtype=np.int16).astype(np.float32) / 32768.0
                
                # 채널이 2개 이상이면 모노로 변환
                if audio_float32.ndim > 1 and audio_float32.shape[1] > 1:
                    audio_float32 = audio_float32.mean(axis=1)

                # VAD 모델은 512 샘플 단위로 처리하는 것이 효율적
                speech_confidence = self.vad_model(torch.from_numpy(audio_float32), self.sample_rate).item()

                if speech_confidence >= vad_threshold:
                    if not is_speaking:
                        logger.debug("VAD SPEECH DETECTED")
                        is_speaking = True
                    speech_buffer.append(chunk)
                    silence_start_time = None # 침묵 타이머 리셋
                else: # 침묵 구간
                    if is_speaking:
                        # 음성이 막 끝난 경우, 추가 버퍼링
                        speech_buffer.append(chunk)
                        if silence_start_time is None:
                            silence_start_time = time.time()
                            logger.debug("VAD SILENCE DETECTED, starting silence timer...")

                        # 일정 시간 이상 침묵이 지속되면 문장 종료로 간주
                        if time.time() - silence_start_time > (min_silence_duration_ms / 1000.0):
                            final_chunk = b"".join(speech_buffer)
                            speech_buffer.clear()
                            is_speaking = False
                            silence_start_time = None
                            
                            if len(final_chunk) > (self.sample_rate * 2 * 0.2): # 최소 0.2초 이상
                                logger.info(f"Speech segment finalized, emitting chunk of size {len(final_chunk)} bytes.")
                                self.audio_chunk_ready.emit(final_chunk)
                            else:
                                logger.debug("Discarding speech segment, too short.")
                    else:
                        # 버퍼에 내용이 없고 계속 침묵인 경우, 버퍼 비우기
                        if speech_buffer:
                            speech_buffer.clear()
            except Empty:
                # 큐가 비어있을 때, 여전히 말하는 중이었다면 타임아웃으로 문장 종료 처리
                if is_speaking and silence_start_time and (time.time() - silence_start_time > (min_silence_duration_ms / 1000.0)):
                     final_chunk = b"".join(speech_buffer)
                     speech_buffer.clear()
                     is_speaking = False
                     silence_start_time = None
                     logger.info(f"Speech segment finalized by timeout, emitting chunk of size {len(final_chunk)} bytes.")
                     self.audio_chunk_ready.emit(final_chunk)
                continue


    def tr(self, text, context="AudioProcessor"):
        return QCoreApplication.translate(context, text)