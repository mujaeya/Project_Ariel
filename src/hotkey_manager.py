# src/hotkey_manager.py (신규 파일)
import keyboard
from PySide6.QtCore import QObject, Signal, Slot

class HotkeyManager(QObject):
    """
    keyboard 라이브러리의 이벤트를 Qt 시그널로 변환하여 GUI 스레드와 안전하게
    통신하는 역할을 전담하는 클래스.
    """
    start_hotkey_pressed = Signal()
    stop_hotkey_pressed = Signal()
    setup_hotkey_pressed = Signal()

    def __init__(self, config_manager):
        super().__init__()
        self.config_manager = config_manager
        self.registered_hotkeys = []

    @Slot()
    def start_listening(self):
        """
        초기 단축키를 등록하고 리스닝을 시작하는 메인 함수.
        반드시 QThread 위에서 실행되어야 합니다.
        """
        print("[HotkeyManager] 단축키 리스닝을 시작합니다.")
        self.reregister_hotkeys()

    @Slot()
    def reregister_hotkeys(self):
        """기존 단축키를 모두 해제하고 설정을 다시 읽어 새로 등록합니다."""
        print("[HotkeyManager] 단축키를 다시 등록합니다...")
        
        for hotkey_str, hook in self.registered_hotkeys:
            try:
                keyboard.remove_hotkey(hook)
            except (KeyError, ValueError):
                pass
        self.registered_hotkeys.clear()

        start_key = self.config_manager.get("hotkey_start_translate")
        stop_key = self.config_manager.get("hotkey_stop_translate")
        setup_key = self.config_manager.get("hotkey_toggle_setup_window")
        
        try:
            if start_key:
                hook = keyboard.add_hotkey(start_key, self.start_hotkey_pressed.emit, suppress=True)
                self.registered_hotkeys.append((start_key, hook))
            if stop_key:
                hook = keyboard.add_hotkey(stop_key, self.stop_hotkey_pressed.emit, suppress=True)
                self.registered_hotkeys.append((stop_key, hook))
            if setup_key:
                hook = keyboard.add_hotkey(setup_key, self.setup_hotkey_pressed.emit, suppress=True)
                self.registered_hotkeys.append((setup_key, hook))

            print(f"[HotkeyManager] 단축키 등록 완료: {[key for key, _ in self.registered_hotkeys]}")
        except Exception as e:
            # 이 오류는 GUI 스레드로 전달할 방법이 마땅치 않으므로 로그만 남깁니다.
            print(f"[HotkeyManager] 단축키 등록 실패: {e}")

    def stop_listening(self):
        print("[HotkeyManager] 모든 단축키를 해제합니다.")
        for hotkey_str, hook in self.registered_hotkeys:
            try:
                keyboard.remove_hotkey(hook)
            except (KeyError, ValueError):
                pass
        self.registered_hotkeys.clear()