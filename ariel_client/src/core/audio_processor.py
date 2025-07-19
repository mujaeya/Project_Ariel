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

        # [수정] config_manager.get()을 사용하여 설정값을 직접 로드 (AttributeError 해결)
        self.vad_sensitivity = self.config_manager.get("vad_sensitivity", 3)
        self.silence_threshold_s = self.config_manager.get("silence_threshold_s", 1.0)
        self.min_audio_length_s = self.config_manager.get("min_audio_length_s", 0.5)

        self.vad = webrtcvad.Vad(self.vad_sensitivity)
        self.SUPPORTED_RATES = [48000, 32000, 16000, 8000]
        self.sample_rate = 16000
        self.chunk_duration_ms = 30
        self.bytes_per_sample = 2  # 16-bit audio

        logger.info(f"AudioProcessor 초기화 완료 (VAD 민감도: {self.vad_sensitivity})")

    @Slot()
    def start_processing(self):
        logger.info("오디오 처리 시작 요청...")
        if self._is_running:
            logger.warning("오디오 프로세서가 이미 실행 중입니다.")
            return

        self._is_running = True
        QThread.msleep(10) # is_running 플래그가 확실히 적용되도록 잠시 대기
        
        self.p = pyaudio.PyAudio()
        device_index, self.sample_rate, self.channels = self._find_audio_device()

        if device_index is None:
            self.status_updated.emit("오류: 사용 가능한 오디오 장치 없음")
            logger.error("사용 가능한 오디오 장치를 찾지 못하여 처리를 중단합니다.")
            self.stop() # 실패 시 자원 정리 및 finished 시그널 방출
            return

        logger.info(f"오디오 장치 설정 완료: Rate={self.sample_rate}Hz, Channels={self.channels}")

        try:
            self.stream = self.p.open(
                format=pyaudio.paInt16,
                channels=self.channels,
                rate=self.sample_rate,
                input=True,
                input_device_index=device_index,
                frames_per_buffer=int(self.sample_rate * self.chunk_duration_ms / 1000)
            )
            logger.info(f"오디오 스트림 시작됨 (장치: {self.p.get_device_info_by_index(device_index)['name']})")
            self.status_updated.emit("듣는 중...")
            
            # 메인 루프 실행
            self.process_audio_stream()

        except Exception as e:
            logger.error(f"오디오 스트림 열기 실패: {e}", exc_info=True)
            self.status_updated.emit("오류: 오디오 장치를 열 수 없습니다")
            self.stop()

    def process_audio_stream(self):
        """오디오 스트림을 읽고 VAD를 통해 음성 구간을 감지하여 처리하는 메인 루프"""
        silence_chunks = int((self.silence_threshold_s * 1000) / self.chunk_duration_ms)
        min_audio_chunks = int((self.min_audio_length_s * 1000) / self.chunk_duration_ms)
        
        ring_buffer = deque(maxlen=silence_chunks)
        voiced_frames = []
        is_speaking = False

        logger.debug("오디오 스트림 처리 루프 진입...")
        while self._is_running:
            try:
                chunk = self.stream.read(int(self.sample_rate * self.chunk_duration_ms / 1000), exception_on_overflow=False)
                
                mono_chunk = self._to_mono(chunk) if self.channels > 1 else chunk
                
                # VAD는 특정 바이트 길이의 청크가 필요함
                if len(mono_chunk) != int(self.sample_rate * (self.chunk_duration_ms / 1000.0) * self.bytes_per_sample / self.channels):
                     continue

                is_speech = self.vad.is_speech(mono_chunk, self.sample_rate)

                if is_speech:
                    if not is_speaking:
                        logger.debug("음성 감지 시작됨.")
                        self.status_updated.emit("음성 감지됨...")
                        is_speaking = True
                        voiced_frames.extend(list(ring_buffer))
                        ring_buffer.clear()
                    
                    voiced_frames.append(chunk)

                elif not is_speech and is_speaking:
                    logger.debug(f"음성 감지 종료. 녹음된 프레임 수: {len(voiced_frames)}")
                    is_speaking = False
                    self.status_updated.emit("듣는 중...")
                    
                    if len(voiced_frames) > min_audio_chunks:
                        audio_data = b''.join(voiced_frames)
                        logger.info(f"유효한 오디오 데이터 생성 (길이: {len(audio_data)} bytes), STT 요청 준비.")
                        self.audio_chunk_ready.emit(audio_data)
                    else:
                        logger.info(f"녹음된 음성이 너무 짧아 무시합니다 (프레임: {len(voiced_frames)} < 최소: {min_audio_chunks}).")
                    
                    voiced_frames.clear()
                    ring_buffer.clear()
                
                else: # 말하고 있지 않은 상태 (조용한 상태)
                    ring_buffer.append(chunk)

                QThread.msleep(1)

            except IOError as e:
                logger.error(f"오디오 스트림 읽기 오류: {e}")
                self.status_updated.emit("오류: 오디오 장치 연결 끊김")
                self._is_running = False # 루프 중단
            except Exception as e:
                logger.error(f"오디오 처리 중 예외 발생: {e}", exc_info=True)
                self._is_running = False

        logger.info("오디오 처리 루프가 종료되었습니다.")
        # 루프가 끝나면 항상 stop()을 호출하여 자원을 정리
        self.stop()

    def _to_mono(self, chunk: bytes) -> bytes:
        """16-bit 스테레오 오디오 바이트를 모노로 변환합니다."""
        return chunk[::2]

    @Slot()
    def stop(self):
        logger.info("오디오 처리 중지 요청 수신...")
        self._is_running = False
        
        # 스트림과 PyAudio 객체가 아직 살아있을 때만 정리 시도
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
        
        logger.info("오디오 프로세서가 안전하게 중지되고 'finished' 시그널을 방출합니다.")
        self.finished.emit()

    def _find_audio_device(self):
        logger.info("사용 가능한 오디오 장치를 검색합니다...")
        try:
            # 1단계: 'Stereo Mix' 또는 '스테레오 믹스' 이름으로 장치 검색
            for i in range(self.p.get_device_count()):
                device = self.p.get_device_info_by_index(i)
                if device.get('maxInputChannels', 0) > 0:
                    name_lower = device.get('name', '').lower()
                    if 'stereo mix' in name_lower or '스테레오 믹스' in name_lower:
                        logger.info(f"✅ [1단계 성공] 'Stereo Mix' 장치 발견: {device['name']}")
                        for rate in self.SUPPORTED_RATES:
                             if self.p.is_format_supported(rate, input_device=device['index'], input_channels=device['maxInputChannels'], input_format=pyaudio.paInt16):
                                logger.info(f"✅ {rate}Hz 샘플링 지원 확인.")
                                return device['index'], rate, device['maxInputChannels']
            
            # 2단계: WASAPI 루프백 장치 검색 (Windows 전용)
            try:
                wasapi_info = self.p.get_host_api_info_by_type(pyaudio.paWASAPI)
                default_output = self.p.get_default_output_device_info()
                loopback_name = default_output['name'] + ' (loopback)'
                
                for i in range(self.p.get_device_count()):
                     device = self.p.get_device_info_by_index(i)
                     if device['hostApi'] == wasapi_info['index'] and 'loopback' in device['name'].lower():
                        logger.info(f"✅ [2단계 성공] WASAPI 루프백 장치 발견: {device['name']}")
                        for rate in self.SUPPORTED_RATES:
                            if self.p.is_format_supported(rate, input_device=device['index'], input_channels=device['maxInputChannels'], input_format=pyaudio.paInt16):
                                logger.info(f"✅ {rate}Hz 샘플링 지원 확인.")
                                return device['index'], rate, device['maxInputChannels']
            except Exception:
                 logger.warning("WASAPI 루프백 장치를 찾지 못했습니다. (비-Windows 환경일 수 있음)")

            # 3단계: 기본 입력 장치(마이크)를 최후의 수단으로 사용
            logger.warning("루프백 장치 탐색 실패. 시스템 기본 마이크를 사용합니다.")
            default_device = self.p.get_default_input_device_info()
            for rate in self.SUPPORTED_RATES:
                 if self.p.is_format_supported(rate, input_device=default_device['index'], input_channels=1, input_format=pyaudio.paInt16):
                    logger.info(f"✅ 기본 마이크({default_device['name']})에서 {rate}Hz 샘플링 지원 확인.")
                    return default_device['index'], rate, 1

        except Exception as e:
            logger.error(f"오디오 장치 검색 중 치명적 오류 발생: {e}", exc_info=True)

        return None, None, None