# ariel_client/src/core/hotkey_manager.py (새 파일)
import logging
import keyboard
from PySide6.QtCore import QObject, Signal, QTimer
from ..config_manager import ConfigManager

class HotkeyManager(QObject):
    """전역 단축키를 감지하고 신호를 보내는 클래스"""
    hotkey_pressed = Signal(str)

    def __init__(self, config_manager: ConfigManager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        
        # 단축키 이름과 설정 파일의 키를 매핑
        self.hotkey_map = {
            "start_ocr": "hotkey_ocr",
            "toggle_translation": "hotkey_start_translate",
            "open_setup": "hotkey_toggle_setup_window",
            "quit_app": "hotkey_quit_app"
        }
        self.hotkey_states = {name: False for name in self.hotkey_map.keys()}

        self.timer = QTimer(self)
        self.timer.setInterval(50)  # 50ms 마다 체크
        self.timer.timeout.connect(self.check_hotkeys)
        self.timer.start()
        logging.info("단축키 관리자 시작.")

    def check_hotkeys(self):
        """설정된 단축키가 눌렸는지 주기적으로 확인합니다."""
        for action_name, config_key in self.hotkey_map.items():
            key_str = self.config_manager.get(config_key)
            if not key_str:
                continue
            
            try:
                is_pressed = keyboard.is_pressed(key_str)
                # 키가 눌렸고, 이전에 눌린 상태가 아니었을 때만 신호 발생 (한 번만 트리거)
                if is_pressed and not self.hotkey_states[action_name]:
                    logging.info(f"단축키 감지: {action_name} ({key_str})")
                    self.hotkey_pressed.emit(action_name)
                
                self.hotkey_states[action_name] = is_pressed
            except Exception:
                # keyboard 라이브러리가 특정 키 조합을 처리 못할 때 오류 방지
                continue

    def stop(self):
        self.timer.stop()
        logging.info("단축키 관리자 중지.")