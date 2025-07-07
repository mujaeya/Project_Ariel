import json
import os
import sys
import copy
import logging

logger = logging.getLogger(__name__)

class ConfigManager:
    def __init__(self, file_name='config.json'):
        if getattr(sys, 'frozen', False):
            base_path = os.path.dirname(sys.executable)
        else:
            base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            
        self.file_path = os.path.join(base_path, file_name)
        self.config = self.load_config()

    # [핵심 복원] 삭제되었던 메서드 원상 복구
    def get_default_profile_settings(self):
        """프로필 하나에 들어갈 모든 세부 설정의 기본값을 반환합니다."""
        return {
            "is_first_run": True,
            # --- [문제 해결] 필수 API 키/URL 기본값만 추가 ---
            "api_base_url": "http://127.0.0.1:8000",
            "deepl_api_key": "",

            # --- 이하 모든 구조는 원본과 완벽하게 동일 ---
            "source_languages": ["EN-US"],
            "target_languages": ["KO"],
            "app_theme": "dark",
            "app_language": "en", # 기본 언어는 영어

            # --- [신규] 번역 언어 설정 ---
            "stt_source_language": "auto", # 자동 감지
            "stt_target_language": "KO",   # 한국어
            "ocr_source_language": "auto", # 자동 감지
            "ocr_target_language": "KO",   # 한국어

            "custom_theme_colors": {
                "BACKGROUND_PRIMARY": "#1e2b37", "BACKGROUND_SECONDARY": "#283747",
                "BACKGROUND_TERTIARY": "#212f3c", "TEXT_PRIMARY": "#eaf2f8",
                "TEXT_HEADER": "#ffffff", "TEXT_MUTED": "#85929e",
                "INTERACTIVE_NORMAL": "#546e7a", "INTERACTIVE_HOVER": "#607d8b",
                "INTERACTIVE_ACCENT": "#3498db", "INTERACTIVE_ACCENT_HOVER": "#5dade2",
                "BORDER_COLOR": "#3c4f62"
            },
            "ocr_engine": "default",
            "ocr_mode": "overlay",
            "vad_sensitivity": 3,
            "silence_threshold_s": 1.0,
            "min_audio_length_s": 0.5,
            "stt_overlay_style": {
                "font_family": "Malgun Gothic", "font_size": 18,
                "font_color": "#FFFFFF", "background_color": "rgba(0, 0, 0, 0.8)"
            },
            "ocr_overlay_style": {
                "font_family": "Malgun Gothic", "font_size": 14,
                "font_color": "#FFFFFF", "background_color": "rgba(20, 20, 20, 0.9)"
            },
            "show_original_text": True,
            "original_text_font_size_offset": -2,
            "original_text_font_color": "#BBBBBB",
            "overlay_pos_x": None, "overlay_pos_y": None,
            "overlay_width": 800, "overlay_height": 250,
            "hotkey_toggle_stt": "alt+1",
            "hotkey_toggle_ocr": "alt+2",
            "hotkey_toggle_setup": "alt+`",
            "hotkey_quit_app": "alt+q",
            "sound_master_volume": 80,
            "sound_app_start": "assets/sounds/app_start.wav",
            "sound_stt_start": "assets/sounds/stt_start.wav",
            "sound_ocr_start": "assets/sounds/ocr_start.wav",
            "sound_stt_stop": "assets/sounds/stt_stop.wav",
            "sound_ocr_stop": "assets/sounds/ocr_stop.wav"
        }

    # [핵심 복원] get_default_config 메서드 원상 복구
    def get_default_config(self):
        """전체 설정 파일의 기본 구조를 반환합니다."""
        return {
            "is_first_run": True,
            "active_profile": "기본 프로필",
            "profiles": {
                "기본 프로필": self.get_default_profile_settings()
            }
        }

    # [핵심 복원] 원본의 마이그레이션 로직을 그대로 사용 (더 안전함)
    def load_config(self):
        if not os.path.exists(self.file_path):
            new_config = self.get_default_config()
            self.save_config_data(new_config)
            return new_config
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                loaded_config = json.load(f)
            config_updated = False
            default_full_config = self.get_default_config()
            for key, value in default_full_config.items():
                if key != "profiles" and key not in loaded_config:
                    loaded_config[key] = value
                    config_updated = True
            default_profile_keys = self.get_default_profile_settings()
            for profile_name in list(loaded_config.get("profiles", {}).keys()):
                profile = loaded_config["profiles"][profile_name]
                for key, value in default_profile_keys.items():
                    if key not in profile:
                        profile[key] = value
                        config_updated = True
                    elif key == "custom_theme_colors" and isinstance(value, dict):
                        for sub_key, sub_value in value.items():
                            if sub_key not in profile[key]:
                                profile[key][sub_key] = sub_value
                                config_updated = True
            if config_updated:
                self.save_config_data(loaded_config)
            return loaded_config
        except (json.JSONDecodeError, IOError):
            return self.reset_config()

    def save_config_data(self, config_data):
        self.config = config_data
        try:
            with open(self.file_path, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=4, ensure_ascii=False)
        except IOError:
            pass

    def reset_config(self):
        new_config = self.get_default_config()
        self.save_config_data(new_config)
        return new_config

    def get_active_profile(self):
        active_profile_name = self.config.get("active_profile", "기본 프로필")
        profiles = self.config.get("profiles", {})
        if active_profile_name not in profiles:
            active_profile_name = list(profiles.keys())[0] if profiles else "기본 프로필"
        return profiles.get(active_profile_name, self.get_default_profile_settings())

    def get(self, key, default=None):
        if key in self.config and key != "profiles":
            return self.config.get(key, default)
        active_profile = self.get_active_profile()
        return active_profile.get(key, default)

    def set(self, key, value, is_global=False):
        if is_global:
            self.config[key] = value
        else:
            active_profile_name = self.config.get("active_profile", "기본 프로필")
            profiles = self.config.setdefault("profiles", {})
            profile = profiles.setdefault(active_profile_name, self.get_default_profile_settings())
            profile[key] = value
        self.save_config_data(self.config)

    def get_profile_names(self):
        return list(self.config.get("profiles", {}).keys())
        
    def get_active_profile_name(self):
        return self.config.get("active_profile")
        
    def switch_profile(self, profile_name):
        if profile_name in self.config.get("profiles", {}):
            self.set("active_profile", profile_name, is_global=True)
            return True
        return False
        
    def add_profile(self, new_profile_name, from_profile=None):
        profiles = self.config.setdefault("profiles", {})
        if new_profile_name in profiles:
            return False, "이미 존재하는 프로필 이름입니다."
        if from_profile and from_profile in profiles:
            base_settings = profiles[from_profile]
        else:
            base_settings = self.get_default_profile_settings()
        profiles[new_profile_name] = copy.deepcopy(base_settings)
        self.save_config_data(self.config)
        return True, "성공"
        
    def remove_profile(self, profile_name):
        profiles = self.config.get("profiles", {})
        if profile_name not in profiles or len(profiles) <= 1:
            return False, "프로필 삭제에 실패했습니다."
        del profiles[profile_name]
        if self.config.get("active_profile") == profile_name:
            new_active = list(profiles.keys())[0]
            self.set("active_profile", new_active, is_global=True)
        else:
            self.save_config_data(self.config)
        return True, "성공"

    def rename_profile(self, old_name, new_name):
        profiles = self.config.get("profiles", {})
        if old_name not in profiles or new_name in profiles:
            return False, "프로필 이름 변경에 실패했습니다."
        profiles[new_name] = profiles.pop(old_name)
        if self.config.get("active_profile") == old_name:
            self.set("active_profile", new_name, is_global=True)
        else:
            self.save_config_data(self.config)
        return True, "성공"