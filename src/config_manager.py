# src/config_manager.py (프로필 시스템 적용 버전)
import json
import os
import sys
import copy

class ConfigManager:
    def __init__(self, file_name='config.json'):
        if getattr(sys, 'frozen', False):
            base_path = os.path.dirname(sys.executable)
        else:
            base_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')

        self.file_path = os.path.join(base_path, file_name)
        self.config = self.load_config()

    def get_default_config(self):
        """하나의 프로필에 대한 기본 설정값을 반환합니다."""
        return {
            "tesseract_path": "C:\Program Files\Tesseract-OCR",
            "google_credentials_path": "",
            "deepl_api_key": "",
            "source_languages": ["en-US"],
            "target_languages": ["KO"],
            "sentence_commit_delay_ms": 250,
            "hotkey_start_translate": "shift+1",
            "hotkey_stop_translate": "shift+2",
            "hotkey_ocr": "shift+3",             
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
        """
        설정 파일을 로드합니다.
        프로필 구조가 없으면, 기존 설정을 '기본 프로필'로 마이그레이션합니다.
        """
        if not os.path.exists(self.file_path):
            # 파일이 없으면 새로운 프로필 구조로 생성
            default_profile = self.get_default_config()
            new_config = {
                "active_profile": "기본 프로필",
                "profiles": {
                    "기본 프로필": default_profile
                }
            }
            self.save_config_data(new_config)
            return new_config
        
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                loaded_config = json.load(f)

            # --- 하위 호환성 마이그레이션 로직 ---
            if "profiles" not in loaded_config or "active_profile" not in loaded_config:
                print("구버전 설정 파일을 발견하여, 새로운 프로필 구조로 마이그레이션합니다.")
                old_config_copy = copy.deepcopy(loaded_config)
                
                # profiles, active_profile 키 제거
                old_config_copy.pop("profiles", None)
                old_config_copy.pop("active_profile", None)

                default_settings = self.get_default_config()
                # 기존 설정 파일의 값을 기본값 위에 덮어씁니다.
                default_settings.update(old_config_copy)

                loaded_config = {
                    "active_profile": "기본 프로필",
                    "profiles": {
                        "기본 프로필": default_settings
                    }
                }
                self.save_config_data(loaded_config)
            
            # --- 누락된 키 보완 로직 ---
            config_updated = False
            default_keys = self.get_default_config()
            for profile_name, profile_data in loaded_config["profiles"].items():
                for key, value in default_keys.items():
                    if key not in profile_data:
                        profile_data[key] = value
                        config_updated = True
            
            if config_updated:
                self.save_config_data(loaded_config)
            
            return loaded_config

        except (json.JSONDecodeError, IOError) as e:
            print(f"설정 파일 읽기 오류: {e}. 기본 설정으로 복구합니다.")
            default_profile = self.get_default_config()
            new_config = {
                "active_profile": "기본 프로필",
                "profiles": {
                    "기본 프로필": default_profile
                }
            }
            self.save_config_data(new_config)
            return new_config

    def save_config_data(self, config_data):
        """전체 설정 데이터를 파일에 저장합니다."""
        self.config = config_data
        try:
            with open(self.file_path, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=4, ensure_ascii=False)
        except IOError as e:
            print(f"설정 파일 저장 오류: {e}")

    def get_active_profile(self):
        """현재 활성화된 프로필의 설정 데이터를 반환합니다."""
        active_profile_name = self.config.get("active_profile", "기본 프로필")
        return self.config["profiles"].get(active_profile_name)

    def get(self, key, default=None):
        """활성화된 프로필에서 특정 설정 값을 가져옵니다."""
        active_profile = self.get_active_profile()
        if active_profile:
            return active_profile.get(key, default)
        return default

# ConfigManager 클래스 내부
    def set(self, key, value):
        """활성화된 프로필에 특정 설정 값을 저장합니다."""
        active_profile_name = self.config.get("active_profile", "기본 프로필")
        if active_profile_name in self.config["profiles"]:
            # <<<<<<< 핵심 수정: 경로 관련 설정은 슬래시로 변환하여 저장 >>>>>>>>>
            if key.endswith("_path") and isinstance(value, str):
                self.config["profiles"][active_profile_name][key] = value.replace("\\", "/")
            else:
                self.config["profiles"][active_profile_name][key] = value
            
            self.save_config_data(self.config) # 변경 후 전체 저장
    
    # --- 새로운 프로필 관리 메소드들 ---
    
    def get_profile_names(self):
        """모든 프로필의 이름 목록을 반환합니다."""
        return list(self.config.get("profiles", {}).keys())
        
    def get_active_profile_name(self):
        """활성화된 프로필의 이름을 반환합니다."""
        return self.config.get("active_profile")
        
    def switch_profile(self, profile_name):
        """활성 프로필을 전환합니다."""
        if profile_name in self.config["profiles"]:
            self.config["active_profile"] = profile_name
            self.save_config_data(self.config)
            print(f"프로필이 '{profile_name}'(으)로 전환되었습니다.")
            return True
        return False
        
# src/config_manager.py의 ConfigManager 클래스 내부

def add_profile(self, new_profile_name):
    """(재수정) 새로운 프로필을 합리적인 기본값으로 추가합니다."""
    if new_profile_name in self.config["profiles"]:
        return False, "이미 존재하는 프로필 이름입니다."
    
    new_profile_settings = self.get_default_config()

    # [핵심 수정] 원본 언어는 항상 'en-US' (미국 영어)로 고정합니다.
    new_profile_settings['source_languages'] = ['en-US']

    # [핵심 수정] 번역 언어를 시스템 언어에서 감지합니다.
    try:
        system_locale_name = QLocale.system().name()
        bcp47_code = QLocale(system_locale_name).bcp47Name()
        
        supported_codes_lower = {code.lower(): original_code for code in SUPPORTED_LANGUAGES.values()}

        # 시스템 언어(예: ko-kr) 또는 주 언어(예: ko)가 지원 목록에 있는지 확인
        if bcp47_code.lower() in supported_codes_lower:
            target_lang = supported_codes_lower[bcp47_code.lower()]
        elif bcp47_code.split('-')[0] in supported_codes_lower:
            target_lang = supported_codes_lower[bcp47_code.split('-')[0]]
        else:
            target_lang = 'KO' # 감지 실패 또는 미지원 시 한국어로 기본 설정

        new_profile_settings['target_languages'] = [target_lang]
            
    except Exception as e:
        logging.warning(f"시스템 언어 감지 실패: {e}. 기본 번역 언어로 설정합니다.")
        new_profile_settings['target_languages'] = ['KO']

    self.config["profiles"][new_profile_name] = new_profile_settings
    self.save_config_data(self.config)
    return True, "성공"
        
    def remove_profile(self, profile_name):
        """프로필을 삭제합니다."""
        if profile_name not in self.config["profiles"]:
            return False, "존재하지 않는 프로필입니다."
        if len(self.config["profiles"]) <= 1:
            return False, "최소 1개의 프로필은 유지해야 합니다."
            
        del self.config["profiles"][profile_name]
        
        # 삭제된 프로필이 활성 프로필이었다면, 다른 프로필로 전환
        if self.config["active_profile"] == profile_name:
            self.config["active_profile"] = list(self.config["profiles"].keys())[0]
            
        self.save_config_data(self.config)
        print(f"프로필 '{profile_name}'이(가) 삭제되었습니다.")
        return True, "성공"

    def rename_profile(self, old_name, new_name):
        """프로필의 이름을 변경합니다."""
        if old_name not in self.config["profiles"]:
            return False, "존재하지 않는 프로필입니다."
        if new_name in self.config["profiles"]:
            return False, "이미 존재하는 프로필 이름입니다."
            
        self.config["profiles"][new_name] = self.config["profiles"].pop(old_name)
        
        if self.config["active_profile"] == old_name:
            self.config["active_profile"] = new_name
            
        self.save_config_data(self.config)
        print(f"프로필 이름이 '{old_name}'에서 '{new_name}'(으)로 변경되었습니다.")
        return True, "성공"