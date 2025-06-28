# run_ariel.py

import sys
import os
from multiprocessing import freeze_support

# 이 파일은 애플리케이션의 유일한 진입점입니다.
# 역할: QApplication 객체를 가장 먼저 생성하고, main 로직을 호출합니다.

if __name__ == '__main__':
    # Windows에서 실행 파일(.exe)로 만들 때 필요합니다.
    freeze_support()

    # 'src' 폴더를 Python 경로에 추가하여 하위 모듈을 찾을 수 있게 합니다.
    application_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src')
    sys.path.insert(0, application_path)

    # 1. 다른 어떤 코드보다도 먼저 QApplication 객체를 생성합니다.
    from PySide6.QtWidgets import QApplication
    app = QApplication(sys.argv)

    # 2. QApplication이 생성된 후에야 메인 애플리케이션 로직을 import하고 실행합니다.
    #    이렇게 하면 main.py 내부의 모든 import는 app 생성 이후에 처리됩니다.
    import main
    main.run_main_app(app)