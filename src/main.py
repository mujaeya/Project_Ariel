# src/main.py (NameError 해결 및 구조 유지 최종본)
import sys
import os
import logging

# 이전 단계에서 수정한 대로 utils에서 resource_path를 가져옵니다.
from utils import resource_path

def setup_logging():
    """애플리케이션의 로깅 시스템을 설정합니다."""
    if getattr(sys, 'frozen', False):
        log_dir = os.path.join(os.path.dirname(sys.executable), 'logs')
    else:
        log_dir = resource_path('logs')
        
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, 'ariel_app.log')

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    logging.info("로깅 시스템 초기화 완료.")

# --- 로깅 및 경로 설정 ---
setup_logging()
# 개발 환경 경로 설정 (프로젝트 루트 추가)
if not getattr(sys, 'frozen', False):
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# --- 모듈 Import ---
# <<<<<<<<<<<<<<<< 핵심 수정: 누락되었던 QSystemTrayIcon 추가 >>>>>>>>>>>>>>>>>>
from PySide6.QtWidgets import QApplication, QMessageBox, QSystemTrayIcon
from PySide6.QtCore import QLocale, Qt
from config_manager import ConfigManager
from gui.tray_icon import TrayIcon

def main():
    """애플리케이션 메인 진입점"""
    app = QApplication(sys.argv)
    if QLocale.system().textDirection() == Qt.LayoutDirection.RightToLeft:
        app.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
    app.setQuitOnLastWindowClosed(False)

    # 이제 QSystemTrayIcon이 정상적으로 import되었으므로 오류가 발생하지 않습니다.
    if not QSystemTrayIcon.isSystemTrayAvailable():
        logging.critical("시스템 트레이를 사용할 수 없어 프로그램을 시작할 수 없습니다.")
        QMessageBox.critical(None, "오류", "시스템 트레이를 사용할 수 없습니다.")
        return

    config_manager = ConfigManager()
    icon_path = resource_path(os.path.join('assets', 'ariel_icon.ico'))
    
    if not hasattr(app, 'tray_icon_controller'):
        app.tray_icon_controller = TrayIcon(config_manager, icon_path, app)
    
    if not config_manager.get("google_credentials_path") or not config_manager.get("deepl_api_key"):
        QMessageBox.information(None, "Ariel에 오신 것을 환영합니다!",
                                "실시간 번역기 'Ariel'을 사용하기 전에, \n"
                                "필수적인 API 키 설정을 먼저 완료해야 합니다.")
        app.tray_controller.open_setup_window()
        
    logging.info("Ariel이 시스템 트레이에서 실행 중입니다.")
    sys.exit(app.exec())

if __name__ == '__main__':
    main()