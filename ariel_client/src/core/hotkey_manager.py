# ariel_client/src/core/hotkey_manager.py (이 코드로 전체 교체)
import logging
from pynput import keyboard
from PySide6.QtCore import QObject, Signal, Slot

from ..config_manager import ConfigManager

logger = logging.getLogger(__name__)

class HotkeyManager(QObject):
    """
    pynput을 사용하여 전역 단축키를 관리하는 클래스.
    재개편된 ConfigManager와 호환되도록 수정되었습니다.
    """
    hotkey_pressed = Signal(str)

    def __init__(self, config_manager: ConfigManager, parent: QObject | None = None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.listener = None

    def _to_pynput_format(self, hotkey_str: str) -> str:
        """'alt+1' 같은 문자열을 pynput이 인식하는 '<alt>+1' 형식으로 변환합니다."""
        if not hotkey_str: return ""
        parts = hotkey_str.lower().split('+')
        modifiers = {'alt', 'ctrl', 'shift', 'cmd', 'win'}
        
        formatted_parts = [f"<{part.strip()}>" if part.strip() in modifiers else part.strip() for part in parts]
        return '+'.join(formatted_parts)

    def load_hotkeys(self):
        """
        단순화된 ConfigManager에서 단축키 설정을 직접 로드하여
        pynput 리스너에 등록합니다.
        """
        # 기존 리스너가 있다면 중지
        if self.listener:
            self.listener.stop()
            self.listener = None

        hotkey_map = {}
        # [핵심 수정] 설정 파일에서 'hotkey_'로 시작하는 모든 키를 동적으로 찾음
        for key in self.config_manager.config.keys():
            if key.startswith("hotkey_"):
                hotkey_str = self.config_manager.get(key)
                pynput_str = self._to_pynput_format(hotkey_str)
                if pynput_str:
                    # pynput_str를 키로, on_activate_factory를 콜백으로 하는 맵 생성
                    hotkey_map[pynput_str] = self.on_activate_factory(key)

        if not hotkey_map:
            logger.warning("등록할 유효한 단축키가 없습니다.")
            return

        try:
            # GlobalHotKeys에 단축키 맵을 전달하여 리스너 생성 및 시작
            self.listener = keyboard.GlobalHotKeys(hotkey_map)
            self.listener.start()
            logger.info(f"단축키 리스너 시작. 감시 대상: {hotkey_map.keys()}")
        except Exception as e:
            logger.error(f"단축키 리스너 시작 중 오류 발생: {e}", exc_info=True)

    def on_activate_factory(self, action_name: str):
        """
        각 단축키에 올바른 액션 이름을 전달하기 위한 팩토리 함수.
        (예: 'hotkey_toggle_stt' 액션 이름을 전달)
        """
        def on_activate():
            logger.info(f"단축키 [{action_name}] 눌림 감지!")
            self.hotkey_pressed.emit(action_name)
        return on_activate

    @Slot()
    def reload_hotkeys(self):
        """설정이 변경되었을 때 단축키를 다시 로드하는 슬롯."""
        logging.info("설정 변경 감지. 단축키를 다시 로드합니다...")
        self.load_hotkeys()

    def start(self):
        """HotkeyManager를 시작합니다."""
        self.load_hotkeys()

    def stop(self):
        """단축키 리스너를 안전하게 중지합니다."""
        if self.listener:
            self.listener.stop()
            self.listener = None
            logging.info("단축키 리스너가 중지되었습니다.")