import pyaudio

def list_devices():
    """
    시스템에 있는 모든 오디오 장치의 목록을 상세 정보와 함께 출력합니다.
    """
    p = pyaudio.PyAudio()
    info = p.get_host_api_info_by_index(0)
    num_devices = info.get('deviceCount')

    print("--- 사용 가능한 오디오 장치 목록 ---")
    for i in range(num_devices):
        device_info = p.get_device_info_by_host_api_device_index(0, i)
        
        # 입력 채널이 1개 이상인 장치만 필터링 (녹음 가능한 장치)
        if device_info.get('maxInputChannels') > 0:
            print(f"Index: {device_info.get('index')}, "
                  f"Name: \"{device_info.get('name')}\", "
                  f"Input Channels: {device_info.get('maxInputChannels')}")

    print("---------------------------------")
    print("\n[사용법] 위 목록에서 사용하려는 장치의 \"Name\" 부분을 그대로 복사하여")
    print("config.json 파일의 'audio_input_device_name' 값으로 붙여넣으세요.")

    p.terminate()


if __name__ == '__main__':
    list_devices()