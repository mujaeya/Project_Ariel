# F:/projects/Project_Ariel/ariel_client/src/core/audio_processor.py (이 코드로 전체 교체)

import pyaudio
import webrtcvad
import logging
from PySide6.QtCore import QObject, Signal, Slot

logger = logging.getLogger(__name__)

class AudioProcessor(QObject):
    """
    [v3.0 최종 안정화] 기본 출력 장치에 대한 루프백을 직접 탐색하는 기능으로 개선하여,
    모든 사용자 환경에 안정적으로 대응하는 범용 WASAPI 루프백 오디오 프로세서.
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
        
        # VAD 설정: 민감도는 1 (Least aggressive) ~ 3 (Most aggressive)
        self.vad = webrtcvad.Vad(self.config.get("vad_sensitivity", 3))
        self.SUPPORTED_RATES = [48000, 32000, 16000, 8000] # 선호도 순
        
        self.sample_rate = 16000
        self.chunk_duration_ms = 30 # VAD는 10, 20, 30ms 조각만 지원
        self.chunk_size = 0
        self.channels = 0

        self.silence_threshold_s = self.config.get("silence_threshold_s", 1.0)
        self.min_audio_length_s = self.config.get("min_audio_length_s", 0.5)
        logger.info("AudioProcessor (PyAudio/VAD/Robust) 초기화 완료.")

    def _find_wasapi_loopback_device(self):
        """
        [개선] WASAPI 루프백 장치를 찾는 가장 안정적인 방법.
        1. 기본 오디오 출력 장치를 찾습니다.
        2. 해당 출력 장치에 대한 '루프백' 입력 장치를 직접 찾습니다.
        3. 실패 시 '스테레오 믹스'와 같은 일반적인 이름으로 폴백합니다.
        """
        try:
            self.p = pyaudio.PyAudio()
            wasapi_info = self.p.get_host_api_info_by_type(pyaudio.paWASAPI)
        except Exception as e:
            logger.error(f"PyAudio WASAPI 호스트 정보를 가져올 수 없습니다: {e}")
            self.status_updated.emit("오디오 시스템 오류")
            return None

        try:
            # 1. 시스템의 기본 *출력* 장치를 가져옵니다.
            default_output_device = self.p.get_default_output_device_info()
            logger.info(f"시스템 기본 출력 장치: '{default_output_device['name']}'")
        except IOError:
            logger.error("기본 출력 장치를 찾을 수 없습니다. 스피커/헤드폰이 연결되어 있는지 확인하세요.")
            self.status_updated.emit("출력 장치 없음")
            return None

        # 2. 모든 WASAPI *입력* 장치를 스캔하여 '루프백' 장치를 찾습니다.
        for i in range(self.p.get_device_count()):
            dev = self.p.get_device_info_by_index(i)
            # 입력 채널이 있고, WASAPI 장치이며, 이름에 'loopback'이 포함된 경우
            if dev.get('maxInputChannels', 0) > 0 and dev.get('hostApi') == wasapi_info['index']:
                if 'loopback' in dev.get('name', '').lower():
                    logger.info(f"✅ [1단계 성공] 루프백 장치 발견: {dev['name']}")
                    return dev

        # 3. 루프백을 못 찾았을 경우, '스테레오 믹스' 등의 이름으로 2차 탐색 (Fallback)
        logger.warning("1단계 탐색 실패. 'Stereo Mix' 또는 '스테레오 믹스' 장치를 찾습니다...")
        for i in range(self.p.get_device_count()):
            dev = self.p.get_device_info_by_index(i)
            if dev.get('maxInputChannels', 0) > 0 and dev.get('hostApi') == wasapi_info['index']:
                name_lower = dev.get('name', '').lower()
                if 'stereo mix' in name_lower or '스테레오 믹스' in name_lower:
                    logger.info(f"✅ [2단계 성공] 'Stereo Mix' 장치 발견: {dev['name']}")
                    return dev

        logger.error("시스템에서 유효한 WASAPI 루프백 장치를 찾을 수 없습니다. 윈도우 사운드 설정에서 '스테레오 믹스'를 '사용'으로 설정했는지 확인해주세요.")
        self.status_updated.emit("루프백 장치 없음")
        return None

    @Slot()
    def start_processing(self):
        device_info = self._find_wasapi_loopback_device()
        if not device_info:
            self.stop()
            return

        # 자동 샘플 레이트 협상
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
            logger.error(f"오디오 장치 '{device_info['name']}'가 VAD 요구 샘플 레이트({self.SUPPORTED_RATES})를 지원하지 않습니다.")
            self.status_updated.emit("지원되지 않는 오디오 장치")
            self.stop()
            return

        self.sample_rate = supported_rate
        self.chunk_size = int(self.sample_rate * self.chunk_duration_ms / 1000)
        self.channels = device_info['maxInputChannels']

        try:
            self.stream = self.p.open(
                format=pyaudio.paInt16,
                channels=self.channels,
                rate=self.sample_rate,
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
                
                # 스테레오(2ch) 데이터를 모노로 변환 (Whisper API는 모노를 선호)
                mono_frame = frame_data
                if self.channels == 2:
                    # 왼쪽 채널만 사용하거나 (frame_data[0::4] + frame_data[1::4]),
                    # 단순 슬라이싱으로 바이트 수를 줄일 수 있습니다.
                    # 여기서는 바이트 수를 줄이는 간단한 방법을 사용합니다.
                    mono_frame = frame_data[::2]
                
                # VAD(음성 구간 감지)는 16-bit, 모노, 특정 샘플링 레이트의 PCM 데이터에서 가장 잘 작동합니다.
                # mono_frame의 길이가 VAD가 처리 가능한지 확인하는 것이 좋습니다.
                if len(mono_frame) != (self.sample_rate * self.chunk_duration_ms // 1000) * 2:
                    continue # 데이터 길이가 맞지 않으면 건너뛰기

                if self.vad.is_speech(mono_frame, self.sample_rate):
                    voiced_frames.append(mono_frame)
                    silence_counter = 0
                else:
                    silence_counter += 1
                
                silence_duration_s = (silence_counter * self.chunk_duration_ms) / 1000.0
                if voiced_frames and silence_duration_s > self.silence_threshold_s:
                    audio_data = b''.join(voiced_frames)
                    audio_duration_s = len(audio_data) / (self.sample_rate * 2)
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
            try:
                if self.stream.is_active(): self.stream.stop_stream()
                self.stream.close()
            except Exception as e:
                logger.error(f"PyAudio 스트림 정리 중 오류 발생: {e}")
            finally:
                self.stream = None
        if self.p:
            self.p.terminate()
            self.p = None
        
        # 시그널 방출 순서 조정
        self.stopped.emit()
        self.finished.emit()
        logger.info("AudioProcessor가 안전하게 중지되었습니다.")

    def __del__(self):
        logger.debug("AudioProcessor 인스턴스가 소멸됩니다.")