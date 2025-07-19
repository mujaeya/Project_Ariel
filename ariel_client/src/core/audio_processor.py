# ariel_client/src/core/audio_processor.py (수정 후)
import pyaudio
import webrtcvad
import logging
from collections import deque
from PySide6.QtCore import QObject, Signal, Slot, QThread

from ..config_manager import ConfigManager

logger = logging.getLogger(__name__)

class AudioProcessor(QObject):
    """
    안정성과 디버깅이 강화된 오디오 프로세서.
    WASAPI 루프백, Stereo Mix, 기본 마이크 순으로 장치를 탐색하며,
    VAD(음성 구간 감지)를 통해 유효한 오디오 청크만 전달합니다.
    """
    audio_chunk_ready = Signal(bytes)
    status_updated = Signal(str)
    finished = Signal() # [중요] 스레드 완전 종료를 알리는 시그널

    def __init__(self, config_manager: ConfigManager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self._is_running = False
        self.p = None
        self.stream = None

        # [수정] config_manager.get()을 사용하여 설정값을 직접 로드 (get_active_profile 호출 오류 해결)
        self.vad_sensitivity = self.config_manager.get("vad_sensitivity", 3)
        self.silence_threshold_s = self.config_manager.get("silence_threshold_s", 1.0)
        self.min_audio_length_s = self.config_manager.get("min_audio_length_s", 0.5)

        self.vad = webrtcvad.Vad(self.vad_sensitivity)
        self.SUPPORTED_RATES = [48000, 32000, 16000, 8000]
        self.sample_rate = 16000
        self.chunk_duration_ms = 30
        self.bytes_per_sample = 2  # 16-bit audio
        self.channels = 1 # VAD는 모노 채널에서만 동작

        logger.info(f"AudioProcessor 초기화 완료 (VAD 민감도: {self.vad_sensitivity})")

    @Slot()
    def start_processing(self):
        logger.info("오디오 처리 시작 요청...")
        if self._is_running:
            logger.warning("오디오 프로세서가 이미 실행 중입니다.")
            return

        self._is_running = True
        self.p = pyaudio.PyAudio()
        device_index, supported_rate, supported_channels = self._find_audio_device()

        if device_index is None:
            self.status_updated.emit("Error: No suitable audio device found.")
            self.stop()
            return

        self.sample_rate = supported_rate
        self.channels = supported_channels
        
        # VAD는 1채널(모노)만 지원하므로, 채널 수가 1이 아니면 처리 로직에서 변환 필요
        logger.info(f"최종 오디오 설정: Device Idx={device_index}, Rate={self.sample_rate}Hz, Channels={self.channels}")

        try:
            self.stream = self.p.open(
                format=pyaudio.paInt16,
                channels=self.channels,
                rate=self.sample_rate,
                input=True,
                input_device_index=device_index,
                frames_per_buffer=int(self.sample_rate * self.chunk_duration_ms / 1000)
            )
            logger.info(f"오디오 스트림 시작 (장치: {self.p.get_device_info_by_index(device_index)['name']})")
            self.status_updated.emit("Listening...")

            self.process_audio_stream()

        except Exception as e:
            logger.error(f"오디오 스트림 열기 실패: {e}", exc_info=True)
            self.status_updated.emit(f"Error: Failed to open audio stream.")
            self.stop()

    def process_audio_stream(self):
        """오디오 스트림을 읽고 VAD를 통해 음성 구간을 감지하여 처리하는 메인 루프"""
        silence_chunks = int((self.silence_threshold_s * 1000) / self.chunk_duration_ms)
        min_audio_chunks = int((self.min_audio_length_s * 1000) / self.chunk_duration_ms)
        
        ring_buffer = deque(maxlen=silence_chunks)
        voiced_frames = []
        is_speaking = False

        logger.debug("오디오 스트림 처리 루프 시작...")
        # [수정] 스레드 중단 시 스트림 유효성을 함께 검사하여 충돌 방지
        while self._is_running and self.stream and not self.stream.is_stopped():
            try:
                chunk = self.stream.read(int(self.sample_rate * self.chunk_duration_ms / 1000), exception_on_overflow=False)
                
                # 스테레오 -> 모노 변환 (VAD를 위해)
                mono_chunk = self._to_mono(chunk) if self.channels > 1 else chunk
                
                # VAD는 10, 20, 30ms 청크만 지원. 길이가 맞지 않으면 오류 발생 가능
                if len(mono_chunk) != self.chunk_size:
                    continue

                is_speech = self.vad.is_speech(mono_chunk, self.sample_rate)

                if is_speech:
                    if not is_speaking:
                        logger.debug("음성 감지 시작")
                        self.status_updated.emit("Speaking detected...")
                        is_speaking = True
                        voiced_frames.extend(list(ring_buffer)) # 앞부분의 조용한 소리도 포함
                        ring_buffer.clear()
                    
                    voiced_frames.append(chunk)

                elif not is_speech and is_speaking:
                    logger.debug(f"음성 감지 종료. voiced_frames 길이: {len(voiced_frames)}")
                    is_speaking = False
                    if len(voiced_frames) > min_audio_chunks:
                        audio_data = b''.join(voiced_frames)
                        logger.info(f"유효한 오디오 데이터 (길이: {len(audio_data)} bytes) 전송")
                        self.audio_chunk_ready.emit(audio_data)
                    else:
                        logger.info("녹음된 음성이 너무 짧아 무시합니다.")
                    
                    voiced_frames.clear()
                    ring_buffer.clear()
                
                else: # 말하고 있지 않은 상태
                    ring_buffer.append(chunk)

                QThread.msleep(10) # CPU 사용량 완화

            except IOError as e:
                logger.error(f"오디오 스트림 읽기 오류: {e}")
                self.status_updated.emit("Error: Audio stream read error.")
                self._is_running = False # 루프 중단
            except Exception as e:
                logger.error(f"오디오 처리 중 예외 발생: {e}", exc_info=True)
                self._is_running = False # 루프 중단

        logger.info("오디오 처리 루프가 정상적으로 종료되었습니다.")
        self.stop() # 모든 자원 정리

    def _to_mono(self, chunk: bytes) -> bytes:
        """16-bit 스테레오 오디오를 모노로 변환합니다. (왼쪽 채널 데이터만 추출)"""
        return b''.join(chunk[i:i+2] for i in range(0, len(chunk), 4))

    @Slot()
    def stop(self):
        # [수정] 중복 호출 방지 및 상태 플래그 우선 설정으로 안정성 강화
        if not self._is_running and not self.stream:
            return
            
        logger.info("오디오 처리 중지 요청...")
        self._is_running = False
        
        if self.stream:
            if not self.stream.is_stopped():
                self.stream.stop_stream()
            self.stream.close()
            logger.debug("오디오 스트림이 닫혔습니다.")
        self.stream = None

        if self.p:
            self.p.terminate()
            logger.debug("PyAudio가 종료되었습니다.")
        self.p = None
        
        logger.info("오디오 프로세서가 성공적으로 중지되고 'finished' 시그널을 방출합니다.")
        self.finished.emit()


    def _find_audio_device(self):
        """[수정] 더 안정적인 장치 탐색 로직 (WASAPI 우선)"""
        logger.info("사용 가능한 오디오 장치를 검색합니다...")
        try:
            # 1단계: WASAPI 루프백 장치 우선 검색
            for i in range(self.p.get_host_api_count()):
                host_api = self.p.get_host_api_info_by_index(i)
                if host_api.get('name') == 'Windows WASAPI':
                    for j in range(host_api.get('deviceCount')):
                        # WASAPI 장치의 인덱스는 host_api 인덱스와 관련 없음
                        device_index = self.p.get_device_info_by_host_api_device_index(i, j)['index']
                        device = self.p.get_device_info_by_index(device_index)
                        # device.get('isLoopbackDevice')는 Pyaudio 0.2.12+ 에서만 사용 가능
                        if 'loopback' in device.get('name', '').lower():
                            logger.info(f"✅ [1단계 성공] WASAPI 루프백 장치 발견: {device['name']}")
                            for rate in self.SUPPORTED_RATES:
                                try:
                                    if self.p.is_format_supported(rate, input_device=device['index'], input_channels=device['maxInputChannels'], input_format=pyaudio.paInt16):
                                        logger.info(f"✅ {rate}Hz 샘플링 지원 확인.")
                                        return device['index'], rate, device['maxInputChannels']
                                except ValueError:
                                    continue
            
            # 2단계: 'Stereo Mix' 이름으로 장치 검색
            logger.warning("1단계 탐색 실패. 'Stereo Mix' 또는 '스테레오 믹스' 장치를 찾습니다...")
            for i in range(self.p.get_device_count()):
                device = self.p.get_device_info_by_index(i)
                if 'Stereo Mix' in device.get('name', '') or '스테레오 믹스' in device.get('name', ''):
                    logger.info(f"✅ [2단계 성공] 'Stereo Mix' 장치 발견: {device['name']}")
                    for rate in self.SUPPORTED_RATES:
                         try:
                             if self.p.is_format_supported(rate, input_device=device['index'], input_channels=device['maxInputChannels'], input_format=pyaudio.paInt16):
                                logger.info(f"✅ {rate}Hz 샘플링 지원 확인.")
                                return device['index'], rate, device['maxInputChannels']
                         except ValueError:
                             continue

            logger.error("호환되는 루프백 오디오 장치를 찾을 수 없습니다. 마이크를 기본 장치로 사용합니다.")
            default_device_index = self.p.get_default_input_device_info()['index']
            device = self.p.get_device_info_by_index(default_device_index)
            for rate in self.SUPPORTED_RATES:
                 try:
                     if self.p.is_format_supported(rate, input_device=device['index'], input_channels=1, input_format=pyaudio.paInt16):
                        logger.info(f"✅ 기본 마이크 장치에서 {rate}Hz 샘플링 지원 확인.")
                        return device['index'], rate, 1
                 except ValueError:
                     continue

        except Exception as e:
            logger.error(f"오디오 장치 검색 중 오류 발생: {e}", exc_info=True)

        return None, None, None