# src/audio_capturer.py (VB-CABLE 전용 버전)

import pyaudio
import queue

class AudioCapturer:
    """
    VB-CABLE을 사용하여 시스템 오디오를 캡처하고,
    동시에 실제 스피커로 소리를 다시 출력(재송출)하는 클래스.
    """
    def __init__(self, rate=44100, chunk_size=1024):
        self.p_audio = pyaudio.PyAudio()
        self.rate = rate
        self.chunk_size = chunk_size
        self.input_device_index = None
        self.output_device_index = None
        self.stream = None
        self.audio_queue = queue.Queue() # 오디오 청크를 담을 큐

    def find_devices(self):
        """
        'CABLE Output'을 입력 장치로, 실제 스피커를 출력 장치로 찾습니다.
        """
        # 입력 장치 (CABLE Output) 찾기
        for i in range(self.p_audio.get_device_count()):
            dev = self.p_audio.get_device_info_by_index(i)
            if 'CABLE Output' in dev['name'] and dev['maxInputChannels'] > 0:
                self.input_device_index = i
                print(f"입력 장치 찾음: {dev['name']} (index {i})")
                break
        
        if self.input_device_index is None:
            raise Exception("'CABLE Output' 장치를 찾을 수 없습니다. VB-CABLE이 올바르게 설치되었는지 확인하세요.")

        # 출력 장치 (실제 스피커) 찾기 - get_default_output_device 사용
        default_output_device_info = self.p_audio.get_default_output_device_info()
        self.output_device_index = default_output_device_info['index']
        print(f"출력 장치 찾음: {default_output_device_info['name']} (index {self.output_device_index})")
    
    def start_stream(self, callback_function):
        """
        오디오 스트림을 시작합니다.
        입력(CABLE Output)에서 데이터를 읽어 콜백 함수에 전달하고,
        동시에 출력(스피커)으로 해당 데이터를 그대로 보냅니다.
        """
        if self.input_device_index is None or self.output_device_index is None:
            self.find_devices()

        def stream_callback(in_data, frame_count, time_info, status):
            # 캡처된 오디오 데이터를 외부 콜백 함수로 전달
            callback_function(in_data)
            
            # 이 데이터를 스피커로 다시 보내기 위해 반환합니다.
            # 이것이 '재송출'의 핵심입니다.
            return (in_data, pyaudio.paContinue)

        self.stream = self.p_audio.open(
            format=pyaudio.paInt16,
            channels=2, # CABLE의 기본 채널은 스테레오(2)
            rate=self.rate,
            input=True,
            output=True, # 이제 입/출력 모두 사용합니다!
            input_device_index=self.input_device_index,
            output_device_index=self.output_device_index,
            frames_per_buffer=self.chunk_size,
            stream_callback=stream_callback
        )

        print("오디오 스트림 시작. 시스템 사운드를 캡처하고 스피커로 재송출합니다...")
        self.stream.start_stream()

    def stop_stream(self):
        """
        오디오 스트림을 안전하게 중지하고 자원을 해제합니다.
        """
        if self.stream and self.stream.is_active():
            self.stream.stop_stream()
            self.stream.close()
            print("오디오 스트림 중지됨.")
        self.p_audio.terminate()
        print("PyAudio 종료됨.")