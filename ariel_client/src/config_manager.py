# ariel_client/src/config_manager.py (이 코드로 전체 교체)
import json
import os
import sys
import logging
from PySide6.QtCore import QObject, Signal

logger = logging.getLogger(__name__)

class ConfigManager(QObject):
    """
    프로그램의 모든 설정을 관리하는 단순화된 클래스.
    프로필 시스템을 제거하고 단일 설정 객체만 관리합니다.
    """
    settings_changed = Signal()

    def __init__(self, file_name='config.json', parent=None):
        super().__init__(parent)
        if getattr(sys, 'frozen', False):
            base_path = os.path.dirname(sys.executable)
        else:
            base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        self.file_path = os.path.join(base_path, file_name)
        self.config = self._load_or_create_config()

    def get_default_config(self):
        """프로그램의 모든 기본 설정을 반환하는 공개 메서드입니다."""
        return {
            "is_first_run": True,
            "api_base_url": "http://127.0.0.1:8000",
            "deepl_api_key": "",
            "app_theme": "dark",
            "app_language": "auto",
            "stt_source_language": "auto",
            "stt_target_language": "auto",
            "ocr_source_language": "auto",
            "ocr_target_language": "auto",
            "custom_theme_colors": {
                "BACKGROUND_PRIMARY": "#1e2b37", "BACKGROUND_SECONDARY": "#283747",
                "BACKGROUND_TERTIARY": "#212f3c", "TEXT_PRIMARY": "#eaf2f8",
                "TEXT_HEADER": "#ffffff", "TEXT_MUTED": "#85929e",
                "INTERACTIVE_NORMAL": "#546e7a", "INTERACTIVE_HOVER": "#607d8b",
                "INTERACTIVE_ACCENT": "#3498db", "INTERACTIVE_ACCENT_HOVER": "#5dade2",
                "BORDER_COLOR": "#3c4f62"
            },
            "ocr_mode": "Standard Overlay", # [수정] 기본값을 'Standard Overlay'로 변경
            "vad_sensitivity": 3,
            "silence_threshold_s": 1.0,
            "min_audio_length_s": 0.5,
            "stt_overlay_style": {
                "font_family": "Malgun Gothic", "font_size": 18,
                "font_color": "#FFFFFF", "background_color": "rgba(0, 0, 0, 0.8)",
                "show_original_text": True,
                "original_text_font_size_offset": -2,
                "original_text_font_color": "#BBBBBB"
            },
            "ocr_overlay_style": {
                "font_family": "Malgun Gothic", "font_size": 14,
                "font_color": "#FFFFFF", "background_color": "rgba(20, 20, 20, 0.9)"
            },
            "overlay_pos_x": None, "overlay_pos_y": None,
            "overlay_width": 800, "overlay_height": 250,
            "hotkey_toggle_stt": "alt+1", "hotkey_toggle_ocr": "alt+2",
            "hotkey_toggle_setup": "alt+`", "hotkey_quit_app": "alt+q",
            "notification_volume": 80,
            "sound_app_start": "assets/sounds/app_start.wav",
            "sound_stt_start": "assets/sounds/stt_start.wav",
            "sound_ocr_start": "assets/sounds/ocr_start.wav",
            "sound_stt_stop": "assets/sounds/stt_stop.wav",
            "sound_ocr_stop": "assets/sounds/ocr_stop.wav"
        }

    def _load_or_create_config(self):
        default_config = self.get_default_config()

        if not os.path.exists(self.file_path):
            self._save_config_to_file(default_config)
            return default_config
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                loaded_config = json.load(f)

            config_updated = False
            if "sound_master_volume" in loaded_config:
                loaded_config["notification_volume"] = loaded_config.pop("sound_master_volume")
                config_updated = True

            for key, value in default_config.items():
                if key not in loaded_config:
                    loaded_config[key] = value
                    config_updated = True
                elif isinstance(value, dict):
                    for sub_key, sub_value in value.items():
                        if sub_key not in loaded_config.get(key, {}):
                            loaded_config.setdefault(key, {})[sub_key] = sub_value
                            config_updated = True
            
            if config_updated:
                self._save_config_to_file(loaded_config)
            
            return loaded_config
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Failed to load/parse config file '{self.file_path}': {e}. Restoring defaults.")
            self._save_config_to_file(default_config)
            return default_config

    def _save_config_to_file(self, config_data):
        try:
            with open(self.file_path, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=4, ensure_ascii=False)
            logger.info(f"Settings saved to '{self.file_path}'.")
        except IOError as e:
            logger.error(f"Failed to save config file: {e}", exc_info=True)

    def get(self, key, default=None):
        return self.config.get(key, default)

    def set(self, key, value):
        self.config[key] = value
    
    def save(self):
        self._save_config_to_file(self.config)
        self.settings_changed.emit()
    
    def reset_to_defaults(self):
        self.config = self.get_default_config()
        self.save()