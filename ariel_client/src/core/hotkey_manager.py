import logging
from pynput import keyboard
from PySide6.QtCore import QObject, Signal

class HotkeyManager(QObject):
    """
    pynput.keyboard.Listener를 사용하여 전역 단축키를 관리하는 클래스.
    설정된 단축키 문자열을 pynput 형식으로 변환하여 안정적으로 등록합니다.
    """
    hotkey_pressed = Signal(str)

    def __init__(self, config_manager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.hotkeys = {}
        self.listener = None
        self.load_hotkeys()
        self.start()

    def _to_pynput_format(self, hotkey_str: str) -> str:
        """
        [핵심 수정] 'alt+1' 같은 문자열을 '<alt>+1' 형식으로 변환합니다.
        pynput이 특수 키를 인식할 수 있도록 돕습니다.
        """
        # pynput에서 특수 키로 취급하는 키들의 목록
        special_keys = {
            'ctrl', 'alt', 'shift', 'cmd', 'win', 'command',
            'esc', 'space', 'enter', 'tab', 'backspace', 'delete', 'insert',
            'home', 'end', 'page_up', 'page_down', 'up', 'down', 'left', 'right',
            'caps_lock', 'scroll_lock', 'num_lock', 'print_screen'
        }
        # F1 ~ F24 키 추가
        for i in range(1, 25):
            special_keys.add(f'f{i}')

        parts = hotkey_str.lower().split('+')
        formatted_parts = []
        for part in parts:
            part = part.strip()
            if part in special_keys:
                # 특수 키는 꺾쇠로 감쌉니다.
                formatted_parts.append(f"<{part}>")
            else:
                # 일반 키는 그대로 둡니다.
                formatted_parts.append(part)
        
        return '+'.join(formatted_parts)

    def load_hotkeys(self):
        """설정 파일에서 단축키를 불러옵니다."""
        profile = self.config_manager.get_active_profile()
        self.hotkeys.clear()
        for key, value in profile.items():
            if key.startswith("hotkey_") and isinstance(value, str) and value:
                action_name = key.replace("hotkey_", "")
                self.hotkeys[value.lower()] = action_name
        logging.info(f"단축키 로드 완료: {self.hotkeys}")

    def on_activate_factory(self, action):
        """콜백 함수에 전달할 action 값을 고정시키기 위한 팩토리 함수."""
        def on_activate():
            self.hotkey_pressed.emit(action)
        return on_activate

    def start(self):
        """단축키 리스너를 시작합니다."""
        if self.listener is not None:
            self.stop()

        hotkey_map = {}
        for hotkey_str, action in self.hotkeys.items():
            try:
                # [핵심 수정] pynput 형식으로 변환 후 파싱
                pynput_formatted_str = self._to_pynput_format(hotkey_str)
                key_combination = frozenset(keyboard.HotKey.parse(pynput_formatted_str))
                hotkey_map[key_combination] = self.on_activate_factory(action)
            except Exception as e:
                logging.warning(f"잘못된 단축키 형식 '{hotkey_str}'을(를) 무시합니다. 오류: {e}")

        if not hotkey_map:
            logging.warning("등록할 유효한 단축키가 없습니다.")
            return

        try:
            self.listener = keyboard.Listener(hotkeys=hotkey_map)
            self.listener.start()
            logging.info(f"단축키 리스너 시작. 감시 대상: {list(self.hotkeys.keys())}")
        except Exception as e:
            logging.error(f"단축키 리스너 시작 중 예측하지 못한 오류 발생: {e}")

    def stop(self):
        """단축키 리스너를 안전하게 중지합니다."""
        if self.listener:
            self.listener.stop()
            self.listener = None
            logging.info("단축키 리스너 중지됨.")

    def reload_hotkeys(self):
        """설정 파일이 변경되었을 때 단축키를 다시 불러와 적용합니다."""
        logging.info("단축키 설정을 다시 불러옵니다...")
        self.stop()
        self.load_hotkeys()
        self.start()