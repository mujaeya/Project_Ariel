# ariel_client/src/core/audio_processor.py (스레딩 문제 해결 최종본)
import pyaudio
import webrtcvad
import logging
from collections import deque
from PySide6.QtCore import QObject, Signal, Slot, QThread, QTimer

from ..config_manager import ConfigManager

logger = logging.getLogger(__name__)

class AudioProcessor(QObject):
    """
    시스템 오디오를 실시간으로 녹음하고, VAD 또는 슬라이딩 윈도우 방식을 선택하여
    오디오 청크를 생성하고 시그널을 발생시키는 클래스.
    """
    audio_processed = Signal(bytes, int)
    status_updated = Signal(str)
    finished = Signal()
    error_occurred = Signal(str)

    def __init__(self, config_manager: ConfigManager, parent=None):
        # [중요] 이 객체를 moveToThread로 다른 스레드로 보낼 예정이라면,
        # 생성 시 절대로 부모(parent)를 지정해서는 안 됩니다.
        # super().__init__(None) 또는 super().__init__()를 호출해야 합니다.
        # Qt 규칙: 부모가 있는 객체는 다른 스레드로 이동할 수 없습니다.
        super().__init__(parent)
        
        # 만약 외부에서 parent를 지정하여 'QObject::setParent' 오류가 계속 발생한다면,
        # 위 라인을 아래와 같이 강제 수정할 수 있습니다.
        # super().__init__(None)
        
        self.config_manager = config_manager
        self._is_running = False
        self.p = None
        self.stream = None
        self.channels = 1
        self.sample_rate = 16000

        # --- 슬라이딩 윈도우 설정 ---
        self.buffer_duration_s = self.config_manager.get("sliding_window_size_s", 10)
        self.processing_interval_s = self.config_manager.get("sliding_window_interval_s", 2)
        self._buffer = bytearray()
        self._buffer_max_size = 0

        self._processing_timer = None

        logger.info("AudioProcessor 객체 초기화 완료.")

    @staticmethod
    def get_available_input_devices() -> dict:
        """사용 가능한 오디오 입력 장치 목록을 반환합니다."""
        devices = {}
        p = pyaudio.PyAudio()
        try:
            for i in range(p.get_device_count()):
                dev_info = p.get_device_info_by_index(i)
                if dev_info.get('maxInputChannels', 0) > 0:
                    devices[dev_info['name']] = dev_info['index']
            logger.info(f"사용 가능한 입력 장치: {devices}")
        except Exception as e:
            logger.error(f"오디오 장치 목록 조회 실패: {e}")
        finally:
            p.terminate()
        return devices

    @Slot()
    def stop(self):
        """오디오 처리를 중지합니다."""
        logger.info("오디오 처리 중지 요청됨.")
        self._is_running = False
        if self._processing_timer and self._processing_timer.isActive():
            self._processing_timer.stop()

    @Slot()
    def run(self):
        """오디오 처리 스레드를 시작합니다."""
        if self._is_running:
            return
        logger.info("AudioProcessor 스레드 실행 시작.")
        self._is_running = True
        try:
            self.p = pyaudio.PyAudio()
            preferred_device_idx = self.config_manager.get("audio_input_device_index")
            device_index, self.sample_rate, self.channels = self._find_audio_device(preferred_device_idx)

            if device_index is None:
                raise RuntimeError("호환되는 오디오 장치를 찾을 수 없습니다.")

            self._buffer_max_size = self.buffer_duration_s * self.sample_rate * 2 * self.channels
            device_name = self.p.get_device_info_by_index(device_index)['name']

            use_vad = self.config_manager.get("use_vad", True)
            if not use_vad:
                self._processing_timer = QTimer()
                self._processing_timer.timeout.connect(self._process_buffer)

            if use_vad:
                logger.info("VAD 모드로 오디오 처리를 시작합니다.")
                self.stream = self.p.open(
                    format=pyaudio.paInt16, channels=self.channels, rate=self.sample_rate,
                    input=True, input_device_index=device_index,
                    frames_per_buffer=int(self.sample_rate * 30 / 1000)
                )
                logger.info(f"오디오 스트림 시작 (장치: {device_name}, 채널: {self.channels})")
                self._process_stream_with_vad()
            else:
                logger.info("슬라이딩 윈도우 모드로 오디오 처리를 시작합니다.")
                self.stream = self.p.open(
                    format=pyaudio.paInt16, channels=self.channels, rate=self.sample_rate,
                    input=True, input_device_index=device_index,
                    frames_per_buffer=int(self.sample_rate * 30 / 1000),
                    stream_callback=self._audio_callback
                )
                logger.info(f"오디오 스트림 시작 (장치: {device_name}, 채널: {self.channels}, 콜백 모드)")
                self._process_stream_with_sliding_window()

        except Exception as e:
            logger.error(f"오디오 처리 중 예외 발생: {e}", exc_info=True)
            self.error_occurred.emit(f"오디오 오류: {e}")
        finally:
            if self._processing_timer and self._processing_timer.isActive():
                self._processing_timer.stop()
            if self.stream:
                if self.stream.is_active():
                    self.stream.stop_stream()
                self.stream.close()
            if self.p:
                self.p.terminate()

            self.stream, self.p, self._is_running, self._processing_timer = None, None, False, None
            self.status_updated.emit("오프라인")
            logger.info("오디오 처리 루프가 종료되고 'finished' 시그널을 방출합니다.")
            self.finished.emit()

    def _audio_callback(self, in_data, frame_count, time_info, status):
        if status:
            logger.warning(f"오디오 콜백 상태 경고: {status}")
        self._buffer.extend(in_data)
        if len(self._buffer) > self._buffer_max_size:
            self._buffer = self._buffer[-self._buffer_max_size:]
        return (None, pyaudio.paContinue)

    def _process_stream_with_sliding_window(self):
        self.stream.start_stream()
        self.status_updated.emit("음성 듣는 중...")
        if self._processing_timer:
            self._processing_timer.start(int(self.processing_interval_s * 1000))

        while self._is_running and self.stream.is_active():
            QThread.msleep(100)

        if self.stream.is_active():
            self.stream.stop_stream()

    @Slot()
    def _process_buffer(self):
        if not self._buffer or not self._is_running:
            return
        buffer_copy = bytes(self._buffer)
        self.audio_processed.emit(buffer_copy, self.channels)
        logger.debug(f"오디오 버퍼 처리. 크기: {len(buffer_copy)} bytes")

    def _process_stream_with_vad(self):
        vad = webrtcvad.Vad(self.config_manager.get("vad_sensitivity", 3))
        silence_threshold_s = self.config_manager.get("silence_threshold_s", 1.5)
        min_audio_length_s = self.config_manager.get("min_audio_length_s", 0.5)

        silence_chunks = int((silence_threshold_s * 1000) / 30)
        min_audio_chunks = int((min_audio_length_s * 1000) / 30)
        ring_buffer = deque(maxlen=silence_chunks)
        voiced_frames = []
        is_speaking = False
        num_frames_to_read = int(self.sample_rate * 30 / 1000)

        self.status_updated.emit("음성 듣는 중... (VAD)")
        while self._is_running:
            try:
                chunk = self.stream.read(num_frames_to_read, exception_on_overflow=False)
                mono_chunk_for_vad = self._to_mono_for_vad(chunk, self.channels)
                if len(mono_chunk_for_vad) != int(self.sample_rate * 30 / 1000 * 2):
                    continue

                is_speech = vad.is_speech(mono_chunk_for_vad, self.sample_rate)
                if is_speech:
                    if not is_speaking:
                        is_speaking = True
                        voiced_frames.extend(list(ring_buffer))
                        ring_buffer.clear()
                    voiced_frames.append(chunk)
                elif not is_speech and is_speaking:
                    is_speaking = False
                    if len(voiced_frames) > min_audio_chunks:
                        self.audio_processed.emit(b''.join(voiced_frames), self.channels)
                    voiced_frames.clear()
                    ring_buffer.clear()
                else:
                    ring_buffer.append(chunk)
                QThread.msleep(5)
            except IOError as e:
                logger.warning(f"오디오 스트림 읽기 오류: {e}")
                self._is_running = False

    def _to_mono_for_vad(self, chunk: bytes, channels: int) -> bytes:
        return chunk if channels == 1 else b''.join(chunk[i:i+2] for i in range(0, len(chunk), 4))

    def _find_audio_device(self, preferred_device_index=None):
        logger.info("사용 가능한 오디오 장치를 검색합니다...")
        SUPPORTED_RATES = [16000, 48000, 32000, 8000]

        if preferred_device_index is not None:
            try:
                dev = self.p.get_device_info_by_index(preferred_device_index)
                for rate in SUPPORTED_RATES:
                    for ch in [min(2, dev['maxInputChannels']), 1]:
                        if self.p.is_format_supported(rate, input_device=dev['index'], input_channels=ch, input_format=pyaudio.paInt16):
                            logger.info(f"✅ [설정 장치 사용] 장치: {dev['name']} @ {rate}Hz, {ch}ch")
                            return dev['index'], rate, ch
            except Exception as e:
                logger.warning(f"선호 장치({preferred_device_index}) 사용 실패: {e}. 자동 탐색을 시작합니다.")

        try:
            wasapi_info = self.p.get_host_api_info_by_type(pyaudio.paWASAPI)
            dev = self.p.get_device_info_by_index(wasapi_info["defaultOutputDevice"])
            for rate in SUPPORTED_RATES:
                if self.p.is_format_supported(rate, input_device=dev['index'], input_channels=dev['maxInputChannels'], input_format=pyaudio.paInt16):
                    logger.info(f"✅ [1단계 성공] WASAPI: {dev['name']} @ {rate}Hz")
                    return dev['index'], rate, dev['maxInputChannels']
        except Exception:
            pass

        for i in range(self.p.get_device_count()):
            dev = self.p.get_device_info_by_index(i)
            if 'Stereo Mix' in dev.get('name', '') or '스테레오 믹스' in dev.get('name', ''):
                for rate in SUPPORTED_RATES:
                    if self.p.is_format_supported(rate, input_device=dev['index'], input_channels=dev['maxInputChannels'], input_format=pyaudio.paInt16):
                        logger.info(f"✅ [2단계 성공] 'Stereo Mix': {dev['name']} @ {rate}Hz")
                        return dev['index'], rate, dev['maxInputChannels']

        try:
            dev_idx = self.p.get_default_input_device_info()['index']
            dev = self.p.get_device_info_by_index(dev_idx)
            for rate in SUPPORTED_RATES:
                if self.p.is_format_supported(rate, input_device=dev['index'], input_channels=1, input_format=pyaudio.paInt16):
                    logger.info(f"✅ [3단계 성공] 기본 마이크: {dev['name']} @ {rate}Hz")
                    return dev['index'], rate, 1
        except Exception as e:
            logger.error(f"기본 입력 장치 검색 실패: {e}")

        return None, None, None