# src/main.py

import sys
import os
from PySide6.QtWidgets import QMessageBox, QSystemTrayIcon
from PySide6.QtCore import QLocale, Qt

# --- 이제 모든 import는 run_ariel.py에서 QApplication 생성 이후에 호출되므로 안전합니다. ---
from qfluentwidgets import setTheme, Theme
from config_manager import ConfigManager
from gui.tray_icon import TrayIcon

def run_main_app(app):
    """
    애플리케이션의 주 로직을 실행하는 함수.
    이미 생성된 app 객체를 인자로 받습니다.
    """
    config_manager = ConfigManager()
    
    theme_setting = config_manager.get("theme", "dark")
    setTheme(Theme.LIGHT if theme_setting == "light" else Theme.DARK)
    
    app.setQuitOnLastWindowClosed(False)

    if not QSystemTrayIcon.isSystemTrayAvailable():
        QMessageBox.critical(None, "오류", "시스템 트레이를 사용할 수 없습니다.")
        sys.exit(1)

    # API 키 존재 여부를 확인합니다.
    google_key = config_manager.get("google_credentials_path")
    deepl_key = config_manager.get("deepl_api_key")

    if not google_key or not deepl_key:
        from gui.setup_window import create_setup_window
        QMessageBox.information(None, "Ariel에 오신 것을 환영합니다!",
                                "실시간 번역기 'Ariel'을 사용하기 전에, \n"
                                "필수적인 API 키 설정을 먼저 완료해야 합니다.")
        
        setup_win = create_setup_window(config_manager)
        
        def on_setup_closed(is_saved, context):
            if is_saved:
                QMessageBox.information(None, "설정 완료", "설정이 저장되었습니다. 프로그램을 다시 시작해주세요.")
            else:
                QMessageBox.critical(None, "설정 미완료", "필수 설정이 완료되지 않아 프로그램을 종료합니다.")
            app.quit()
        
        setup_win.closed.connect(on_setup_closed)
        setup_win.show()
    else:
        if not hasattr(app, 'tray_icon_controller'):
            icon_path = os.path.join(os.path.dirname(__file__), '..', 'assets', 'ariel_icon.png')
            app.tray_icon_controller = TrayIcon(config_manager, icon_path, app)
        
        print("Ariel이 시스템 트레이에서 실행 중입니다.")

    sys.exit(app.exec())