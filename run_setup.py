# run_setup.py (완성 코드)

import sys
import os

# 'src' 폴더를 Python 경로에 추가
application_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src')
sys.path.insert(0, application_path)

# --- GUI 라이브러리 및 필요 모듈 import ---
from PySide6.QtWidgets import QApplication, QMainWindow
from config_manager import ConfigManager
from gui.setup_window import SetupWindow

if __name__ == '__main__':
    # 1. [핵심] QApplication 객체 생성
    app = QApplication(sys.argv)

    # 2. [핵심] qfluentwidgets를 위한 보이지 않는 '더미' 메인 윈도우 생성
    dummy_main_window = QMainWindow()

    # 3. 이제 SetupWindow(FluentWindow)를 안전하게 생성할 수 있습니다.
    config_manager = ConfigManager()
    setup_win = SetupWindow(config_manager)
    setup_win.show()

    # 4. 애플리케이션 이벤트 루프 시작
    sys.exit(app.exec())