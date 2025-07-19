# ariel_client/src/core/audio_processor.py (이 코드로 전체 교체)
import pyaudio
import webrtcvad
import logging
from collections import deque
from PySide6.QtCore import QObject, Signal, Slot, QThread

from ..config_manager import ConfigManager

logger = logging.getLogger(__name__)

class AudioProcessor(QObject):
    audio_chunk_ready = Signal(bytes, int)
    status_updated = Signal(str)
    finished = Signal()

    def __init__(self, config_manager: ConfigManager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self._is_running = False
        self.p = None
        self.stream = None
        self.channels = 1
        logger.info("AudioProcessor 객체 초기화 완료.")

    @staticmethod
    def get_available_input_devices() -> dict:
        devices = {}; p = pyaudio.PyAudio()
        try:
            for i in range(p.get_device_count()):
                dev_info = p.get_device_info_by_index(i)
                if dev_info.get('maxInputChannels', 0) > 0: devices[dev_info['name']] = dev_info['index']
            logger.info(f"사용 가능한 입력 장치: {devices}")
        except Exception as e: logger.error(f"오디오 장치 목록 조회 실패: {e}")
        finally: p.terminate()
        return devices

    @Slot()
    def stop(self):
        logger.info("오디오 처리 중지 요청됨."); self._is_running = False

    @Slot()
    def run(self):
        if self._is_running: return
        logger.info("AudioProcessor 스레드 실행 시작."); self._is_running = True
        try:
            self.p = pyaudio.PyAudio()
            preferred_device_idx = self.config_manager.get("audio_input_device_index")
            device_index, self.sample_rate, self.channels = self._find_audio_device(preferred_device_idx)
            if device_index is None: raise RuntimeError("호환되는 오디오 장치를 찾을 수 없습니다.")

            num_frames_per_buffer = int(self.sample_rate * 30 / 1000)
            self.stream = self.p.open(
                format=pyaudio.paInt16, channels=self.channels, rate=self.sample_rate,
                input=True, input_device_index=device_index, frames_per_buffer=num_frames_per_buffer)
            device_name = self.p.get_device_info_by_index(device_index)['name']
            logger.info(f"오디오 스트림 시작 (장치: {device_name}, 채널: {self.channels})")
            
            # [수정] 설정에 따라 처리 루프 분기
            if self.config_manager.get("use_vad", True):
                logger.info("VAD 모드로 오디오 처리를 시작합니다.")
                self._process_stream_with_vad()
            else:
                logger.info("고정 시간 청크 모드로 오디오 처리를 시작합니다.")
                self._process_stream_with_fixed_chunks()

        except Exception as e:
            logger.error(f"오디오 처리 중 예외 발생: {e}", exc_info=True)
            self.status_updated.emit(f"Error: {e}")
        finally:
            if self.stream and self.stream.is_active(): self.stream.stop_stream(); self.stream.close()
            if self.p: self.p.terminate()
            self.stream, self.p, self._is_running = None, None, False
            logger.info("오디오 처리 루프가 종료되고 'finished' 시그널을 방출합니다."); self.finished.emit()

    def _process_stream_with_vad(self):
        vad = webrtcvad.Vad(self.config_manager.get("vad_sensitivity", 3))
        silence_threshold_s = self.config_manager.get("silence_threshold_s", 1.5)
        min_audio_length_s = self.config_manager.get("min_audio_length_s", 0.5)
        
        silence_chunks = int((silence_threshold_s * 1000) / 30)
        min_audio_chunks = int((min_audio_length_s * 1000) / 30)
        ring_buffer = deque(maxlen=silence_chunks); voiced_frames = []; is_speaking = False
        num_frames_to_read = int(self.sample_rate * 30 / 1000)

        while self._is_running:
            try:
                chunk = self.stream.read(num_frames_to_read, exception_on_overflow=False)
                mono_chunk_for_vad = self._to_mono_for_vad(chunk, self.channels)
                if len(mono_chunk_for_vad) != int(self.sample_rate * 30 / 1000 * 2): continue

                is_speech = vad.is_speech(mono_chunk_for_vad, self.sample_rate)
                if is_speech:
                    if not is_speaking: is_speaking = True; voiced_frames.extend(list(ring_buffer)); ring_buffer.clear()
                    voiced_frames.append(chunk)
                elif not is_speech and is_speaking:
                    is_speaking = False
                    if len(voiced_frames) > min_audio_chunks:
                        self.audio_chunk_ready.emit(b''.join(voiced_frames), self.channels)
                    voiced_frames.clear(); ring_buffer.clear()
                else: ring_buffer.append(chunk)
                QThread.msleep(5)
            except IOError as e: logger.warning(f"오디오 스트림 읽기 오류: {e}"); self._is_running = False

    def _process_stream_with_fixed_chunks(self):
        duration_s = self.config_manager.get("fixed_chunk_duration_s", 4.0)
        num_chunks = int(duration_s * 1000 / 30)
        frames_per_read = int(self.sample_rate * 30 / 1000)
        
        while self._is_running:
            audio_chunk = bytearray()
            for _ in range(num_chunks):
                if not self._is_running: break
                try:
                    data = self.stream.read(frames_per_read, exception_on_overflow=False)
                    audio_chunk.extend(data)
                except IOError as e:
                    logger.warning(f"고정 청크 스트림 읽기 오류: {e}"); self._is_running = False; break
            
            if self._is_running and audio_chunk:
                self.audio_chunk_ready.emit(bytes(audio_chunk), self.channels)

    def _to_mono_for_vad(self, chunk: bytes, channels: int) -> bytes:
        return chunk if channels == 1 else b''.join(chunk[i:i+2] for i in range(0, len(chunk), 4))

    def _find_audio_device(self, preferred_device_index=None):
        logger.info("사용 가능한 오디오 장치를 검색합니다..."); SUPPORTED_RATES = [16000, 48000, 32000, 8000]
        if preferred_device_index is not None:
            try:
                dev = self.p.get_device_info_by_index(preferred_device_index)
                for rate in SUPPORTED_RATES:
                    for ch in [min(2, dev['maxInputChannels']), 1]:
                         if self.p.is_format_supported(rate, input_device=dev['index'], input_channels=ch, input_format=pyaudio.paInt16):
                            logger.info(f"✅ [설정 장치 사용] 장치: {dev['name']} @ {rate}Hz, {ch}ch"); return dev['index'], rate, ch
            except Exception as e: logger.warning(f"선호 장치({preferred_device_index}) 사용 실패: {e}. 자동 탐색을 시작합니다.")

        try: # 1단계: WASAPI
            wasapi_info = self.p.get_host_api_info_by_type(pyaudio.paWASAPI)
            dev = self.p.get_device_info_by_index(wasapi_info["defaultOutputDevice"])
            for rate in SUPPORTED_RATES:
                if self.p.is_format_supported(rate, input_device=dev['index'], input_channels=dev['maxInputChannels'], input_format=pyaudio.paInt16):
                    logger.info(f"✅ [1단계 성공] WASAPI: {dev['name']} @ {rate}Hz"); return dev['index'], rate, dev['maxInputChannels']
        except Exception: pass

        for i in range(self.p.get_device_count()): # 2단계: 'Stereo Mix'
            dev = self.p.get_device_info_by_index(i)
            if 'Stereo Mix' in dev.get('name', '') or '스테레오 믹스' in dev.get('name', ''):
                for rate in SUPPORTED_RATES:
                     if self.p.is_format_supported(rate, input_device=dev['index'], input_channels=dev['maxInputChannels'], input_format=pyaudio.paInt16):
                        logger.info(f"✅ [2단계 성공] 'Stereo Mix': {dev['name']} @ {rate}Hz"); return dev['index'], rate, dev['maxInputChannels']

        try: # 3단계: 기본 입력
            dev_idx = self.p.get_default_input_device_info()['index']
            dev = self.p.get_device_info_by_index(dev_idx)
            for rate in SUPPORTED_RATES:
                 if self.p.is_format_supported(rate, input_device=dev['index'], input_channels=1, input_format=pyaudio.paInt16):
                    logger.info(f"✅ [3단계 성공] 기본 마이크: {dev['name']} @ {rate}Hz"); return dev['index'], rate, 1
        except Exception as e: logger.error(f"기본 입력 장치 검색 실패: {e}")
        return None, None, None