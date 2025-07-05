# F:/projects/Project_Ariel/ariel_client/src/core/audio_processor.py (최종 완성 및 배포 가능 버전)

import pyaudio
import webrtcvad
import logging
from PySide6.QtCore import QObject, Signal, Slot

logger = logging.getLogger(__name__)

class AudioProcessor(QObject):
    """
    [최종 안정화] 자동 샘플 레이트 협상 기능을 추가하여 모든 사용자 환경에 대응하는
    범용 WASAPI 루프백 오디오 프로세서.
    """
    audio_chunk_ready = Signal(bytes)
    stopped = Signal()
    status_updated = Signal(str)
    finished = Signal()

    def __init__(self, config_manager, parent=None):
        super().__init__(parent)
        self.config = config_manager.get_active_profile()
        self._is_running = False
        self.p = None
        self.stream = None
        
        self.vad = webrtcvad.Vad(self.config.get("vad_sensitivity", 3))
        # VAD가 지원하는 샘플 레이트 목록 (선호도 순)
        self.SUPPORTED_RATES = [16000, 48000, 32000, 8000]
        
        # 실제 적용될 값들 (초기값)
        self.sample_rate = 16000
        self.chunk_duration_ms = 30 # VAD는 10, 20, 30ms 조각만 지원
        self.chunk_size = 0 # 실제 샘플 레이트에 따라 결정됨
        self.channels = 0 # 스트림의 실제 채널 수

        self.silence_threshold_s = self.config.get("silence_threshold_s", 1.0)
        self.min_audio_length_s = self.config.get("min_audio_length_s", 0.5)
        logger.info("AudioProcessor (PyAudio/VAD/Robust) 초기화 완료.")

    def _find_wasapi_loopback_device(self):
        try:
            self.p = pyaudio.PyAudio()
            wasapi_info = self.p.get_host_api_info_by_type(pyaudio.paWASAPI)
            all_wasapi_devices = [self.p.get_device_info_by_index(i) for i in range(self.p.get_device_count()) if self.p.get_device_info_by_index(i).get('hostApi') == wasapi_info['index']]

            try:
                default_output = self.p.get_default_output_device_info()
                logger.info(f"현재 기본 출력 장치: '{default_output['name']}'")
                for dev in all_wasapi_devices:
                    if dev['maxInputChannels'] > 0 and default_output['name'] in dev['name']:
                        logger.info(f"✅ [1단계 성공] 기본 출력 장치와 연관된 루프백 장치: {dev['name']}")
                        return dev
            except Exception: pass

            logger.info("1단계 탐색 실패. 'Stereo Mix' 장치를 찾습니다...")
            for dev in all_wasapi_devices:
                name_lower = dev['name'].lower()
                if dev['maxInputChannels'] > 0 and ('stereo mix' in name_lower or '스테레오 믹스' in name_lower):
                    logger.info(f"✅ [2단계 성공] 'Stereo Mix' 장치: {dev['name']}")
                    return dev
            
            logger.info("2단계 탐색 실패. 기본 입력 장치를 확인합니다...")
            try:
                default_input = self.p.get_default_input_device_info()
                logger.info(f"현재 기본 입력 장치: '{default_input['name']}'")
                name_lower = default_input['name'].lower()
                if 'mix' in name_lower or '믹스' in name_lower or 'loopback' in name_lower:
                    for dev in all_wasapi_devices:
                        if dev['name'] == default_input['name']:
                            logger.info(f"✅ [3단계 성공] 기본 입력 장치가 루프백: {dev['name']}")
                            return dev
            except Exception: pass

            logger.error("시스템에서 유효한 WASAPI 루프백 장치를 찾을 수 없습니다. 윈도우 사운드 설정에서 '스테레오 믹스'를 '사용'으로 설정했는지 확인해주세요.")
            self.status_updated.emit("오디오 장치 없음")
            return None
        except Exception as e:
            logger.error(f"오디오 장치 탐색 중 예외 발생: {e}", exc_info=True)
            self.status_updated.emit("오디오 장치 탐색 오류")
            return None

    @Slot()
    def start_processing(self):
        device_info = self._find_wasapi_loopback_device()
        if not device_info:
            self.stop()
            return

        # --- [핵심 수정] 자동 샘플 레이트 협상 로직 ---
        supported_rate = None
        for rate in self.SUPPORTED_RATES:
            try:
                if self.p.is_format_supported(rate, input_device=device_info['index'], input_channels=device_info['maxInputChannels'], input_format=pyaudio.paInt16):
                    supported_rate = rate
                    logger.info(f"✅ 오디오 장치가 {rate}Hz 샘플링을 지원합니다. 이 설정으로 진행합니다.")
                    break
            except ValueError:
                continue
        
        if not supported_rate:
            logger.error(f"오디오 장치 '{device_info['name']}'가 VAD가 요구하는 샘플 레이트({self.SUPPORTED_RATES})를 지원하지 않습니다.")
            self.status_updated.emit("지원되지 않는 오디오 장치")
            self.stop()
            return

        # 협상된 샘플 레이트로 VAD 관련 변수 업데이트
        self.sample_rate = supported_rate
        self.chunk_size = int(self.sample_rate * self.chunk_duration_ms / 1000)
        # ---------------------------------------------

        try:
            # [핵심 수정] 이 변수에 실제 채널 수를 저장합니다.
            self.channels = device_info.get('maxInputChannels', 2)
            self.stream = self.p.open(
                format=pyaudio.paInt16,
                channels=self.channels, # 변수 사용
                rate=self.sample_rate, # 협상된 샘플 레이트 사용
                input=True,
                frames_per_buffer=self.chunk_size,
                input_device_index=device_info['index']
            )
        except Exception as e:
            logger.error(f"PyAudio 스트림 시작 오류: {e}", exc_info=True)
            self.status_updated.emit("오디오 장치 열기 실패")
            self.stop()
            return
            
        self._is_running = True
        voiced_frames, silence_counter = [], 0
        self.status_updated.emit("음성 듣는 중...")
        logger.info(f"오디오 스트림 시작 (장치: {device_info['name']}, 샘플링: {self.sample_rate}Hz, 채널: {self.channels})")
        
        while self._is_running:
            try:
                frame_data = self.stream.read(self.chunk_size, exception_on_overflow=False)
                
                # [핵심 수정] 채널 수에 따라 명확하게 모노로 변환합니다.
                mono_frame = frame_data
                if self.channels == 2:
                    mono_frame = frame_data[::2]
                
                if self.vad.is_speech(mono_frame, self.sample_rate):
                    voiced_frames.append(mono_frame)
                    silence_counter = 0
                else:
                    silence_counter += 1
                
                silence_duration_s = (silence_counter * self.chunk_duration_ms) / 1000.0
                if voiced_frames and silence_duration_s > self.silence_threshold_s:
                    audio_data = b''.join(voiced_frames)
                    audio_duration_s = len(audio_data) / (self.sample_rate * 2) # 모노(2bytes/sample) 기준
                    if audio_duration_s >= self.min_audio_length_s:
                        self.audio_chunk_ready.emit(audio_data)
                    voiced_frames, silence_counter = [], 0
            except IOError as e:
                logger.error(f"오디오 스트림 읽기 오류: {e}")
                self.status_updated.emit("오디오 장치 연결 끊김")
                self._is_running = False
        
        self.stop()

    @Slot()
    def stop(self):
        if not self._is_running and self.stream is None and self.p is None: return
        self._is_running = False
        if self.stream:
            if self.stream.is_active(): self.stream.stop_stream()
            self.stream.close()
            self.stream = None
        if self.p:
            self.p.terminate()
            self.p = None
        self.stopped.emit()
        self.finished.emit()

    def __del__(self):
        logger.debug("AudioProcessor 인스턴스가 소멸됩니다.")