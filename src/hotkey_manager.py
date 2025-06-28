import keyboard
import time

def hotkey_listener(queue, hotkeys_config):
    """
    독립된 프로세스에서 실행될 함수.
    설정된 단축키를 감지하여 큐에 이벤트를 넣습니다.
    """
    print("[Hotkey Listener Process] 독립된 프로세스에서 단축키 리스닝을 시작합니다.")

    key_to_event = {
        hotkeys_config.get("hotkey_start_translate"): "start",
        hotkeys_config.get("hotkey_stop_translate"): "stop",
        hotkeys_config.get("hotkey_toggle_setup_window"): "setup",
        hotkeys_config.get("hotkey_toggle_pause"): "toggle_pause" 
    }

    for key, event_name in key_to_event.items():
        if key and event_name:
            try:
                keyboard.add_hotkey(key, lambda event_name=event_name: queue.put(event_name), suppress=True)
                print(f"[Hotkey Listener Process] 단축키 등록: {key} -> {event_name}")
            except Exception as e:
                print(f"[Hotkey Listener Process] 단축키 등록 실패: {key}, 오류: {e}")

    while True:
        time.sleep(1)