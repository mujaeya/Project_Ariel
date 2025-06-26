import pyaudio
import time
import numpy as np
from PySide6.QtCore import QThread, Signal, QObject

class AudioCapturer(QThread):
    """
    지정된 오디오 장치에서 오디오를 캡처하여,
    설정된 버퍼 시간만큼 모아 하나의 청크(bytes)로 만들어 방출(emit)하는 QThread.
    """
    # 시그널 정의: 완성된 오디오 청크(bytes)를 전달
    chunk_ready = Signal(bytes)
    error_occurred = Signal(str)

    # 오디오 스트림의 기본 사양
    SAMPLE_RATE = 16000  # STT API가 선호하는 샘플레이트
    CHUNK_SIZE = 1024    # 한 번에 읽어올 프레임 수
    CHANNELS = 1         # 모노
    FORMAT = pyaudio.paInt16 # 16비트 오디오

    def __init__(self, device_name: str, buffer_seconds: int, parent=None):
        super().__init__(parent)
        self.device_name = device_name
        self.buffer_seconds = buffer_seconds
        
        self._is_running = False
        self._p = None
        self._stream = None

        # 버퍼링에 필요한 청크 개수 계산
        self.num_chunks_for_buffer = int((self.SAMPLE_RATE / self.CHUNK_SIZE) * self.buffer_seconds)

    def _find_device_index(self):
        """pyaudio를 통해 장치 이름으로 인덱스를 찾습니다."""
        self._p = pyaudio.PyAudio()
        info = self._p.get_host_api_info_by_index(0)
        num_devices = info.get('deviceCount')

        for i in range(num_devices):
            device_info = self._p.get_device_info_by_host_api_device_index(0, i)
            if self.device_name in device_info.get('name'):
                print(f"오디오 장치를 찾았습니다: {device_info.get('name')} (Index: {i})")
                return i
        
        self.error_occurred.emit(f"오디오 장치 '{self.device_name}'를 찾을 수 없습니다.")
        return None

    def run(self):
        """스레드가 시작되면 실행되는 메인 로직"""
        device_index = self._find_device_index()
        if device_index is None:
            self._cleanup()
            return

        try:
            self._stream = self._p.open(format=self.FORMAT,
                                        channels=self.CHANNELS,
                                        rate=self.SAMPLE_RATE,
                                        input=True,
                                        input_device_index=device_index,
                                        frames_per_buffer=self.CHUNK_SIZE)
        except Exception as e:
            self.error_occurred.emit(f"오디오 스트림 열기 실패: {e}")
            self._cleanup()
            return

        print("오디오 캡처를 시작합니다...")
        self._is_running = True
        
        frames_buffer = []

        while self._is_running:
            try:
                data = self._stream.read(self.CHUNK_SIZE, exception_on_overflow=False)
                frames_buffer.append(data)

                # 버퍼가 가득 찼는지 확인
                if len(frames_buffer) >= self.num_chunks_for_buffer:
                    # 완성된 오디오 청크를 bytes로 합쳐서 시그널로 보냄
                    audio_chunk = b''.join(frames_buffer)
                    self.chunk_ready.emit(audio_chunk)
                    
                    # 버퍼 비우기
                    frames_buffer = []

            except IOError as e:
                # 스트림이 stop()에 의해 닫히면 IOError가 발생함
                print(f"오디오 스트림 I/O 에러 (정상적인 중지일 수 있음): {e}")
                break
            except Exception as e:
                self.error_occurred.emit(f"캡처 중 예외 발생: {e}")
                break

        print("오디오 캡처가 중지되었습니다.")
        self._cleanup()

    def stop(self):
        """오디오 캡처 스레드를 안전하게 중지합니다."""
        print("오디오 캡처 중지를 요청합니다...")
        self._is_running = False
        # run() 메서드의 루프가 자연스럽게 종료되도록 대기
        self.wait(2000) # 최대 2초 대기
        
    def _cleanup(self):
        """PyAudio 리소스를 정리합니다."""
        if self._stream is not None:
            if self._stream.is_active():
                self._stream.stop_stream()
            self._stream.close()
            self._stream = None
        
        if self._p is not None:
            self._p.terminate()
            self._p = None
        print("PyAudio 리소스가 정리되었습니다.")


# --- 이 파일을 직접 실행하여 테스트하는 부분 ---
if __name__ == '__main__':
    from PySide6.QtWidgets import QApplication
    import sys
    from config_manager import ConfigManager

    # Qt 애플리케이션 환경 구성
    app = QApplication(sys.argv)

    # 테스트를 위한 슬롯(데이터를 받는 함수)
    class TestReceiver(QObject):
        def on_chunk_ready(self, audio_data: bytes):
            duration = len(audio_data) / (AudioCapturer.SAMPLE_RATE * AudioCapturer.CHANNELS * 2) # 2 bytes for paInt16
            print(f"▶ [{time.strftime('%H:%M:%S')}] 오디오 청크 수신 완료! "
                  f"크기: {len(audio_data) / 1024:.2f} KB, 길이: {duration:.2f} 초")

        def on_error(self, message: str):
            print(f"오류 발생: {message}")

    # 설정에서 장치 이름과 버퍼 시간 가져오기
    config = ConfigManager()
    device_name = config.get("audio_input_device_name")
    buffer_seconds = config.get("buffer_seconds")
    
    if not device_name:
        print("오류: config.json에 'audio_input_device_name'이 설정되지 않았습니다.")
        print("기본값 'CABLE Input'으로 테스트를 시도합니다.")
        device_name = "CABLE Input"

    print(f"테스트 시작: {buffer_seconds}초 단위로 오디오를 캡처합니다.")
    
    receiver = TestReceiver()
    capturer = AudioCapturer(device_name=device_name, buffer_seconds=buffer_seconds)

    # 시그널과 슬롯 연결
    capturer.chunk_ready.connect(receiver.on_chunk_ready)
    capturer.error_occurred.connect(receiver.on_error)

    # 캡처 시작
    capturer.start()

    # 20초 동안 테스트 실행
    print("\n--- 20초 동안 테스트를 실행합니다. VB-CABLE로 소리를 출력해보세요. ---")
    
    # Qt 이벤트 루프를 잠시 실행하여 시그널이 처리되도록 함
    start_time = time.time()
    while time.time() - start_time < 20:
        app.processEvents() # GUI 없어도 이벤트 처리를 위해 필요
        time.sleep(0.1)

    # 캡처 중지
    capturer.stop()
    
    print("\n--- 테스트 종료 ---")
    sys.exit()