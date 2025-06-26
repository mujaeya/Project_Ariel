# src/utils/audio_device_manager.py
import pyaudio

def get_audio_input_devices():
    """
    시스템에서 사용 가능한 모든 오디오 '입력' 장치의 목록을 반환합니다.
    (예: 마이크, 스테레오 믹스, VB-CABLE)

    Returns:
        A list of dictionaries, where each dictionary contains 'index' and 'name' of a device.
        e.g., [{'index': 1, 'name': 'Microphone (Realtek Audio)'}, ...]
    """
    p = pyaudio.PyAudio()
    devices = []
    info = p.get_host_api_info_by_index(0)
    num_devices = info.get('deviceCount')

    for i in range(num_devices):
        device_info = p.get_device_info_by_host_api_device_index(0, i)
        # 'maxInputChannels' > 0 인 장치만 입력 장치로 간주
        if device_info.get('maxInputChannels') > 0:
            devices.append({
                'index': i,
                'name': device_info.get('name')
            })
    
    p.terminate()
    return devices

if __name__ == '__main__':
    print("사용 가능한 오디오 입력 장치:")
    available_devices = get_audio_input_devices()
    if available_devices:
        for device in available_devices:
            print(f"- Index {device['index']}: {device['name']}")
    else:
        print("사용 가능한 입력 장치를 찾을 수 없습니다.")