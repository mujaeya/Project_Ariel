# ariel_client/src/core/audio_processor.py (이 코드로 전체 교체)
import logging
import sounddevice as sd
import numpy as np
import webrtcvad
from PySide6.QtCore import QObject, Signal, QThread, Slot

class AudioProcessor(QObject):
    """
    [완전 자동화] 시스템 사운드를 지능적으로 감지하여 음성 활동(VAD)을
    처리하고, 음성 데이터 덩어리(chunk)를 생성하는 작업자.
    """
    audio_chunk_ready = Signal(bytes)
    stopped = Signal()
    status_updated = Signal(str)
    finished = Signal() # [오류 수정] 누락되었던 시그널을 추가합니다.

    def __init__(self, config_manager, parent=None):
        super().__init__(parent)
        self.config = config_manager.get_active_profile()
        self._is_running = False
        
        # VAD 설정
        self.vad = webrtcvad.Vad(self.config.get("vad_sensitivity", 3))
        self.sample_rate = 16000
        self.chunk_duration_ms = 30 # 10, 20, 30 중 하나
        self.chunk_size = int(self.sample_rate * self.chunk_duration_ms / 1000)
        
        self.silence_threshold_s = self.config.get("silence_threshold_s", 1.0)
        self.min_audio_length_s = self.config.get("min_audio_length_s", 0.5)
        
    def _find_best_audio_device(self) -> int | None:
        """
        [대폭 개선] 시스템의 모든 입력 장치를 스캔하여
        스피커 소리를 '도청'하기에 가장 적합한 장치를 자동으로 찾습니다.
        """
        try:
            devices = sd.query_devices()
            hostapis = sd.query_hostapis()

            # 1순위: 윈도우 기본 스피커와 연결된 WASAPI 루프백 장치
            try:
                default_output_device_index = sd.default.device[1]
                default_output_device_name = devices[default_output_device_index]['name']
                for i, dev in enumerate(devices):
                    is_input = dev['max_input_channels'] > 0
                    hostapi_name = hostapis[dev['hostapi']]['name']
                    is_wasapi_loopback = 'WASAPI' in hostapi_name and 'loopback' in dev['name'].lower()
                    if is_input and is_wasapi_loopback and default_output_device_name in dev['name']:
                        logging.info(f"✅ 최적의 자동 선택 장치(WASAPI)를 찾았습니다: {dev['name']}")
                        return i
            except Exception:
                logging.warning("기본 출력 장치를 확인하는 데 실패했습니다. 다른 방법으로 탐색을 계속합니다.")

            # 2순위: 잘 알려진 이름의 '스테레오 믹스' 계열 장치
            known_mix_names = ['stereo mix', 'what u hear', 'wave out mix', '혼합']
            for i, dev in enumerate(devices):
                is_input = dev['max_input_channels'] > 0
                dev_name_lower = dev['name'].lower()
                if is_input and any(name in dev_name_lower for name in known_mix_names):
                    logging.info(f"✅ 차선책 장치(Stereo Mix 계열)를 찾았습니다: {dev['name']}")
                    return i
            
            # 3순위: 가상 오디오 케이블
            cable_devices = [i for i, dev in enumerate(devices) if dev['max_input_channels'] > 0 and 'cable' in dev['name'].lower()]
            if cable_devices:
                logging.info(f"✅ 차선책 장치(Virtual Cable)를 찾았습니다: {devices[cable_devices[0]]['name']}")
                return cable_devices[0]

        except Exception as e:
            logging.error(f"최적의 오디오 장치를 찾는 중 오류 발생: {e}", exc_info=True)
        
        # --- 최종 실패 및 디버깅 로그 ---
        logging.warning("적합한 시스템 오디오 캡처 장치를 찾지 못했습니다. STT가 동작하지 않을 수 있습니다.")
        logging.warning("--- 사용 가능한 입력 오디오 장치 목록 ---")
        try:
            for i, dev in enumerate(sd.query_devices()):
                if dev['max_input_channels'] > 0:
                    logging.warning(f"  - 장치 {i}: {dev['name']}")
        except Exception as e:
            logging.error(f"디버깅을 위한 장치 목록 조회 중 오류 발생: {e}")
        logging.warning("------------------------------------")
        return None


    @Slot()
    def start_processing(self):
        device_index = self._find_best_audio_device()
        if device_index is None:
            self.status_updated.emit("오디오 장치 없음")
            QThread.msleep(1000)
            self.stop()
            return
            
        self._is_running = True
        voiced_frames = []
        silence_counter = 0
        
        try:
            with sd.InputStream(
                samplerate=self.sample_rate,
                blocksize=self.chunk_size,
                device=device_index,
                channels=1,
                dtype='int16'
            ) as stream:
                logging.info(f"오디오 스트림 시작 (장치: {sd.query_devices(device_index)['name']})")
                while self._is_running:
                    frame, overflowed = stream.read(self.chunk_size)
                    if overflowed:
                        logging.warning("오디오 버퍼 오버플로우 발생!")
                    
                    is_speech = self.vad.is_speech(frame.tobytes(), self.sample_rate)
                    if is_speech:
                        voiced_frames.append(frame.tobytes())
                        silence_counter = 0
                    else:
                        silence_counter += 1
                    
                    silence_duration_s = (silence_counter * self.chunk_duration_ms) / 1000.0
                    if voiced_frames and silence_duration_s > self.silence_threshold_s:
                        audio_data = b''.join(voiced_frames)
                        audio_duration_s = len(audio_data) / (self.sample_rate * 2) # 16-bit
                        
                        if audio_duration_s >= self.min_audio_length_s:
                            logging.info(f"문장 감지 완료. 오디오 처리 시작 (길이: {audio_duration_s:.2f}s)")
                            self.audio_chunk_ready.emit(audio_data)
                        else:
                            logging.info(f"녹음된 오디오가 너무 짧아({audio_duration_s:.2f}s) 무시합니다.")

                        voiced_frames = []
                        silence_counter = 0
        except Exception as e:
            logging.error(f"오디오 처리 중 심각한 오류 발생: {e}", exc_info=True)
            self.status_updated.emit(f"오디오 오류: {e}")

        logging.info("오디오 처리 중지됨.")
        self.stopped.emit()

    def stop(self):
        self._is_running = False