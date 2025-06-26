# src/main.py
import sys
import os
from PySide6.QtWidgets import QApplication, QMessageBox

# --- 모듈 경로 문제 해결 ---
if getattr(sys, 'frozen', False):
    application_path = os.path.dirname(sys.executable)
else:
    application_path = os.path.dirname(os.path.abspath(__file__))
sys.path.append(application_path)
# ---------------------------

from config_manager import ConfigManager
from gui.tray_icon import TrayIcon
from gui.setup_window import SetupWindow

def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    config_manager = ConfigManager()

    google_key = config_manager.get("google_credentials_path")
    deepl_key = config_manager.get("deepl_api_key")

    if not google_key or not deepl_key:
        QMessageBox.information(None, "Ariel에 오신 것을 환영합니다!",
                                "실시간 번역기 'Ariel'을 사용하기 전에, \n"
                                "필수적인 API 키와 오디오 장치 설정을 먼저 완료해야 합니다.")
        
        setup_win = SetupWindow(config_manager)
        
        def on_setup_closed(is_saved):
            if is_saved and config_manager.get("google_credentials_path") and config_manager.get("deepl_api_key"):
                start_main_application(app, config_manager)
            else:
                QMessageBox.critical(None, "설정 미완료", "필수 설정이 완료되지 않아 프로그램을 종료합니다.")
                app.quit()

        setup_win.closed.connect(on_setup_closed)
        setup_win.show()
    else:
        start_main_application(app, config_manager)

    sys.exit(app.exec())


def start_main_application(app, config_manager):
    """트레이 아이콘을 생성하고 메인 앱을 시작하는 함수."""
    if getattr(sys, 'frozen', False):
        application_path = os.path.dirname(sys.executable)
    else:
        application_path = os.path.dirname(os.path.abspath(__file__))

    icon_path = os.path.join(application_path, '..', 'assets', 'ariel_icon.png')
    
    if not hasattr(app, 'tray_icon'):
        app.tray_icon = TrayIcon(config_manager, icon_path)
    
    if not app.tray_icon.isSystemTrayAvailable():
        QMessageBox.critical(None, "오류", "시스템 트레이를 사용할 수 없습니다.")
        app.quit()
        return

    app.tray_icon.show()
    print("Ariel이 시스템 트레이에서 실행 중입니다.")

if __name__ == '__main__':
    main()