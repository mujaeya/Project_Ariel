import pyaudio
import webrtcvad
import logging
from collections import deque
from PySide6.QtCore import QObject, Signal, Slot, QThread

from ..config_manager import ConfigManager

logger = logging.getLogger(__name__)

class AudioProcessor(QObject):
    """
    안정성과 디버깅이 강화된 오디오 프로세서 (Worker 역할).
    QThread로 이동되어 백그라운드에서 실행되며, run() 메서드가 전체 생명주기를 관리합니다.
    """
    audio_chunk_ready = Signal(bytes)
    status_updated = Signal(str)
    finished = Signal() # 스레드의 모든 작업이 완료되었음을 알리는 시그널

    def __init__(self, config_manager: ConfigManager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self._is_running = False
        self.p = None
        self.stream = None
        self.vad = None
        self.chunk_size = None
        logger.info(f"AudioProcessor 객체 초기화 완료.")

    @Slot()
    def stop(self):
        """오디오 처리 루프의 안전한 중지를 요청합니다."""
        logger.info("오디오 처리 중지 요청됨.")
        self._is_running = False # ❗️ 플래그만 변경하고 직접적인 정리는 하지 않습니다.

    @Slot()
    def run(self):
        """
        스레드의 메인 실행 함수.
        오디오 장치 초기화, 실시간 처리 루프, 리소스 정리까지 모든 작업을 담당합니다.
        """
        if self._is_running:
            logger.warning("이미 실행 중인 AudioProcessor의 run()이 호출되었습니다.")
            return

        logger.info("AudioProcessor 스레드 실행 시작.")
        self._is_running = True

        try:
            # 설정값 로드 및 VAD 초기화
            self.vad_sensitivity = self.config_manager.get("vad_sensitivity", 3)
            self.silence_threshold_s = self.config_manager.get("silence_threshold_s", 1.0)
            self.min_audio_length_s = self.config_manager.get("min_audio_length_s", 0.5)
            self.vad = webrtcvad.Vad(self.vad_sensitivity)

            # PyAudio 초기화 및 오디오 장치 검색
            self.p = pyaudio.PyAudio()
            device_index, self.sample_rate, self.channels = self._find_audio_device()

            if device_index is None:
                raise RuntimeError("호환되는 오디오 장치를 찾을 수 없습니다.")

            # 실제 장치 설정에 따라 chunk_size 계산
            num_frames = int(self.sample_rate * 30 / 1000) # 30ms
            self.chunk_size = num_frames * 2 # 16-bit PCM(2 bytes/sample)

            logger.info(f"최종 오디오 설정: Device Idx={device_index}, Rate={self.sample_rate}Hz, Channels={self.channels}")

            self.stream = self.p.open(
                format=pyaudio.paInt16,
                channels=self.channels,
                rate=self.sample_rate,
                input=True,
                input_device_index=device_index,
                frames_per_buffer=num_frames
            )
            device_name = self.p.get_device_info_by_index(device_index)['name']
            logger.info(f"오디오 스트림 시작 (장치: {device_name})")
            
            # ❗️❗️❗️ 진단을 위해 이 라인을 잠시 주석 처리합니다.
            # self.status_updated.emit("Listening...") 

            # --- 메인 오디오 처리 루프 ---
            self._process_stream_loop()

        except Exception as e:
            logger.error(f"오디오 처리 중 예외 발생: {e}", exc_info=True)
            self.status_updated.emit(f"Error: {e}")
        finally:
            # --- ❗️핵심: 모든 리소스 정리 ---
            logger.debug("오디오 처리 리소스 정리 시작...")
            if self.stream and not self.stream.is_stopped():
                self.stream.stop_stream()
            if self.stream:
                self.stream.close()
            if self.p:
                self.p.terminate()
            
            self.stream = None
            self.p = None
            self._is_running = False # 상태 확실히 정리
            
            # --- ❗️❗️핵심: 모든 정리가 끝난 후, 마지막에 신호 방출 ---
            logger.info("오디오 처리 루프가 종료되고 'finished' 시그널을 방출합니다.")
            self.finished.emit()

    def _process_stream_loop(self):
        """실시간으로 오디오를 읽고 처리하는 내부 루프"""
        silence_chunks = int((self.silence_threshold_s * 1000) / 30)
        min_audio_chunks = int((self.min_audio_length_s * 1000) / 30)
        
        ring_buffer = deque(maxlen=silence_chunks)
        voiced_frames = []
        is_speaking = False
        num_frames_to_read = int(self.sample_rate * 30 / 1000)

        while self._is_running:
            try:
                chunk = self.stream.read(num_frames_to_read, exception_on_overflow=False)
                mono_chunk = self._to_mono(chunk) if self.channels > 1 else chunk

                if len(mono_chunk) != self.chunk_size:
                    continue

                is_speech = self.vad.is_speech(mono_chunk, self.sample_rate)

                if is_speech:
                    if not is_speaking:
                        is_speaking = True
                        voiced_frames.extend(list(ring_buffer))
                        ring_buffer.clear()
                    voiced_frames.append(chunk)
                elif not is_speech and is_speaking:
                    is_speaking = False
                    if len(voiced_frames) > min_audio_chunks:
                        audio_data = b''.join(voiced_frames)
                        self.audio_chunk_ready.emit(audio_data)
                    voiced_frames.clear()
                    ring_buffer.clear()
                else:
                    ring_buffer.append(chunk)

                QThread.msleep(5) # CPU 사용량 완화

            except IOError as e:
                logger.warning(f"오디오 스트림 읽기 오류: {e}")
                self._is_running = False # 루프 중단
    
    def _to_mono(self, chunk: bytes) -> bytes:
        """16-bit 스테레오 오디오를 모노로 변환합니다."""
        return b''.join(chunk[i:i+2] for i in range(0, len(chunk), 4))

    def _find_audio_device(self):
        """WASAPI 루프백 > Stereo Mix > 기본 입력 장치 순으로 탐색합니다."""
        logger.info("사용 가능한 오디오 장치를 검색합니다...")
        SUPPORTED_RATES = [48000, 32000, 16000, 8000]
        try:
            # 1단계: WASAPI 루프백
            for i in range(self.p.get_host_api_count()):
                host_api = self.p.get_host_api_info_by_index(i)
                if host_api.get('name') == 'Windows WASAPI':
                    for j in range(host_api.get('deviceCount')):
                        dev_idx = self.p.get_device_info_by_host_api_device_index(i, j)['index']
                        dev = self.p.get_device_info_by_index(dev_idx)
                        if 'loopback' in dev.get('name', '').lower():
                            for rate in SUPPORTED_RATES:
                                if self.p.is_format_supported(rate, input_device=dev['index'], input_channels=dev['maxInputChannels'], input_format=pyaudio.paInt16):
                                    logger.info(f"✅ [1단계 성공] WASAPI 루프백 장치 발견: {dev['name']} @ {rate}Hz")
                                    return dev['index'], rate, dev['maxInputChannels']
            
            # 2단계: 'Stereo Mix'
            logger.warning("1단계 탐색 실패. 'Stereo Mix' 또는 '스테레오 믹스' 장치를 찾습니다...")
            for i in range(self.p.get_device_count()):
                dev = self.p.get_device_info_by_index(i)
                if 'Stereo Mix' in dev.get('name', '') or '스테레오 믹스' in dev.get('name', ''):
                    for rate in SUPPORTED_RATES:
                         if self.p.is_format_supported(rate, input_device=dev['index'], input_channels=dev['maxInputChannels'], input_format=pyaudio.paInt16):
                            logger.info(f"✅ [2단계 성공] 'Stereo Mix' 장치 발견: {dev['name']} @ {rate}Hz")
                            return dev['index'], rate, dev['maxInputChannels']

            # 3단계: 기본 입력 장치
            logger.warning("호환되는 루프백 오디오를 찾지 못함. 시스템 기본 입력 장치를 사용합니다.")
            dev_idx = self.p.get_default_input_device_info()['index']
            dev = self.p.get_device_info_by_index(dev_idx)
            for rate in SUPPORTED_RATES:
                 if self.p.is_format_supported(rate, input_device=dev['index'], input_channels=1, input_format=pyaudio.paInt16):
                    logger.info(f"✅ [3단계 성공] 기본 마이크 장치: {dev['name']} @ {rate}Hz")
                    return dev['index'], rate, 1

        except Exception as e:
            logger.error(f"오디오 장치 검색 중 심각한 오류 발생: {e}", exc_info=True)

        return None, None, None