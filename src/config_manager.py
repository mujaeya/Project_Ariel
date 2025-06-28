import json
import os
import sys

class ConfigManager:
    def __init__(self, file_name='config.json'):
        if getattr(sys, 'frozen', False):
            base_path = os.path.dirname(sys.executable)
        else:
            base_path = os.path.dirname(os.path.abspath(__file__))
            base_path = os.path.join(base_path, '..')

        self.file_path = os.path.join(base_path, file_name)
        self.config = self.load_config()

    def get_default_config(self):
        """기본 설정값을 반환합니다."""
        return {
            "google_credentials_path": "",
            "deepl_api_key": "",
            "source_languages": ["en-US"],
            "target_languages": ["KO"],
            "translation_formality": "default",
            "sentence_commit_delay_ms": 700,
            "use_video_model": False,
            "buffer_seconds": 7,
            "hotkey_start_translate": "ctrl+f9",
            "hotkey_stop_translate": "ctrl+f10",
            "hotkey_toggle_setup_window": "ctrl+f12",
            
            "theme": "dark",
            "themes": {
                "dark": {
                    "overlay_font_color": "#FFFFFF",
                    "overlay_bg_color": "rgba(0, 0, 0, 160)",
                    "original_text_font_color": "#BBBBBB"
                },
                "light": {
                    "overlay_font_color": "#000000",
                    "overlay_bg_color": "rgba(255, 255, 255, 180)",
                    "original_text_font_color": "#555555"
                }
            },
            # --------------------------

            "overlay_font_family": "Malgun Gothic",
            "overlay_font_size": 18,
            "overlay_font_color": "#FFFFFF", 
            "overlay_bg_color": "rgba(0, 0, 0, 160)",
            "show_original_text": True,
            "original_text_font_size_offset": -4,
            "original_text_font_color": "#BBBBBB",
            "overlay_geometry": None
        }

    def load_config(self):
        default_config = self.get_default_config()
        if not os.path.exists(self.file_path):
            self.save_config(default_config)
            return default_config
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                loaded_config = json.load(f)
            
            if "source_language" in loaded_config and isinstance(loaded_config["source_language"], str):
                loaded_config["source_languages"] = [loaded_config["source_language"]]
                del loaded_config["source_language"]
            if "target_language" in loaded_config and isinstance(loaded_config["target_language"], str):
                loaded_config["target_languages"] = [loaded_config["target_language"]]
                del loaded_config["target_language"]
            if "speaker_count" in loaded_config: del loaded_config["speaker_count"]
            if "status_font_size" in loaded_config: del loaded_config["status_font_size"]
            if "status_font_color" in loaded_config: del loaded_config["status_font_color"]

            for key, value in default_config.items():
                if key not in loaded_config:
                    loaded_config[key] = value
            
            self.save_config(loaded_config)
            return loaded_config
        except (json.JSONDecodeError, IOError) as e:
            print(f"설정 파일 읽기 오류: {e}. 기본 설정으로 복구합니다.")
            self.save_config(default_config)
            return default_config

    def save_config(self, config_data):
        self.config = config_data
        try:
            with open(self.file_path, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=4, ensure_ascii=False)
        except IOError as e: print(f"설정 파일 저장 오류: {e}")

    def get(self, key, default=None):
        return self.config.get(key, default)

    def set(self, key, value):
        self.config[key] = value
        self.save_config(self.config)