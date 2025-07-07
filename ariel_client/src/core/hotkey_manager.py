# F:/projects/Project_Ariel/ariel_client/src/core/hotkey_manager.py

import logging
from pynput import keyboard
from PySide6.QtCore import QObject, Signal

logger = logging.getLogger(__name__)

class HotkeyManager(QObject):
    """
    pynput을 사용하여 전역 단축키를 관리하는 클래스.
    설정된 단축키 문자열을 pynput 형식으로 변환하여 안정적으로 등록합니다.
    """
    hotkey_pressed = Signal(str)

    def __init__(self, config_manager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.hotkeys = {}
        self.listener = None
        self.load_hotkeys()

    def _to_pynput_format(self, hotkey_str: str) -> str:
        """
        [핵심 수정] 'alt+1' 같은 문자열을 '<alt>+1' 형식으로 변환합니다.
        pynput이 특수 키를 인식할 수 있도록 돕습니다.
        """
        parts = hotkey_str.lower().split('+')
        # pynput은 조합키(modifier)를 꺾쇠로 감싸줘야 합니다.
        # 예: 'alt', 'ctrl', 'shift', 'cmd' (macOS의 command 키)
        modifiers = {'alt', 'ctrl', 'shift', 'cmd', 'win'}
        
        formatted_parts = []
        for part in parts:
            part = part.strip()
            if part in modifiers:
                formatted_parts.append(f"<{part}>")
            else:
                # 일반 키(a, b, 1, 2, f1, 등)는 그대로 사용합니다.
                formatted_parts.append(part)
        
        return '+'.join(formatted_parts)

    def load_hotkeys(self):
        """설정 파일에서 단축키를 불러옵니다."""
        profile = self.config_manager.get_active_profile()
        self.hotkeys.clear()
        
        # hotkey_ 접두사가 붙은 모든 키를 동적으로 로드합니다.
        for key, value in profile.items():
            if key.startswith("hotkey_") and isinstance(value, str) and value:
                # 'hotkey_toggle_stt' -> 'toggle_stt'
                action_name = key # tray_icon에서 action_name을 그대로 사용하므로 'hotkey_' 접두사를 유지
                self.hotkeys[value.lower()] = action_name
        
        logging.info(f"단축키 로드 완료: {self.hotkeys}")
        logger.info(f"단축키 로드 완료: {self.hotkeys}")

    def on_activate_factory(self, action: str):
        """클로저 문제를 피하고, 각 단축키에 올바른 액션 이름을 전달하기 위한 팩토리 함수."""
        def on_activate():
            logging.info(f"단축키 [{action}] 눌림 감지!")
            self.hotkey_pressed.emit(action)
        return on_activate

    def start(self):
        """단축키 리스너를 시작합니다."""
        if self.listener is not None:
            logging.warning("기존 단축키 리스너가 실행 중이므로 중지하고 다시 시작합니다.")
            self.stop()

        hotkey_map = {}
        for hotkey_str, action in self.hotkeys.items():
            try:
                # [핵심 수정] pynput 형식으로 변환 후 HotKey 객체 생성
                pynput_str = self._to_pynput_format(hotkey_str)
                # GlobalHotKeys는 {단축키_문자열: 콜백_함수} 형태의 딕셔너리를 인자로 받습니다.
                hotkey_map[pynput_str] = self.on_activate_factory(action)
            except Exception as e:
                logging.warning(f"잘못된 단축키 형식 '{hotkey_str}'을(를) 무시합니다. 오류: {e}")

        if not hotkey_map:
            logging.warning("등록할 유효한 단축키가 없습니다.")
            return

        try:
            # 리스너를 별도 스레드에서 시작하지 않도록 수정 (pynput 내부 처리)
            self.listener = keyboard.GlobalHotKeys(hotkey_map)
            self.listener.start()
            logging.info(f"단축키 리스너 시작. 감시 대상: {list(self.hotkeys.keys())}")
        except Exception as e:
            # 보통 다른 프로그램이 단축키를 선점했을 때 발생 (관리자 권한으로 실행 시도)
            logging.error(f"단축키 리스너 시작 중 예측하지 못한 오류 발생: {e}. 다른 프로그램이 단축키를 사용 중일 수 있습니다.", exc_info=True)

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