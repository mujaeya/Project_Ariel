# src/hotkey_manager.py

from PySide6.QtCore import QObject, Signal, Slot
from pynput import keyboard

class HotkeyManager(QObject):
    start_pressed = Signal()
    stop_pressed = Signal()
    setup_pressed = Signal()

    def __init__(self, hotkeys_config: dict, parent=None):
        super().__init__(parent)
        self.hotkeys_config = hotkeys_config
        self.listener = None

        def parse_hotkey(hotkey_str: str) -> str:
            if not hotkey_str or not isinstance(hotkey_str, str): return None
            parts = hotkey_str.lower().split('+')
            parsed_parts = [f"<{p.strip()}>" if p.strip() in ['ctrl', 'alt', 'shift', 'cmd', 'win'] else p.strip() for p in parts]
            return '+'.join(parsed_parts)

        parsed_map = {
            parse_hotkey(self.hotkeys_config.get("hotkey_start_translate")): self.on_start,
            parse_hotkey(self.hotkeys_config.get("hotkey_stop_translate")): self.on_stop,
            parse_hotkey(self.hotkeys_config.get("hotkey_toggle_setup_window")): self.on_setup,
        }
        self.registered_hotkeys = {k: v for k, v in parsed_map.items() if k}
        print("[HotkeyManager] pynput 기반으로 초기화되었습니다.")

    def on_start(self):
        print("[HotkeyManager] '번역 시작' 단축키 감지")
        self.start_pressed.emit()

    def on_stop(self):
        print("[HotkeyManager] '번역 중지' 단축키 감지")
        self.stop_pressed.emit()

    def on_setup(self):
        print("[HotkeyManager] '설정' 단축키 감지")
        self.setup_pressed.emit()

    @Slot()
    def start(self):
        if self.listener or not self.registered_hotkeys: return
        try:
            self.listener = keyboard.GlobalHotKeys(self.registered_hotkeys)
            self.listener.start()
            print(f"[HotkeyManager] pynput 리스너 시작. 감지 대상: {list(self.registered_hotkeys.keys())}")
        except Exception as e:
            print(f"[HotkeyManager] pynput 리스너 시작 실패: {e}")

    @Slot()
    def stop(self):
        if self.listener:
            print("[HotkeyManager] pynput 리스너를 중지합니다.")
            self.listener.stop()
            self.listener.join()
            self.listener = None