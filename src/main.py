# src/main.py

import time
from audio_capturer import AudioCapturer

# 오디오 데이터가 들어올 때마다 호출될 간단한 콜백 함수
def audio_chunk_callback(chunk):
    """오디오 청크를 받을 때마다 호출되어, 받았다는 사실을 출력합니다."""
    # 실제로는 이 청크 데이터를 STT API로 보내는 로직이 들어갑니다.
    print(f"오디오 청크 수신: {len(chunk)} 바이트")

if __name__ == "__main__":
    # 1. 오디오 캡처 객체 생성
    capturer = AudioCapturer()

    try:
        # 2. 콜백 함수를 등록하고 스트림 시작
        #    이 함수는 백그라운드 스레드에서 오디오를 계속 캡처합니다.
        capturer.start_stream(audio_chunk_callback)

        # 3. 메인 프로그램은 다른 작업을 할 수 있습니다.
        #    여기서는 10초 동안 프로그램을 실행 상태로 유지합니다.
        print("메인 스레드: 10초 동안 대기합니다. 유튜브나 음악을 재생해 보세요.")
        time.sleep(10)
        print("메인 스레드: 대기 시간 종료.")

    except Exception as e:
        print(f"에러 발생: {e}")
    finally:
        # 4. 스트림을 안전하게 종료합니다.
        capturer.stop_stream()