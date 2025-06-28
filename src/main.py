import sys
import os
from PySide6.QtWidgets import QApplication, QMessageBox, QSystemTrayIcon
from PySide6.QtCore import QLocale, Qt
from qfluentwidgets import setTheme, Theme

if getattr(sys, 'frozen', False):
    application_path = os.path.dirname(sys.executable)
else:
    application_path = os.path.dirname(os.path.abspath(__file__))
sys.path.append(application_path)

from config_manager import ConfigManager

def main():
    app = QApplication(sys.argv)

    from gui.tray_icon import TrayIcon
    from gui.setup_window import SetupWindow
    
    config_manager = ConfigManager()
    theme_setting = config_manager.get("theme", "dark")
    if theme_setting == "light":
        setTheme(Theme.LIGHT)
    else:
        setTheme(Theme.DARK)

    if QLocale.system().textDirection() == 1:
        app.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        
    app.setQuitOnLastWindowClosed(False)

    if not QSystemTrayIcon.isSystemTrayAvailable():
        QMessageBox.critical(None, "오류", "시스템 트레이를 사용할 수 없습니다. 프로그램을 시작할 수 없습니다.")
        return

    google_key = config_manager.get("google_credentials_path")
    deepl_key = config_manager.get("deepl_api_key")

    if not google_key or not deepl_key:
        QMessageBox.information(None, "Ariel에 오신 것을 환영합니다!",
                                "실시간 번역기 'Ariel'을 사용하기 전에, \n"
                                "필수적인 API 키 설정을 먼저 완료해야 합니다.")
        
        setup_win = SetupWindow(config_manager)
        
        def on_setup_closed(is_saved, context):
            if is_saved and config_manager.get("google_credentials_path") and config_manager.get("deepl_api_key"):
                start_main_application(app, config_manager, TrayIcon)
            else:
                QMessageBox.critical(None, "설정 미완료", "필수 설정이 완료되지 않아 프로그램을 종료합니다.")
                app.quit()

        setup_win.closed.connect(on_setup_closed)
        setup_win.show()
    else:
        start_main_application(app, config_manager, TrayIcon)

    sys.exit(app.exec())


def start_main_application(app, config_manager, TrayIcon):
    """트레이 아이콘을 생성하고 메인 앱을 시작하는 함수."""
    if getattr(sys, 'frozen', False):
        application_path = os.path.dirname(sys.executable)
    else:
        application_path = os.path.dirname(os.path.abspath(__file__))

    icon_path = os.path.join(application_path, '..', 'assets', 'ariel_icon.png')
    
    if not hasattr(app, 'tray_icon_controller'):
        app.tray_icon_controller = TrayIcon(config_manager, icon_path, app)
    
    print("Ariel이 시스템 트레이에서 실행 중입니다.")

if __name__ == '__main__':
    main()