# ariel_client/src/run_client.py (이 코드로 전체 교체)
import sys
import os
import logging

# [수정] 상대 경로로 import
from .utils import resource_path

def setup_logging():
    """애플리케이션의 로깅 시스템을 설정합니다."""
    # 로그 폴더 경로 설정 (상대 경로 유틸리티 사용)
    log_dir = resource_path(os.path.join('..', 'logs'))
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, 'ariel_app.log')

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler(sys.stdout) # 로그가 콘솔에도 출력되도록 수정
        ]
    )
    logging.info("로깅 시스템 초기화 완료.")

# --- 모듈 Import (필요한 것만) ---
from PySide6.QtWidgets import QApplication, QMessageBox, QSystemTrayIcon
from PySide6.QtCore import QTimer

# [수정] 상대 경로로 import
from .config_manager import ConfigManager
from .gui.tray_icon import TrayIcon

def main():
    """애플리케이션 메인 진입점"""
    # 로깅 설정은 main 함수 안에서 호출하는 것이 더 안정적입니다.
    setup_logging()

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    if not QSystemTrayIcon.isSystemTrayAvailable():
        logging.critical("시스템 트레이를 사용할 수 없어 프로그램을 시작할 수 없습니다.")
        QMessageBox.critical(None, "오류", "시스템 트레이를 사용할 수 없습니다.")
        return

    # 설정 및 트레이 아이콘 생성
    try:
        config_manager = ConfigManager()
        # assets 폴더는 src 폴더와 같은 레벨에 있어야 함
        icon_path = resource_path(os.path.join('assets', 'ariel_icon.ico'))
        tray_icon = TrayIcon(config_manager, icon_path, app)
    except Exception as e:
        logging.critical(f"애플리케이션 초기화 실패: {e}", exc_info=True)
        QMessageBox.critical(None, "초기화 오류", f"프로그램 시작 중 오류가 발생했습니다:\n{e}")
        return
        
    logging.info("Ariel 클라이언트 이벤트 루프 시작.")
    sys.exit(app.exec())

if __name__ == '__main__':
    main()