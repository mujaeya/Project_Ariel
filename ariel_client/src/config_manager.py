# ariel_client/src/config_manager.py (완성된 최종 코드)
import json
import os
import sys
import copy
import logging

logger = logging.getLogger(__name__)

class ConfigManager:
    def __init__(self, file_name='config.json'):
        # PyInstaller로 패키징되었을 때와 개발 환경을 모두 지원하는 경로 설정
        if getattr(sys, 'frozen', False):
            # 실행 파일이 있는 디렉토리
            base_path = os.path.dirname(sys.executable)
        else:
            # src 폴더의 상위, 즉 프로젝트 루트
            base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        self.file_path = os.path.join(base_path, file_name)
        self.config = self.load_config()

    def get_default_profile_settings(self):
        """프로필 하나에 들어갈 모든 세부 설정의 기본값을 반환합니다."""
        return {
            "is_first_run": True,
            "api_base_url": "http://127.0.0.1:8000",
            "deepl_api_key": "",
            "source_languages": ["EN-US"],
            "target_languages": ["KO"],
            "app_theme": "dark",
            "app_language": "en",
            "stt_source_language": "auto",
            "stt_target_language": "KO",
            "ocr_source_language": "auto",
            "ocr_target_language": "KO",
            "custom_theme_colors": {
                "BACKGROUND_PRIMARY": "#1e2b37", "BACKGROUND_SECONDARY": "#283747",
                "BACKGROUND_TERTIARY": "#212f3c", "TEXT_PRIMARY": "#eaf2f8",
                "TEXT_HEADER": "#ffffff", "TEXT_MUTED": "#85929e",
                "INTERACTIVE_NORMAL": "#546e7a", "INTERACTIVE_HOVER": "#607d8b",
                "INTERACTIVE_ACCENT": "#3498db", "INTERACTIVE_ACCENT_HOVER": "#5dade2",
                "BORDER_COLOR": "#3c4f62"
            },
            "ocr_engine": "default", "ocr_mode": "overlay", "vad_sensitivity": 3,
            "silence_threshold_s": 1.0, "min_audio_length_s": 0.5,
            "stt_overlay_style": {
                "font_family": "Malgun Gothic", "font_size": 18,
                "font_color": "#FFFFFF", "background_color": "rgba(0, 0, 0, 0.8)"
            },
            "ocr_overlay_style": {
                "font_family": "Malgun Gothic", "font_size": 14,
                "font_color": "#FFFFFF", "background_color": "rgba(20, 20, 20, 0.9)"
            },
            "show_original_text": True, "original_text_font_size_offset": -2,
            "original_text_font_color": "#BBBBBB",
            "overlay_pos_x": None, "overlay_pos_y": None,
            "overlay_width": 800, "overlay_height": 250,
            "hotkey_toggle_stt": "alt+1", "hotkey_toggle_ocr": "alt+2",
            "hotkey_toggle_setup": "alt+`", "hotkey_quit_app": "alt+q",
            "sound_master_volume": 80,
            "sound_app_start": "assets/sounds/app_start.wav",
            "sound_stt_start": "assets/sounds/stt_start.wav",
            "sound_ocr_start": "assets/sounds/ocr_start.wav",
            "sound_stt_stop": "assets/sounds/stt_stop.wav",
            "sound_ocr_stop": "assets/sounds/ocr_stop.wav"
        }

    def get_default_config(self):
        """전체 설정 파일의 기본 구조를 반환합니다."""
        return {
            "is_first_run": True,
            "active_profile": "기본 프로필",
            "profiles": {"기본 프로필": self.get_default_profile_settings()}
        }

    def load_config(self):
        """설정 파일을 로드합니다. 파일이 없으면 새로 생성하고, 기존 파일에 누락된 키가 있으면 기본값으로 채웁니다."""
        if not os.path.exists(self.file_path):
            new_config = self.get_default_config()
            self.save_config_data(new_config)
            return new_config
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                loaded_config = json.load(f)
            
            config_updated = False
            default_full_config = self.get_default_config()

            # 최상위 레벨의 키 마이그레이션
            for key, value in default_full_config.items():
                if key != "profiles" and key not in loaded_config:
                    loaded_config[key] = value
                    config_updated = True
            
            # 각 프로필 내부의 키 마이그레이션
            default_profile_keys = self.get_default_profile_settings()
            for profile_name in list(loaded_config.get("profiles", {}).keys()):
                profile = loaded_config["profiles"][profile_name]
                for key, value in default_profile_keys.items():
                    if key not in profile:
                        profile[key] = value
                        config_updated = True
                    # 중첩된 딕셔너리(custom_theme_colors) 내부 키까지 확인
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
        """내부적으로 설정을 파일에 저장하는 메서드입니다. (로깅 기능 포함)"""
        self.config = config_data
        try:
            with open(self.file_path, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=4, ensure_ascii=False)
            logger.info(f"설정이 '{self.file_path}' 파일에 저장되었습니다.")
        except IOError as e:
            logger.error(f"설정 파일 저장 실패: {e}", exc_info=True)

    def save_config(self):
        """현재 설정(self.config)을 파일에 저장하는 public 메서드입니다."""
        self.save_config_data(self.config)

    def reset_config(self):
        """모든 설정을 기본값으로 초기화합니다."""
        new_config = self.get_default_config()
        self.save_config_data(new_config)
        return new_config

    def get_active_profile(self):
        """현재 활성화된 프로필의 설정 데이터를 반환합니다."""
        active_profile_name = self.config.get("active_profile", "기본 프로필")
        profiles = self.config.get("profiles", {})
        if active_profile_name not in profiles:
            active_profile_name = list(profiles.keys())[0] if profiles else "기본 프로필"
        return profiles.get(active_profile_name, self.get_default_profile_settings())

    def get(self, key, default=None):
        """전역 설정 또는 활성 프로필에서 설정 값을 가져옵니다."""
        if key in self.config and key != "profiles":
            return self.config.get(key, default)
        return self.get_active_profile().get(key, default)

    def set(self, key, value, is_global=False):
        """전역 또는 활성 프로필에 설정 값을 지정하고 즉시 파일에 저장합니다."""
        if is_global:
            self.config[key] = value
        else:
            profile_name = self.config.get("active_profile", "기본 프로필")
            # setdefault를 사용하여 'profiles'와 해당 프로필이 없는 경우에도 안전하게 처리
            self.config.setdefault("profiles", {}).setdefault(profile_name, self.get_default_profile_settings())[key] = value
        self.save_config()

    def get_profile_names(self):
        """모든 프로필의 이름 리스트를 반환합니다."""
        return list(self.config.get("profiles", {}).keys())
    
    def get_active_profile_name(self):
        """활성화된 프로필의 이름을 반환합니다."""
        return self.config.get("active_profile")
        
    def switch_profile(self, profile_name):
        """활성 프로필을 변경합니다."""
        if profile_name in self.config.get("profiles", {}):
            self.set("active_profile", profile_name, is_global=True)
            return True
        return False
        
    def add_profile(self, new_profile_name, from_profile=None):
        """새로운 프로필을 추가합니다."""
        profiles = self.config.setdefault("profiles", {})
        if new_profile_name in profiles:
            return False, "이미 존재하는 프로필 이름입니다."
        
        # from_profile이 있으면 해당 설정을, 없으면 기본 설정을 복사
        base_settings = profiles.get(from_profile, self.get_default_profile_settings())
        profiles[new_profile_name] = copy.deepcopy(base_settings)
        self.save_config()
        return True, "성공"
        
    def remove_profile(self, profile_name):
        """지정된 프로필을 삭제합니다. (최소 1개의 프로필은 유지)"""
        profiles = self.config.get("profiles", {})
        n_profiles = len(profiles)
        if profile_name not in profiles or n_profiles <= 1:
            return False, "프로필 삭제에 실패했습니다."
        
        del profiles[profile_name]
        
        # 삭제된 프로필이 활성 프로필이었다면 다른 프로필을 활성화
        if self.config.get("active_profile") == profile_name:
            self.set("active_profile", list(profiles.keys())[0], is_global=True)
        else:
            self.save_config() # 활성 프로필 변경이 없었으므로 단순 저장 호출
            
        return True, "성공"

    def rename_profile(self, old_name, new_name):
        """프로필의 이름을 변경합니다."""
        profiles = self.config.get("profiles", {})
        if old_name not in profiles or new_name in profiles:
            return False, "프로필 이름 변경에 실패했습니다."
        
        profiles[new_name] = profiles.pop(old_name)
        
        # 이름이 변경된 프로필이 활성 프로필이었다면, 활성 프로필 정보도 업데이트
        if self.config.get("active_profile") == old_name:
            self.set("active_profile", new_name, is_global=True)
        else:
            self.save_config() # 활성 프로필 변경이 없었으므로 단순 저장 호출
            
        return True, "성공"