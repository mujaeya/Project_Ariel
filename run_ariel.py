# run_ariel.py (완성 코드)

import sys
import os
from multiprocessing import freeze_support

if __name__ == '__main__':
    # 멀티프로세싱 지원 (PyInstaller 등으로 패키징 시 필요)
    freeze_support()

    # 'src' 폴더를 Python 경로에 추가하여 모듈을 찾을 수 있도록 함
    application_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src')
    sys.path.insert(0, application_path)

    # --- GUI 라이브러리 import ---
    from PySide6.QtWidgets import QApplication, QMainWindow

    # 1. [핵심] 다른 어떤 GUI 코드보다도 먼저 QApplication 객체를 생성합니다.
    app = QApplication(sys.argv)

    # 2. [핵심] qfluentwidgets 라이브러리가 안정적으로 동작하도록,
    #    눈에 보이지 않는 '더미' 메인 윈도우를 먼저 생성합니다.
    #    이 윈도우는 메모리에만 존재하며, 실제 화면에 표시되지는 않습니다.
    #    이것이 SetupWindow가 오류 없이 생성될 수 있게 하는 열쇠입니다.
    dummy_main_window = QMainWindow()

    # 3. 모든 환경이 준비되었으므로, 실제 애플리케이션 로직을 실행합니다.
    #    app 객체를 전달하여 main.py에서 이벤트 루프를 제어하도록 합니다.
    import main
    main.run_main_app(app)