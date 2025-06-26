from PySide6.QtCore import QThread, Signal, Slot, QObject
from config_manager import ConfigManager
from audio_capturer import AudioCapturer
from stt_engine import STTEngine
from mt_engine import MTEngine

class Worker(QThread):
    """
    오디오 캡처, STT, 번역의 전체 파이프라인을 관리하는 작업자 스레드.
    """
    # 시그널 정의: 최종 번역 결과(리스트)를 UI로 전달
    translation_ready = Signal(list)
    # 시그널 정의: 오류 메시지를 UI로 전달
    worker_error = Signal(str)

    def __init__(self, config_manager: ConfigManager, parent: QObject = None):
        super().__init__(parent)
        self.config_manager = config_manager
        
        # 파이프라인의 각 부품들
        self.audio_capturer = None
        self.stt_engine = None
        self.mt_engine = None
        
        self._is_running = False

    def run(self):
        """스레드가 시작될 때 실행되는 메인 로직."""
        self._is_running = True
        print("[Worker] 작업자 스레드를 시작합니다...")

        try:
            # 스레드 내에서 엔진들을 초기화해야 스레드 관련 문제를 피할 수 있음
            self.stt_engine = STTEngine(self.config_manager)
            self.mt_engine = MTEngine(self.config_manager)
            
            device_name = self.config_manager.get("audio_input_device_name")
            buffer_seconds = self.config_manager.get("buffer_seconds")
            self.audio_capturer = AudioCapturer(device_name, buffer_seconds)

            # AudioCapturer의 시그널을 Worker의 슬롯에 연결
            self.audio_capturer.chunk_ready.connect(self._process_audio_chunk)
            self.audio_capturer.error_occurred.connect(self.worker_error.emit)
            
            # 오디오 캡처 시작
            print("[Worker] 하위 오디오 캡처 스레드를 시작합니다.")
            self.audio_capturer.start()

            # 이 스레드의 이벤트 루프를 시작. 시그널 처리를 위해 필수.
            self.exec()

        except Exception as e:
            error_message = f"작업자 스레드 초기화 실패: {e}"
            print(error_message)
            self.worker_error.emit(error_message)
        
        print("[Worker] 이벤트 루프 종료. 리소스 정리 시작...")
        
        # 스레드가 종료될 때 하위 스레드도 확실히 정리
        if self.audio_capturer and self.audio_capturer.isRunning():
            self.audio_capturer.stop()
            self.audio_capturer.wait() # 완전히 종료될 때까지 대기
        
        print("[Worker] 작업자 스레드가 안전하게 종료되었습니다.")

    @Slot(bytes)
    def _process_audio_chunk(self, audio_chunk: bytes):
        """오디오 청크가 준비되면 호출되는 슬롯(실질적인 작업 공간)."""
        if not self._is_running:
            return

        print("\n[Worker] 오디오 청크 수신. STT 및 번역 파이프라인 가동...")
        
        # 1. STT (화자 분리 포함)
        stt_results = self.stt_engine.transcribe_chunk(audio_chunk)
        if not stt_results:
            print("[Worker] STT 결과 없음 (음성 미감지 또는 오류).")
            return

        # 2. 각 STT 결과를 번역
        final_results = []
        for result in stt_results:
            # 'transcript' 키가 있고, 내용이 비어있지 않은 경우에만 처리
            if "transcript" in result and result["transcript"]:
                original_text = result["transcript"]
                translated_text = self.mt_engine.translate_text(original_text)
                
                final_results.append({
                    "speaker": result.get("speaker", 0), # 화자 정보가 없을 경우 기본값 0
                    "original": original_text,
                    "translated": translated_text
                })
        
        # 3. 최종 결과를 UI로 전송
        if final_results:
            print(f"[Worker] 처리 완료. UI로 결과 전송: {final_results}")
            self.translation_ready.emit(final_results)

    def stop(self):
        """외부에서 이 스레드를 중지시킬 때 호출."""
        if not self._is_running:
            return
            
        print("[Worker] 작업자 스레드 중지를 요청합니다...")
        self._is_running = False
        
        # run() 메서드의 self.exec()를 중지시켜 스레드가 정상적으로 종료되도록 함
        self.quit()


# --- 이 파일을 직접 실행하여 모든 백엔드 파이프라인을 테스트하는 부분 ---
if __name__ == '__main__':
    from PySide6.QtWidgets import QApplication
    import sys
    import time

    app = QApplication(sys.argv)

    class BackendTester(QObject):
        @Slot(list)
        def on_translation_ready(self, results):
            print("\n" + "="*20 + " 최종 결과 수신 (UI) " + "="*20)
            for result in results:
                print(f"  [화자 {result['speaker']}]")
                print(f"    - 원문: {result['original']}")
                print(f"    - 번역: {result['translated']}")
            print("="*62 + "\n")

        @Slot(str)
        def on_worker_error(self, message):
            print(f"\n!!!!!!!!! 작업자 오류 발생: {message} !!!!!!!!!\n")

    print("===== 전체 백엔드 파이프라인 테스트 시작 =====")
    print("API 키와 오디오 장치가 올바른지 확인하세요.")
    
    try:
        config = ConfigManager()
        tester = BackendTester()
        worker = Worker(config)

        worker.translation_ready.connect(tester.on_translation_ready)
        worker.worker_error.connect(tester.on_worker_error)
        
        worker.start()

        print("\n--- 30초 동안 테스트를 실행합니다. 2명 이상이 대화하는 소리를 틀어주세요. ---")
        app.processEvents()
        time.sleep(30)

    except (FileNotFoundError, ValueError, ConnectionError) as e:
        print(f"테스트 시작 전 오류 발생: {e}")
        sys.exit(1)
        
    finally:
        print("\n--- 테스트 종료. Worker 스레드를 중지합니다. ---")
        if 'worker' in locals() and worker.isRunning():
            worker.stop()
            worker.wait(5000) # 최대 5초간 종료 대기
    
    print("===== 테스트 프로그램 종료. =====")
    sys.exit()