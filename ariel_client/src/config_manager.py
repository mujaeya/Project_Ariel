import json
import os
import sys
import copy
import logging

# setup_window.py와 중복되므로 한 곳(예: utils.py)으로 옮기는 것을 권장합니다.
# 우선은 여기에 임시로 유지합니다.
SUPPORTED_LANGUAGES = {
    "Bulgarian": "BG", "Czech": "CS", "Danish": "DA", "German": "DE",
    "Greek": "EL", "English (British)": "EN-GB", "English (American)": "EN-US",
    "Spanish": "ES", "Estonian": "ET", "Finnish": "FI", "French": "FR",
    "Hungarian": "HU", "Indonesian": "ID", "Italian": "IT", "Japanese": "JA",
    "Korean": "KO", "Lithuanian": "LT", "Latvian": "LV", "Norwegian": "NB",
    "Dutch": "NL", "Polish": "PL", "Portuguese (Brazilian)": "PT-BR",
    "Portuguese (European)": "PT-PT", "Romanian": "RO", "Russian": "RU",
    "Slovak": "SK", "Slovenian": "SL", "Swedish": "SV", "Turkish": "TR",
    "Ukrainian": "UK", "Chinese (Simplified)": "ZH"
}

class ConfigManager:
    def __init__(self, file_name='config.json'):
        if getattr(sys, 'frozen', False):
            base_path = os.path.dirname(sys.executable)
        else:
            base_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')

        self.file_path = os.path.join(base_path, file_name)
        self.config = self.load_config()

    def get_default_profile_settings(self):
        """[확장] 프로필 하나에 들어갈 모든 세부 설정의 기본값을 반환합니다."""
        return {
            # --- 서버 설정 (이제 UI에서 숨겨짐) ---
            "server_url": "http://127.0.0.1:8000",
            "deepl_api_key": "",

            "source_languages": ["en-US"], # 원본 언어
            "target_languages": ["KO"],    # 번역할 대상 언어

            # --- [신규] 프로그램 설정 ---
            "app_theme": "dark",  # dark, light, custom
            "app_language": "system",  # system, ko, en, ja 등
            "custom_theme_colors": {
                "background": "#2c3e50",
                "text": "#ecf0f1",
                "primary": "#3498db",
                "secondary": "#2980b9"
            },

            # --- [신규] OCR 설정 ---
            "ocr_engine": "default",
            "ocr_mode": "overlay", # overlay, patch
            
            # --- [신규] STT 설정 ---
            "vad_sensitivity": 3,
            "silence_threshold_s": 1.0,
            "min_audio_length_s": 0.5,

            # --- 스타일 설정 (기존) ---
            "overlay_font_family": "Malgun Gothic",
            "overlay_font_size": 18,
            "overlay_font_color": "#FFFFFF",
            "overlay_bg_color": "rgba(0, 0, 0, 0.8)",
            "show_original_text": True,
            "original_text_font_size_offset": -2,
            "original_text_font_color": "#BBBBBB",
            "overlay_pos_x": None,
            "overlay_pos_y": None,
            "overlay_width": 800,
            "overlay_height": 250,

            # --- 단축키 및 알림음 (기존) ---
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

    def get_default_config(self):
        """전체 설정 파일의 기본 구조를 반환합니다."""
        return {
            "is_first_run": True,
            "active_profile": "기본 프로필",
            "profiles": {
                "기본 프로필": self.get_default_profile_settings()
            }
        }

    def load_config(self):
        """
        설정 파일을 로드합니다. 파일이 없으면 새로 생성하고,
        기존 파일에 누락된 설정 키가 있으면 기본값으로 채워줍니다.
        """
        if not os.path.exists(self.file_path):
            logging.info("설정 파일이 없어 새로 생성합니다.")
            new_config = self.get_default_config()
            self.save_config_data(new_config)
            return new_config
        
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                loaded_config = json.load(f)

            # --- 누락된 키 보완 로직 (하위 호환성 보장) ---
            config_updated = False
            default_full_config = self.get_default_config()

            # 1. 최상위 키(is_first_run, active_profile 등) 검사 및 추가
            for key, value in default_full_config.items():
                if key != "profiles" and key not in loaded_config:
                    loaded_config[key] = value
                    config_updated = True
                    logging.info(f"전역 설정에 누락된 키 '{key}'를 추가했습니다.")
            
            # 구버전(profiles 키가 없는) 설정 파일 마이그레이션
            if "profiles" not in loaded_config:
                 loaded_config["profiles"] = {"기본 프로필": {}}
                 # 기존 설정들을 '기본 프로필'로 이동
                 for key, value in loaded_config.items():
                    if key not in ["profiles", "active_profile", "is_first_run"]:
                        loaded_config["profiles"]["기본 프로필"][key] = value
                 config_updated = True

            # 2. 각 프로필 내부의 키 검사 및 추가
            default_profile_keys = self.get_default_profile_settings()
            for profile_name in list(loaded_config.get("profiles", {}).keys()):
                for key, value in default_profile_keys.items():
                    if key not in loaded_config["profiles"][profile_name]:
                        loaded_config["profiles"][profile_name][key] = value
                        config_updated = True
                        logging.info(f"프로필 '{profile_name}'에 누락된 키 '{key}'를 추가했습니다.")
            
            if config_updated:
                logging.info("설정 파일이 업데이트되어 새 항목을 추가하고 저장합니다.")
                self.save_config_data(loaded_config)
            
            return loaded_config

        except (json.JSONDecodeError, IOError) as e:
            logging.error(f"설정 파일 읽기 오류: {e}. 기본 설정으로 복구합니다.")
            return self.reset_config()

    def save_config_data(self, config_data):
        """전체 설정 데이터를 파일에 저장합니다."""
        self.config = config_data
        try:
            with open(self.file_path, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=4, ensure_ascii=False)
        except IOError as e:
            logging.error(f"설정 파일 저장 오류: {e}")

    def reset_config(self):
        """설정 파일을 기본값으로 초기화합니다."""
        if os.path.exists(self.file_path):
            try:
                os.remove(self.file_path)
                logging.info("기존 설정 파일을 삭제했습니다.")
            except OSError as e:
                logging.error(f"설정 파일 삭제 실패: {e}")
        new_config = self.get_default_config()
        self.save_config_data(new_config)
        return new_config

    def get_active_profile(self):
        """현재 활성화된 프로필의 설정 데이터를 반환합니다."""
        active_profile_name = self.config.get("active_profile", "기본 프로필")
        profiles = self.config.get("profiles", {})
        
        # 활성 프로필이 존재하지 않거나, 프로필 목록이 비정상일 경우 복구
        if not profiles:
            default_settings = self.get_default_profile_settings()
            self.config["profiles"] = {"기본 프로필": default_settings}
            self.config["active_profile"] = "기본 프로필"
            self.save_config_data(self.config)
            return default_settings
            
        if active_profile_name not in profiles:
            active_profile_name = list(profiles.keys())[0]
            self.set("active_profile", active_profile_name, is_global=True)
            
        return profiles.get(active_profile_name, {})

    def get(self, key, default=None):
        """
        설정 값을 가져옵니다. 전역 설정에 키가 있으면 그 값을,
        없으면 활성화된 프로필에서 값을 찾아 반환합니다.
        """
        # 전역 설정(is_first_run, active_profile)에 키가 있는지 먼저 확인
        if key in self.config and key != "profiles":
            return self.config.get(key, default)
        
        # 없으면 활성 프로필에서 검색
        active_profile = self.get_active_profile()
        return active_profile.get(key, default)

    def set(self, key, value, is_global=False):
        """
        설정 값을 저장합니다. is_global=True이면 전역 설정을,
        아니면 활성화된 프로필의 설정을 변경합니다.
        """
        if is_global:
            self.config[key] = value
        else:
            active_profile_name = self.config.get("active_profile", "기본 프로필")
            if "profiles" not in self.config:
                self.config["profiles"] = {}
            if active_profile_name not in self.config["profiles"]:
                self.config["profiles"][active_profile_name] = {}
            
            # 경로 관련 설정은 슬래시로 변환하여 저장
            if isinstance(value, str) and ("sound_" in key or key.endswith("_path")):
                 self.config["profiles"][active_profile_name][key] = value.replace("\\", "/")
            else:
                self.config["profiles"][active_profile_name][key] = value
        
        self.save_config_data(self.config)

    # --- 프로필 관리 메소드들 ---
    
    def get_profile_names(self):
        return list(self.config.get("profiles", {}).keys())
        
    def get_active_profile_name(self):
        return self.config.get("active_profile")
        
    def switch_profile(self, profile_name):
        if profile_name in self.config.get("profiles", {}):
            self.set("active_profile", profile_name, is_global=True)
            logging.info(f"프로필이 '{profile_name}'(으)로 전환되었습니다.")
            return True
        return False
        
    def add_profile(self, new_profile_name):
        if new_profile_name in self.config.get("profiles", {}):
            return False, "이미 존재하는 프로필 이름입니다."
        
        active_profile = self.get_active_profile()
        new_profile_settings = copy.deepcopy(active_profile)

        self.config["profiles"][new_profile_name] = new_profile_settings
        self.save_config_data(self.config)
        return True, "성공"
        
    def remove_profile(self, profile_name):
        profiles = self.config.get("profiles", {})
        if profile_name not in profiles:
            return False, "존재하지 않는 프로필입니다."
        if len(profiles) <= 1:
            return False, "최소 1개의 프로필은 유지해야 합니다."
            
        del profiles[profile_name]
        
        if self.config.get("active_profile") == profile_name:
            # 활성 프로필이 삭제되면 다른 프로필을 활성화
            self.set("active_profile", list(profiles.keys())[0], is_global=True)
        else:
            self.save_config_data(self.config) # active_profile 변경 없을 시 단순 저장

        logging.info(f"프로필 '{profile_name}'이(가) 삭제되었습니다.")
        return True, "성공"

    def rename_profile(self, old_name, new_name):
        profiles = self.config.get("profiles", {})
        if old_name not in profiles:
            return False, "존재하지 않는 프로필입니다."
        if new_name in profiles:
            return False, "이미 존재하는 프로필 이름입니다."
            
        profiles[new_name] = profiles.pop(old_name)
        
        if self.config.get("active_profile") == old_name:
            self.set("active_profile", new_name, is_global=True)
        else:
            self.save_config_data(self.config)

        logging.info(f"프로필 이름이 '{old_name}'에서 '{new_name}'(으)로 변경되었습니다.")
        return True, "성공"