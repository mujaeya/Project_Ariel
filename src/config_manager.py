# src/config_manager.py (이 코드로 전체를 교체해주세요)
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
        """기본 설정값을 반환합니다. (단순화 버전)"""
        return {
            "google_credentials_path": "",
            "deepl_api_key": "",
            "source_languages": ["en-US"],
            "target_languages": ["KO"],
            "sentence_commit_delay_ms": 250,
            "hotkey_start_translate": "shift+1",
            "hotkey_stop_translate": "shift+2",
            "hotkey_toggle_setup_window": "shift+`",
            "hotkey_quit_app": "shift+0",
            "overlay_font_family": "Malgun Gothic",
            "overlay_font_size": 18,
            "overlay_font_color": "#FFFFFF",
            "overlay_bg_color": "rgba(0, 0, 0, 160)",
            "show_original_text": True,
            "original_text_font_size_offset": -2,
            "original_text_font_color": "#BBBBBB",
            "overlay_pos_x": None,
            "overlay_pos_y": None,
            "overlay_width": 800,
            "overlay_height": 100
        }

    def load_config(self):
        default_config = self.get_default_config()
        if not os.path.exists(self.file_path):
            self.save_config(default_config)
            return default_config
        
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                loaded_config = json.load(f)
            
            config_updated = False
            # 누락된 키가 있으면 기본값으로 추가
            for key, value in default_config.items():
                if key not in loaded_config:
                    loaded_config[key] = value
                    config_updated = True
            
            # 더 이상 사용되지 않는 키가 있으면 제거
            keys_to_remove = ["use_video_model", "translation_formality"]
            for key in keys_to_remove:
                if key in loaded_config:
                    del loaded_config[key]
                    config_updated = True

            if config_updated:
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
        except IOError as e:
            print(f"설정 파일 저장 오류: {e}")

    def get(self, key, default=None):
        return self.config.get(key, default)

    def set(self, key, value):
        self.config[key] = value
        self.save_config(self.config)

    def reset_to_defaults(self):
        """설정을 기본값으로 되돌리고 저장합니다."""
        defaults = self.get_default_config()
        self.save_config(defaults)
        self.config = defaults
        return defaults