import sys
import os
import logging  # 로깅 모듈 import
from PySide6.QtWidgets import QApplication, QMessageBox, QSystemTrayIcon
from PySide6.QtCore import QLocale, Qt

# --- 로깅 설정 함수 ---
def setup_logging(base_path):
    """애플리케이션의 로깅 시스템을 설정합니다."""
    log_dir = os.path.join(base_path, 'logs')
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, 'ariel_app.log')

    # 기본 로거 설정
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler() # 콘솔에도 로그를 출력합니다.
        ]
    )
    logging.info("로깅 시스템 초기화 완료.")

# --- 애플리케이션 경로 설정 ---
# 모듈 경로 문제 해결
if getattr(sys, 'frozen', False):
    # PyInstaller 등으로 빌드된 실행 파일일 경우
    application_path = os.path.dirname(sys.executable)
else:
    # 일반 Python 스크립트로 실행할 경우
    application_path = os.path.dirname(os.path.abspath(__file__))
sys.path.append(application_path)

# --- 로깅 시스템 초기화 ---
# 경로 설정이 끝난 후 바로 로깅을 설정합니다.
setup_logging(application_path)


# --- 나머지 모듈 import ---
from config_manager import ConfigManager
from gui.tray_icon import TrayIcon
from gui.setup_window import SetupWindow

def main():
    """애플리케이션 메인 진입점"""
    app = QApplication(sys.argv)
    
    # 시스템 언어의 텍스트 방향을 확인 (AttributeError 해결)
    if QLocale.system().textDirection() == 1: # 1은 Qt.LayoutDirection.RightToLeft
        app.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        
    app.setQuitOnLastWindowClosed(False)

    if not QSystemTrayIcon.isSystemTrayAvailable():
        # logging.critical은 프로그램 실행이 불가능한 심각한 오류에 사용
        logging.critical("시스템 트레이를 사용할 수 없어 프로그램을 시작할 수 없습니다.")
        QMessageBox.critical(None, "오류", "시스템 트레이를 사용할 수 없습니다. 프로그램을 시작할 수 없습니다.")
        return

    config_manager = ConfigManager()

    google_key = config_manager.get("google_credentials_path")
    deepl_key = config_manager.get("deepl_api_key")

    if not google_key or not deepl_key:
        logging.warning("필수 API 키가 설정되지 않았습니다. 초기 설정 창을 표시합니다.")
        QMessageBox.information(None, "Ariel에 오신 것을 환영합니다!",
                                "실시간 번역기 'Ariel'을 사용하기 전에, \n"
                                "필수적인 API 키 설정을 먼저 완료해야 합니다.")
        
        setup_win = SetupWindow(config_manager)
        
        def on_setup_closed(is_saved, context):
            if is_saved and config_manager.get("google_credentials_path") and config_manager.get("deepl_api_key"):
                logging.info("초기 설정이 완료되었습니다. 메인 애플리케이션을 시작합니다.")
                start_main_application(app, config_manager)
            else:
                logging.critical("필수 설정이 완료되지 않아 프로그램을 종료합니다.")
                QMessageBox.critical(None, "설정 미완료", "필수 설정이 완료되지 않아 프로그램을 종료합니다.")
                app.quit()

        setup_win.closed.connect(on_setup_closed)
        setup_win.show()
    else:
        logging.info("기존 설정 파일을 확인했습니다. 메인 애플리케이션을 시작합니다.")
        start_main_application(app, config_manager)

    sys.exit(app.exec())


def start_main_application(app, config_manager):
    """트레이 아이콘을 생성하고 메인 앱을 시작하는 함수."""
    # application_path는 이미 전역적으로 계산되었지만, 명확성을 위해 다시 정의
    if getattr(sys, 'frozen', False):
        current_path = os.path.dirname(sys.executable)
    else:
        current_path = os.path.dirname(os.path.abspath(__file__))

    icon_path = os.path.join(current_path, '..', 'assets', 'ariel_icon.png')
    
    if not hasattr(app, 'tray_icon_controller'):
        # TrayIcon 생성은 전체 애플리케이션에서 한 번만 수행
        app.tray_icon_controller = TrayIcon(config_manager, icon_path, app)
    
    # print()를 logging.info()로 변경
    logging.info("Ariel이 시스템 트레이에서 실행 중입니다.")


if __name__ == '__main__':
    main()