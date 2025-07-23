# ariel_client/src/config_manager.py (이 코드로 전체 교체)
import json
import os
import sys
import logging
from PySide6.QtCore import QObject, Signal

logger = logging.getLogger(__name__)

class ConfigManager(QObject):
    settings_changed = Signal()

    def __init__(self, file_name='config.json', parent=None):
        super().__init__(parent)
        if getattr(sys, 'frozen', False):
            base_path = os.path.dirname(sys.executable)
        else:
            base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        self.file_path = os.path.join(base_path, file_name)
        self.config = self._load_or_create_config()

# In class ConfigManager:
# In class ConfigManager:
# In class ConfigManager:
    def get_default_config(self):
        """프로그램의 모든 기본 설정을 반환합니다."""
        return {
            "is_first_run": True,
            "api_base_url": "http://127.0.0.1:8000",
            "deepl_api_key": "",
            "app_theme": "dark",
            "app_language": "auto",

            # [V12.3] 오디오 입력 장치 인덱스 추가
            "audio_input_device_index": -1, # -1은 장치가 선택되지 않았음을 의미

            # 번역 설정
            "stt_source_language": "auto",
            "stt_target_language": "auto",
            "ocr_source_language": "auto",
            "ocr_target_language": "auto",
            
            "vad_threshold": 0.5,
            "vad_speech_pad_ms": 400,
            "vad_min_silence_duration_ms": 800,

            # OCR 설정
            "ocr_mode": "Standard Overlay",
            
            # ... 이하 설정은 동일 ...
            "stt_overlay_style": {
                "font_family": "Malgun Gothic", "font_size": 18,
                "font_color": "#FFFFFF", "background_color": "rgba(0, 0, 0, 0.8)",
                "is_draggable": True,
                "max_messages": 3,
                "show_original_text": True,
                "original_text_font_size_offset": -4,
                "original_text_font_color": "#BBBBBB",
            },
            "ocr_overlay_style": {
                "font_family": "Malgun Gothic", "font_size": 14,
                "font_color": "#FFFFFF", "background_color": "rgba(20, 20, 20, 0.9)",
                "is_draggable": True,
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
            "sound_ocr_stop": "assets/sounds/ocr_stop.wav",
            "custom_theme_colors": {
                "BACKGROUND_PRIMARY": "#1e2b37", "BACKGROUND_SECONDARY": "#283747",
                "BACKGROUND_TERTIARY": "#212f3c", "TEXT_PRIMARY": "#eaf2f8",
                "TEXT_HEADER": "#ffffff", "TEXT_MUTED": "#85929e",
                "INTERACTIVE_NORMAL": "#546e7a", "INTERACTIVE_HOVER": "#607d8b",
                "INTERACTIVE_ACCENT": "#3498db", "INTERACTIVE_ACCENT_HOVER": "#5dade2",
                "BORDER_COLOR": "#3c4f62"
            },
        }

    # ... 이하 코드는 변경 없음 ...
    def _load_or_create_config(self):
        default_config = self.get_default_config()

        if not os.path.exists(self.file_path):
            self._save_config_to_file(default_config)
            return default_config
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                loaded_config = json.load(f)

            config_updated = False
            def _update_recursively(target, source):
                is_updated = False
                for key, value in source.items():
                    if key not in target:
                        target[key] = value
                        is_updated = True
                    elif isinstance(value, dict) and isinstance(target.get(key), dict):
                        if _update_recursively(target.get(key, {}), value):
                            is_updated = True
                return is_updated

            if _update_recursively(loaded_config, default_config):
                config_updated = True

            if config_updated:
                self._save_config_to_file(loaded_config)

            return loaded_config
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"설정 파일 로드/분석 실패 '{self.file_path}': {e}. 기본값으로 복원합니다.")
            self._save_config_to_file(default_config)
            return default_config

    def _save_config_to_file(self, config_data):
        try:
            with open(self.file_path, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=4, ensure_ascii=False)
            logger.info(f"설정이 '{self.file_path}'에 저장되었습니다.")
        except IOError as e:
            logger.error(f"설정 파일 저장 실패: {e}", exc_info=True)

    def get(self, key, default=None):
        keys = key.split('.')
        val = self.config
        try:
            for k in keys: val = val[k]
            return val
        except (KeyError, TypeError): return default

    def set(self, key, value):
        keys = key.split('.'); d = self.config
        for k in keys[:-1]: d = d.setdefault(k, {})
        d[keys[-1]] = value

    def save(self):
        self._save_config_to_file(self.config)
        self.settings_changed.emit()

    def reset_to_defaults(self):
        self.config = self.get_default_config()
        self.save()