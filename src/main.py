# src/main.py (이 코드로 전체를 교체해주세요)
import sys
import os
import logging
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
if not getattr(sys, 'frozen', False):
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# --- 모듈 Import ---
from PySide6.QtWidgets import QApplication, QMessageBox, QSystemTrayIcon
from PySide6.QtCore import QLocale, Qt, QTimer
from config_manager import ConfigManager
from gui.tray_icon import TrayIcon

def main():
    """애플리케이션 메인 진입점"""
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    if not QSystemTrayIcon.isSystemTrayAvailable():
        logging.critical("시스템 트레이를 사용할 수 없어 프로그램을 시작할 수 없습니다.")
        QMessageBox.critical(None, "오류", "시스템 트레이를 사용할 수 없습니다.")
        return

    config_manager = ConfigManager()
    icon_path = resource_path(os.path.join('assets', 'ariel_icon.ico'))
    
    # TrayIcon 인스턴스 생성
    tray_icon = TrayIcon(config_manager, icon_path, app)
    
    # [핵심 수정] 이벤트 루프가 시작된 직후, 초기 확인 함수를 딱 한 번 실행하도록 예약합니다.
    # 이렇게 하면 UI 충돌 없이 안전하게 창을 띄울 수 있습니다.
    QTimer.singleShot(0, tray_icon.run_initial_check)
        
    logging.info("Ariel 애플리케이션 이벤트 루프 시작.")
    sys.exit(app.exec())

if __name__ == '__main__':
    main()