# F:/projects/Project_Ariel/ariel_client/src/core/audio_processor.py (최종 완성본)

import pyaudio
import webrtcvad
import logging
from PySide6.QtCore import QObject, Signal, Slot

logger = logging.getLogger(__name__)

class AudioProcessor(QObject):
    """
    PyAudio와 WASAPI를 직접 사용하여 시스템 오디오를 안정적으로 캡처하고,
    webrtcvad로 음성 구간을 감지하여 처리하는 최종 오디오 프로세서.
    [OSError -9996] 문제를 회피하도록 장치 탐색 로직을 강화했습니다.
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
        
        # VAD 설정
        self.vad = webrtcvad.Vad(self.config.get("vad_sensitivity", 3))
        self.sample_rate = 16000
        self.chunk_duration_ms = 30
        self.chunk_size = int(self.sample_rate * self.chunk_duration_ms / 1000)
        
        self.silence_threshold_s = self.config.get("silence_threshold_s", 1.0)
        self.min_audio_length_s = self.config.get("min_audio_length_s", 0.5)
        logger.info("AudioProcessor (PyAudio/VAD/Robust) 초기화 완료.")

    def _find_wasapi_loopback_device(self):
        """
        [수정됨] 모든 장치를 순회하여 WASAPI 루프백 장치를 찾는 더욱 견고한 방식.
        """
        try:
            self.p = pyaudio.PyAudio()
            wasapi_info = self.p.get_host_api_info_by_type(pyaudio.paWASAPI)
            
            # 1. 윈도우의 기본 출력 장치를 찾습니다.
            # get_default_output_device_info()는 더 안정적입니다.
            default_output_device_info = self.p.get_default_output_device_info()
            logger.debug(f"윈도우 기본 출력 장치: {default_output_device_info['name']}")

            # 2. 모든 장치를 순회하며 조건에 맞는 루프백 장치를 찾습니다.
            for i in range(self.p.get_device_count()):
                dev = self.p.get_device_info_by_index(i)
                
                # 조건 1: WASAPI 호스트 API에 속해 있는가?
                # 조건 2: 루프백 장치인가?
                # 조건 3: 이름이 기본 출력 장치의 이름으로 시작하는가? (예: "스피커 (Realtek..)" 와 "루프백 (스피커 (Realtek..))")
                if (dev.get('hostApi') == wasapi_info['index'] and 
                    dev.get('isLoopbackDevice') and 
                    dev.get('name').startswith(default_output_device_info['name'])):
                    logger.info(f"✅ PyAudio WASAPI 루프백 장치를 찾았습니다: {dev['name']}")
                    return dev
            
            logger.warning("이름이 일치하는 루프백 장치를 찾지 못했습니다. 다른 루프백 장치를 탐색합니다.")
            # 만약 이름으로 못찾으면, 그냥 첫번째로 발견되는 루프백 장치를 시도
            for i in range(self.p.get_device_count()):
                dev = self.p.get_device_info_by_index(i)
                if dev.get('hostApi') == wasapi_info['index'] and dev.get('isLoopbackDevice'):
                    logger.info(f"✅ 대체 루프백 장치를 찾았습니다: {dev['name']}")
                    return dev

            logger.error("시스템에서 유효한 WASAPI 루프백 장치를 찾을 수 없습니다.")
            return None

        except Exception as e:
            logger.error(f"오디오 장치 탐색 중 예외 발생: {e}", exc_info=True)
            return None

    # --- start_processing, stop, __del__ 등의 나머지 메서드는 이전과 동일하게 유지 ---
    # (이전 답변에서 제공한 코드를 그대로 사용하시면 됩니다)
    @Slot()
    def start_processing(self):
        device_info = self._find_wasapi_loopback_device()
        if not device_info:
            self.status_updated.emit("오디오 장치 없음")
            self.stop()
            return

        try:
            # 채널 수를 명시적으로 2로 시도해볼 수 있음. 대부분의 루프백은 스테레오.
            channels = device_info.get('maxInputChannels', 2)
            self.stream = self.p.open(
                format=pyaudio.paInt16,
                channels=channels,
                rate=self.sample_rate,
                input=True,
                frames_per_buffer=self.chunk_size,
                input_device_index=device_info['index']
            )
        except Exception as e:
            logger.error(f"PyAudio 스트림 시작 오류: {e}", exc_info=True)
            self.status_updated.emit("오디오 장치 오류")
            self.stop()
            return
            
        self._is_running = True
        voiced_frames = []
        silence_counter = 0

        self.status_updated.emit("음성 듣는 중...")
        logger.info(f"오디오 스트림 시작 (장치: {device_info['name']})")
        
        while self._is_running:
            try:
                frame = self.stream.read(self.chunk_size, exception_on_overflow=False)
                
                is_speech = self.vad.is_speech(frame, self.sample_rate)

                if is_speech:
                    voiced_frames.append(frame)
                    silence_counter = 0
                else:
                    silence_counter += 1
                
                silence_duration_s = (silence_counter * self.chunk_duration_ms) / 1000.0
                
                if voiced_frames and silence_duration_s > self.silence_threshold_s:
                    audio_data = b''.join(voiced_frames)
                    audio_duration_s = len(audio_data) / (self.sample_rate * channels * 2) # 채널 수 반영
                    
                    if audio_duration_s >= self.min_audio_length_s:
                        logger.info(f"문장 감지 완료. 오디오 처리 시작 (길이: {audio_duration_s:.2f}s)")
                        self.audio_chunk_ready.emit(audio_data)
                    else:
                        logger.info(f"녹음된 오디오가 너무 짧아({audio_duration_s:.2f}s) 무시합니다.")

                    voiced_frames = []
                    silence_counter = 0
            except IOError as e:
                logger.error(f"오디오 스트림 읽기 오류: {e}")
                self.status_updated.emit("오디오 장치 연결 끊김")
                self._is_running = False
        
        logger.info("오디오 처리 루프가 종료되었습니다.")
        self.stop()

    @Slot()
    def stop(self):
        if not self._is_running and not self.stream:
            if not self.p: # PyAudio 객체가 이미 종료된 경우
                self.finished.emit()
                return
            
        self._is_running = False
        
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
            self.stream = None
            
        if self.p:
            self.p.terminate()
            self.p = None
        
        logger.info("오디오 리소스가 안전하게 정리되었습니다.")
        self.stopped.emit()
        self.finished.emit()

    def __del__(self):
        logger.debug("AudioProcessor 인스턴스가 소멸됩니다.")