# ariel_client/src/config_manager.py (이 코드로 전체 교체)
import json
import os
import sys
import logging
from PySide6.QtCore import QObject, Signal
import uuid 

logger = logging.getLogger(__name__)

# [해결] _update_recursively 함수를 파일의 적절한 위치에 정의합니다.
def _update_recursively(d, u):
    """
    사전 d를 사전 u의 내용으로 재귀적으로 업데이트합니다.
    u에 있는 키가 d에 없으면 추가하고, d와 u의 값이 모두 사전이면
    재귀적으로 호출합니다.
    d가 업데이트되었으면 True를 반환하고, 아니면 False를 반환합니다.
    """
    updated = False
    for k, v in u.items():
        if k not in d:
            d[k] = v
            updated = True
        elif isinstance(d.get(k), dict) and isinstance(v, dict):
            if _update_recursively(d[k], v):
                updated = True
    return updated

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

    def get_default_config(self):
        """프로그램의 모든 기본 설정을 반환합니다."""
        return {
            "is_first_run": True,
            "api_base_url": "http://127.0.0.1:8000",
            "deepl_api_key": "",
            "app_theme": "dark",
            "app_language": "auto",
            "client_id": "",
            "stt_model_size": "medium",
            "stt_available_models": ["tiny", "base", "small", "medium"],
            "stt_device": "auto",
            "stt_compute_type": "auto",

            # 번역 설정
            "stt_source_language": "auto",
            "stt_target_language": "auto",
            "ocr_source_language": "auto",
            "ocr_target_language": "auto",

            # 오디오 설정
            "audio_input_device_index": None,
            "use_vad": False,
            "vad_sensitivity": 3,
            "silence_db_threshold": -50.0,
            "silence_threshold_s": 1.5,
            "min_audio_length_s": 0.5,
            "fixed_chunk_duration_s": 4.0,
            
            # OCR 설정
            "ocr_mode": "Standard Overlay",
            
            # 오버레이 스타일 및 동작
            "stt_overlay_style": {
                "font_family": "Malgun Gothic", "font_size": 18,
                "font_color": "#FFFFFF", "background_color": "rgba(0, 0, 0, 0.8)",
                "is_draggable": True,
                # [추가] 오버레이 강화 기능 설정
                "max_messages": 3,
                "show_original_text": True,
                "original_text_font_size_offset": -4, # 원문 폰트 크기 오프셋
                "original_text_font_color": "#BBBBBB", # 원문 폰트 색상
            },
            "ocr_overlay_style": {
                "font_family": "Malgun Gothic", "font_size": 14,
                "font_color": "#FFFFFF", "background_color": "rgba(20, 20, 20, 0.9)",
                "is_draggable": True,
            },

            # 오버레이 위치/크기
            "overlay_pos_x": None, "overlay_pos_y": None,
            "overlay_width": 800, "overlay_height": 250,

            # 단축키
            "hotkey_toggle_stt": "alt+1", "hotkey_toggle_ocr": "alt+2",
            "hotkey_toggle_setup": "alt+`", "hotkey_quit_app": "alt+q",
            
            # 알림
            "notification_volume": 80,
            "sound_app_start": "assets/sounds/app_start.wav",
            "sound_stt_start": "assets/sounds/stt_start.wav",
            "sound_ocr_start": "assets/sounds/ocr_start.wav",
            "sound_stt_stop": "assets/sounds/stt_stop.wav",
            "sound_ocr_stop": "assets/sounds/ocr_stop.wav",
            
            # 커스텀 테마
            "custom_theme_colors": {
                "BACKGROUND_PRIMARY": "#1e2b37", "BACKGROUND_SECONDARY": "#283747",
                "BACKGROUND_TERTIARY": "#212f3c", "TEXT_PRIMARY": "#eaf2f8",
                "TEXT_HEADER": "#ffffff", "TEXT_MUTED": "#85929e",
                "INTERACTIVE_NORMAL": "#546e7a", "INTERACTIVE_HOVER": "#607d8b",
                "INTERACTIVE_ACCENT": "#3498db", "INTERACTIVE_ACCENT_HOVER": "#5dade2",
                "BORDER_COLOR": "#3c4f62"
            },
        }

    def _load_or_create_config(self):
        default_config = self.get_default_config()
        config_updated = False # 플래그 초기화

        if not os.path.exists(self.file_path):
            self._save_config_to_file(default_config)
            # 처음 생성 시 client_id를 추가해야 함
            if not default_config.get("client_id"):
                deepl_key = default_config.get("deepl_api_key", "")
                if deepl_key and len(deepl_key) > 8:
                    new_id = f"deepl_{deepl_key[:4]}_{deepl_key[-4:]}"
                else:
                    new_id = f"uuid_{str(uuid.uuid4())}"
                default_config["client_id"] = new_id
                logger.info(f"새로운 클라이언트 ID 생성: {new_id}")
                self._save_config_to_file(default_config)
            return default_config
        
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                loaded_config = json.load(f)

            if not loaded_config.get("client_id"):
                deepl_key = loaded_config.get("deepl_api_key", "")
                if deepl_key and len(deepl_key) > 8:
                    new_id = f"deepl_{deepl_key[:4]}_{deepl_key[-4:]}"
                else:
                    new_id = f"uuid_{str(uuid.uuid4())}"
                loaded_config["client_id"] = new_id
                logger.info(f"새로운 클라이언트 ID 생성: {new_id}")
                config_updated = True

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