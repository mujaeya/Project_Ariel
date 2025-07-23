# ariel_client/src/core/audio_processor.py (논리 오류 수정 및 로직 개선 버전)

import numpy as np
import pyaudio
import logging
import time
from queue import Queue, Empty
from PySide6.QtCore import QObject, Signal, Slot, QThread, QCoreApplication

from ..config_manager import ConfigManager

logger = logging.getLogger(__name__)


class AudioProcessor(QObject):
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
        self.audio_queue = Queue()
        logger.info("AudioProcessor (콜백 기반) 객체 초기화 완료.")

    @Slot()
    def stop(self):
        logger.info("AudioProcessor 중지 요청됨. 루프가 곧 종료됩니다.")
        self._is_running = False

    def _cleanup(self):
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
        if self._is_running:
            self.audio_queue.put(in_data)
        return (None, pyaudio.paContinue)
        
    @Slot()
    def run(self):
        if self._is_running:
            logger.warning("AudioProcessor가 이미 실행 중입니다.")
            return

        logger.info("AudioProcessor 스레드 실행 시작 (콜백 모드).")
        self._is_running = True

        try:
            self.p = pyaudio.PyAudio()
            preferred_device_idx = self.config_manager.get("audio_input_device_index", None)
            device_index, self.sample_rate, self.channels = self._find_audio_device(preferred_device_idx)

            if device_index is None:
                raise RuntimeError("호환되는 오디오 장치를 찾을 수 없습니다. 마이크나 스테레오 믹스가 활성화되어 있는지 확인하세요.")

            device_info = self.p.get_device_info_by_index(device_index)
            device_name = device_info['name']
            
            # [수정] PyAudio는 정수형 샘플 레이트를 요구하며, Whisper 호환성을 위해 16000으로 고정하는 것이 안정적임
            self.sample_rate = 16000
            if int(device_info['defaultSampleRate']) != self.sample_rate:
                 logger.warning(f"장치의 기본 샘플 레이트({device_info['defaultSampleRate']})와 다른 16000Hz로 스트림을 엽니다.")

            self.stream = self.p.open(
                format=pyaudio.paInt16,
                channels=self.channels,
                rate=self.sample_rate,
                input=True,
                input_device_index=device_index,
                frames_per_buffer=1024,
                stream_callback=self._audio_callback
            )
            
            self.stream.start_stream()
            logger.info(f"오디오 스트림 시작 (장치: {device_name}, {self.sample_rate}Hz, {self.channels}ch, 콜백 모드)")
            
            self._process_audio_from_queue()

        except Exception as e:
            logger.error(f"오디오 처리 중 예외 발생: {e}", exc_info=True)
            self.error_occurred.emit(f"Audio Device Error: {e}")
        finally:
            self._cleanup()
            self._is_running = False
            self.status_updated.emit("") # 오프라인 시 상태 메시지 제거
            logger.info("오디오 처리 루프가 정상적으로 종료되고 'finished' 시그널을 방출합니다.")
            self.finished.emit()

    def _process_audio_from_queue(self):
        silence_db_threshold = self.config_manager.get("silence_db_threshold", -50.0)
        silence_duration_s = self.config_manager.get("silence_threshold_s", 1.5)
        buffer_duration_s = 20 # 버퍼 최대 길이를 20초로 늘림
        buffer_max_size_bytes = buffer_duration_s * self.sample_rate * 2 * self.channels
        
        audio_buffer = bytearray()
        last_speech_time = time.time()
        is_speaking = False
        
        self.status_updated.emit(self.tr("Listening..."))
        logger.info(f"무음 감지 처리 시작 (무음 레벨: {silence_db_threshold}dB, 무음 대기: {silence_duration_s}s)")

        while self._is_running:
            try:
                chunk = self.audio_queue.get(timeout=0.1)

                is_silent = self._is_chunk_silent(chunk, silence_db_threshold)

                if not is_silent:
                    # [핵심 로직 수정 1] 음성이 감지되면 is_speaking 플래그를 True로 설정
                    if not is_speaking:
                        logger.debug("음성 시작 감지.")
                        is_speaking = True
                    audio_buffer.extend(chunk)
                    last_speech_time = time.time() # 마지막 음성 감지 시간 갱신
                elif is_speaking:
                    # [핵심 로직 수정 2] 이전에 말하고 있었는데, 지금은 조용하다면
                    # 버퍼에 일단 청크를 추가하고(말 끝의 여운), 시간 경과를 체크
                    audio_buffer.extend(chunk)
                    if time.time() - last_speech_time > silence_duration_s:
                        logger.info(f"음성 종료 감지(무음 {silence_duration_s}s 지속). 버퍼 처리. 크기: {len(audio_buffer)} bytes")
                        self.audio_processed.emit(bytes(audio_buffer), self.channels)
                        audio_buffer.clear()
                        is_speaking = False # 처리 후 말하기 상태 초기화

                # 버퍼가 너무 커지면 오래된 데이터부터 버림
                if len(audio_buffer) > buffer_max_size_bytes:
                    logger.warning(f"오디오 버퍼가 최대 크기({buffer_duration_s}s)를 초과하여 앞부분을 자릅니다.")
                    # 버퍼의 앞부분을 잘라냄
                    cut_size = len(audio_buffer) - buffer_max_size_bytes
                    audio_buffer = audio_buffer[cut_size:]
                    last_speech_time = time.time()

            except Empty:
                # [핵심 로직 수정 3] 큐가 비어있을 때도, 말하고 있던 상태에서 시간이 경과하면 처리
                if is_speaking and (time.time() - last_speech_time > silence_duration_s):
                    logger.info(f"음성 종료 감지(타임아웃). 버퍼 처리. 크기: {len(audio_buffer)} bytes")
                    self.audio_processed.emit(bytes(audio_buffer), self.channels)
                    audio_buffer.clear()
                    is_speaking = False
                continue
        
        if len(audio_buffer) > 0:
            logger.info("종료 전, 남아있는 오디오 버퍼를 처리합니다.")
            self.audio_processed.emit(bytes(audio_buffer), self.channels)
            audio_buffer.clear()

    def _is_chunk_silent(self, chunk: bytes, db_threshold: float) -> bool:
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
            # 1. 선호 장치 확인
            if preferred_device_index is not None:
                try:
                    dev = p_temp.get_device_info_by_index(preferred_device_index)
                    ch = int(dev.get('maxInputChannels', 0))
                    if ch > 0:
                        logger.info(f"✅ [설정 장치 사용] 장치: {dev['name']} @ {dev['defaultSampleRate']}Hz, {ch}ch")
                        return dev['index'], int(dev['defaultSampleRate']), ch
                except Exception as e:
                    logger.warning(f"선호 장치({preferred_device_index}) 사용 실패: {e}. 자동 탐색을 시작합니다.")

            # 2. 'Stereo Mix' 또는 '스테레오 믹스' 이름으로 장치 검색
            for i in range(p_temp.get_device_count()):
                dev = p_temp.get_device_info_by_index(i)
                dev_name = dev.get('name', '').lower()
                if dev.get('maxInputChannels', 0) > 0 and ('stereo mix' in dev_name or '스테레오 믹스' in dev_name):
                    logger.info(f"✅ [1단계 성공] 'Stereo Mix': {dev['name']}")
                    return dev['index'], int(dev['defaultSampleRate']), int(dev['maxInputChannels'])
            
            # 3. WASAPI 기본 출력 장치 (Windows 루프백)
            try:
                wasapi_info = p_temp.get_host_api_info_by_type(pyaudio.paWASAPI)
                default_device_index = wasapi_info.get("defaultOutputDevice")
                if default_device_index is not None and default_device_index != -1:
                    dev = p_temp.get_device_info_by_index(default_device_index)
                    if dev.get('maxInputChannels', 0) > 0:
                        logger.info(f"✅ [2단계 성공] WASAPI 기본 루프백: {dev['name']}")
                        return dev['index'], int(dev['defaultSampleRate']), int(dev['maxInputChannels'])
            except Exception: pass

            # 4. 기본 입력 장치 (마이크)
            try:
                dev_info = p_temp.get_default_input_device_info()
                logger.info(f"✅ [3단계 성공] 기본 마이크: {dev_info['name']}")
                return dev_info['index'], int(dev_info['defaultSampleRate']), int(dev_info['maxInputChannels'])
            except Exception as e:
                 logger.error(f"기본 입력 장치 확인 실패: {e}")

        finally:
            p_temp.terminate()

        logger.error("❌ 사용 가능한 오디오 입력 장치를 찾지 못했습니다.")
        return None, None, None

    @staticmethod
    def get_available_input_devices() -> dict:
        devices = {}
        p = pyaudio.PyAudio()
        try:
            for i in range(p.get_device_count()):
                dev_info = p.get_device_info_by_index(i)
                if dev_info.get('maxInputChannels', 0) > 0:
                    devices[dev_info['name']] = dev_info['index']
        except Exception as e:
            logger.error(f"오디오 장치 목록 조회 실패: {e}")
        finally:
            p.terminate()
        return devices

    def tr(self, text):
        return QCoreApplication.translate("AudioProcessor", text)