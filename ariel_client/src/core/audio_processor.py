# ariel_client/src/core/audio_processor.py (콜백 기반으로 전면 재구축)
import numpy as np
import pyaudio
import logging
from collections import deque
from queue import Queue, Empty
from PySide6.QtCore import QObject, Signal, Slot, QThread

from ..config_manager import ConfigManager

logger = logging.getLogger(__name__)


class AudioProcessor(QObject):
    """
    시스템 오디오를 비동기 콜백 방식으로 녹음하고, VAD 또는 슬라이딩 윈도우를 사용하여
    오디오 청크를 생성하는 클래스. 모든 블로킹 I/O를 제거하여 안정성을 확보했습니다.
    """
    audio_processed = Signal(bytes, int)
    status_updated = Signal(str)
    finished = Signal()
    error_occurred = Signal(str)

    def __init__(self, config_manager: ConfigManager):
        super().__init__(None)
        self.config_manager = config_manager
        self._is_running = False
        self.p = None
        self.stream = None
        self.channels = 1
        self.sample_rate = 16000
        self.audio_queue = Queue() # 콜백에서 메인 루프로 데이터를 전달할 큐
        logger.info("AudioProcessor (콜백 기반) 객체 초기화 완료.")

    @Slot()
    def stop(self):
        """오디오 처리를 안전하게 중지하도록 플래그를 설정합니다."""
        logger.info("AudioProcessor 중지 요청됨. 루프가 곧 종료됩니다.")
        self._is_running = False

    def _cleanup(self):
        """모든 오디오 관련 리소스를 정리합니다."""
        logger.debug("오디오 리소스 정리 시작.")
        if self.stream:
            if self.stream.is_active():
                self.stream.stop_stream()
            self.stream.close()
            self.stream = None
            logger.debug("오디오 스트림 정리 완료.")
        if self.p:
            self.p.terminate()
            self.p = None
            logger.debug("PyAudio 인스턴스 정리 완료.")
        logger.info("오디오 리소스 정리 완료.")

    def _audio_callback(self, in_data, frame_count, time_info, status):
        """
        sounddevice가 오디오 데이터를 수집할 때마다 비동기적으로 호출되는 함수.
        이 함수는 절대 블로킹되어서는 안 됩니다.
        """
        if self._is_running:
            self.audio_queue.put(in_data)
        return (None, pyaudio.paContinue)

    @Slot()
    def run(self):
        """메인 오디오 처리 루프. 콜백으로부터 받은 데이터를 처리합니다."""
        if self._is_running:
            logger.warning("AudioProcessor가 이미 실행 중입니다.")
            return

        logger.info("AudioProcessor 스레드 실행 시작 (콜백 모드).")
        self._is_running = True

        try:
            self.p = pyaudio.PyAudio()
            preferred_device_idx = self.config_manager.get("audio_input_device_index")
            device_index, self.sample_rate, self.channels = self._find_audio_device(preferred_device_idx)

            if device_index is None:
                raise RuntimeError("호환되는 오디오 장치를 찾을 수 없습니다.")

            device_name = self.p.get_device_info_by_index(device_index)['name']

            self.stream = self.p.open(
                format=pyaudio.paInt16,
                channels=self.channels,
                rate=self.sample_rate,
                input=True,
                input_device_index=device_index,
                frames_per_buffer=int(self.sample_rate * 10 / 1000), # 10ms 버퍼
                stream_callback=self._audio_callback # 핵심: 콜백 함수 지정
            )
            
            self.stream.start_stream()
            logger.info(f"오디오 스트림 시작 (장치: {device_name}, 채널: {self.channels}, 콜백 모드)")
            
            # [삭제] VAD 및 슬라이딩 윈도우 로직은 메인 루프로 이동
            # [개선] 현재는 하나의 범용 처리 로직만 유지하여 단순화
            self._process_stream_with_silence_detection()

        except Exception as e:
            logger.error(f"오디오 처리 중 예외 발생: {e}", exc_info=True)
            self.error_occurred.emit(f"오디오 장치 오류: {e}")
        finally:
            self._cleanup()
            self._is_running = False
            self.status_updated.emit("오프라인")
            logger.info("오디오 처리 루프가 정상적으로 종료되고 'finished' 시그널을 방출합니다.")
            self.finished.emit()

    def _process_stream_with_silence_detection(self):
        """
        오디오 큐에서 데이터를 가져와 무음 감지 후 처리하는 메인 루프.
        이 루프는 블로킹되지 않아 stop() 요청에 즉시 반응할 수 있습니다.
        """
        silence_db_threshold = self.config_manager.get("silence_db_threshold", -50.0)
        buffer_duration_s = 10  # 최대 10초 분량의 오디오 버퍼
        
        buffer_max_size_bytes = buffer_duration_s * self.sample_rate * 2 * self.channels
        
        audio_buffer = bytearray()
        last_speech_time = QThread.currentThread().msleep # 편의상 QThread의 함수 사용
        
        self.status_updated.emit("음성 듣는 중...")
        logger.info(f"무음 감지 처리 시작 (무음 레벨: {silence_db_threshold}dB)")

        while self._is_running:
            try:
                # 큐에서 데이터를 가져오되, 최대 100ms만 대기하여 stop()에 빠르게 반응
                chunk = self.audio_queue.get(timeout=0.1)

                is_silent = self._is_chunk_silent(chunk, silence_db_threshold)

                if not is_silent:
                    audio_buffer.extend(chunk)
                    last_speech_time = QThread.currentThread().msleep # 시간 갱신
                elif len(audio_buffer) > 0:
                    # 무음 구간이 감지되고 버퍼에 내용이 있으면 처리
                    logger.debug(f"무음 감지, 오디오 버퍼 처리. 크기: {len(audio_buffer)} bytes")
                    self.audio_processed.emit(bytes(audio_buffer), self.channels)
                    audio_buffer.clear()

                # 버퍼가 너무 커지는 것을 방지
                if len(audio_buffer) > buffer_max_size_bytes:
                    audio_buffer = audio_buffer[-buffer_max_size_bytes:]

            except Empty:
                # 큐가 비어있으면 현재 버퍼에 내용이 있는지 확인
                if len(audio_buffer) > 0:
                     # 오랫동안 말이 없으면 현재까지의 버퍼를 처리
                     self.audio_processed.emit(bytes(audio_buffer), self.channels)
                     audio_buffer.clear()
                continue
            
            # stop() 플래그를 확인하기 위해 QThread.msleep 사용
            QThread.msleep(1)

    def _is_chunk_silent(self, chunk: bytes, db_threshold: float) -> bool:
        """오디오 청크의 RMS를 계산하여 dBFS로 변환, 무음 여부를 판단합니다."""
        if not chunk: return True
        try:
            audio_data = np.frombuffer(chunk, dtype=np.int16)
            if audio_data.size == 0: return True
            rms = np.sqrt(np.mean(audio_data.astype(np.float64)**2))
            if rms == 0: return True
            dbfs = 20 * np.log10(rms / 32768.0)
            return dbfs < db_threshold
        except (ValueError, FloatingPointError):
            return True

    def _find_audio_device(self, preferred_device_index=None):
        logger.info("사용 가능한 오디오 장치를 검색합니다...")
        p_temp = pyaudio.PyAudio()
        try:
            # 이전과 동일한 장치 탐색 로직 (생략, 원본 코드 유지)
            # ... (이 부분은 기존 코드를 그대로 사용합니다) ...
            SUPPORTED_RATES = [16000, 48000, 32000, 8000]

            if preferred_device_index is not None:
                try:
                    dev = p_temp.get_device_info_by_index(preferred_device_index)
                    for rate in SUPPORTED_RATES:
                        for ch in [min(2, dev['maxInputChannels']), 1]:
                            if ch > 0 and p_temp.is_format_supported(rate, input_device=dev['index'], input_channels=ch, input_format=pyaudio.paInt16):
                                logger.info(f"✅ [설정 장치 사용] 장치: {dev['name']} @ {rate}Hz, {ch}ch")
                                return dev['index'], rate, ch
                except Exception as e:
                    logger.warning(f"선호 장치({preferred_device_index}) 사용 실패: {e}. 자동 탐색을 시작합니다.")

            try:
                wasapi_info = p_temp.get_host_api_info_by_type(pyaudio.paWASAPI)
                dev = p_temp.get_device_info_by_index(wasapi_info["defaultOutputDevice"])
                if dev['maxInputChannels'] > 0:
                    for rate in SUPPORTED_RATES:
                        if p_temp.is_format_supported(rate, input_device=dev['index'], input_channels=dev['maxInputChannels'], input_format=pyaudio.paInt16):
                            logger.info(f"✅ [1단계 성공] WASAPI: {dev['name']} @ {rate}Hz")
                            return dev['index'], rate, dev['maxInputChannels']
            except Exception: pass

            for i in range(p_temp.get_device_count()):
                dev = p_temp.get_device_info_by_index(i)
                if dev['maxInputChannels'] > 0 and ('Stereo Mix' in dev.get('name', '') or '스테레오 믹스' in dev.get('name', '')):
                    for rate in SUPPORTED_RATES:
                        for ch in [min(2, dev['maxInputChannels']), 1]:
                             if ch > 0 and p_temp.is_format_supported(rate, input_device=dev['index'], input_channels=ch, input_format=pyaudio.paInt16):
                                logger.info(f"✅ [2단계 성공] 'Stereo Mix': {dev['name']} @ {rate}Hz, {ch}ch")
                                return dev['index'], rate, ch

            dev_idx = p_temp.get_default_input_device_info()['index']
            dev = p_temp.get_device_info_by_index(dev_idx)
            if dev['maxInputChannels'] > 0:
                for rate in SUPPORTED_RATES:
                    if p_temp.is_format_supported(rate, input_device=dev['index'], input_channels=1, input_format=pyaudio.paInt16):
                        logger.info(f"✅ [3단계 성공] 기본 마이크: {dev['name']} @ {rate}Hz")
                        return dev['index'], rate, 1
        finally:
            p_temp.terminate()

        return None, None, None

    @staticmethod
    def get_available_input_devices() -> dict:
        # 이전과 동일한 로직 (생략, 원본 코드 유지)
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