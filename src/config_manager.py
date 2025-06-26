import json
import os
import sys

class ConfigManager:
    def __init__(self, file_name='config.json'):
        # 실행 파일(.exe) 환경과 스크립트(.py) 환경 모두에서 경로를 올바르게 찾음
        if getattr(sys, 'frozen', False):
            # PyInstaller 등으로 패키징된 경우
            base_path = os.path.dirname(sys.executable)
        else:
            # 일반적인 파이썬 스크립트로 실행된 경우
            base_path = os.path.dirname(os.path.abspath(__file__))
            # src 폴더 안에 있으므로, 상위 폴더(프로젝트 루트)로 이동
            base_path = os.path.join(base_path, '..')

        self.file_path = os.path.join(base_path, file_name)
        self.config = self.load_config()

    def get_default_config(self):
        """기본 설정값을 반환합니다."""
        return {
            # --- API Keys ---
            "google_credentials_path": "",
            "deepl_api_key": "",

            # --- Language Settings ---
            "source_language": "en-US",
            "target_language": "KO",

            # --- Audio Settings ---
            "audio_input_device_name": "CABLE Input (VB-Audio Virtual Cable)",
            
            # --- Speaker Diarization Settings ---
            "buffer_seconds": 5,
            "speaker_count": 2,

            # --- Hotkey Settings ---
            "hotkey_start_translate": "ctrl+f9",
            "hotkey_stop_translate": "ctrl+f10",

            # --- Overlay Style Settings ---
            "overlay_font_family": "Malgun Gothic",
            "overlay_font_size": 18,
            "overlay_font_color": "#FFFFFF",
            "overlay_bg_color": "rgba(0, 0, 0, 160)"
        }

    def load_config(self):
        """설정 파일(config.json)을 로드합니다. 파일이 없으면 기본값으로 생성합니다."""
        default_config = self.get_default_config()
        if not os.path.exists(self.file_path):
            print(f"설정 파일이 존재하지 않아, 기본값으로 '{self.file_path}'를 생성합니다.")
            self.save_config(default_config)
            return default_config

        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                loaded_config = json.load(f)
            
            # 기본 설정에 있는 모든 키가 로드된 설정에도 있는지 확인
            # 새로운 버전의 프로그램에서 추가된 설정이 있을 경우를 대비
            for key, value in default_config.items():
                if key not in loaded_config:
                    loaded_config[key] = value
            
            self.save_config(loaded_config) # 업데이트된 내용으로 다시 저장
            return loaded_config

        except (json.JSONDecodeError, IOError) as e:
            print(f"설정 파일 읽기 오류: {e}. 기본 설정으로 복구합니다.")
            self.save_config(default_config)
            return default_config

    def save_config(self, config_data):
        """현재 설정을 파일에 저장합니다."""
        self.config = config_data
        try:
            with open(self.file_path, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=4, ensure_ascii=False)
        except IOError as e:
            print(f"설정 파일 저장 오류: {e}")

    def get(self, key):
        """특정 설정값을 가져옵니다."""
        return self.config.get(key)

    def set(self, key, value):
        """특정 설정값을 변경하고 즉시 파일에 저장합니다."""
        self.config[key] = value
        self.save_config(self.config)

# 이 파일을 직접 실행하여 테스트할 수 있습니다.
if __name__ == '__main__':
    config_manager = ConfigManager()
    print("현재 설정 경로:", config_manager.file_path)
    print("로드된 설정:")
    print(json.dumps(config_manager.config, indent=4, ensure_ascii=False))
    
    # 값 변경 테스트
    # config_manager.set("target_language", "JA")
    # print("\n변경된 설정:")
    # print(json.dumps(config_manager.config, indent=4, ensure_ascii=False))