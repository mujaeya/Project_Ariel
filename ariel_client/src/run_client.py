# ariel_client/src/run_client.py (최종 완성본)
import sys
import os
import logging

def setup_logging():
    # 이 함수는 변경할 필요 없습니다.
    # ... (기존 setup_logging 코드 그대로)
    from .utils import resource_path
    log_dir = resource_path(os.path.join('..', 'logs'))
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, 'ariel_app.log')
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    logging.info("로깅 시스템 초기화 완료.")

def main():
    """애플리케이션 메인 진입점"""
    setup_logging()

    # --- [최후의 해결책] ---
    # PySide6 관련 모듈(TrayIcon)을 임포트하기 전에,
    # 문제가 되는 audio_processor 모듈을 강제로 먼저 임포트하여
    # pycaw가 시스템 환경을 선점하도록 합니다.
    try:
        from .core import audio_processor
        logging.getLogger(__name__).info("초기화 충돌 방지를 위해 audio_processor를 선제적으로 로드했습니다.")
    except Exception as e:
        logging.getLogger(__name__).critical(f"audio_processor 선제적 로드 실패: {e}", exc_info=True)
        # 이 단계에서 실패하면 더 이상 진행할 수 없으므로 종료합니다.
        return
    # --- [수정 끝] ---

    # 이제 나머지 모듈들을 임포트합니다.
    from PySide6.QtWidgets import QApplication, QMessageBox, QSystemTrayIcon
    from .config_manager import ConfigManager
    from .gui.tray_icon import TrayIcon
    from .utils import resource_path
    
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    if not QSystemTrayIcon.isSystemTrayAvailable():
        logging.critical("시스템 트레이를 사용할 수 없어 프로그램을 시작할 수 없습니다.")
        return

    try:
        config_manager = ConfigManager()
        icon_path = resource_path(os.path.join('assets', 'ariel_icon.ico'))
        # audio_processor는 이미 임포트되었으므로 TrayIcon은 캐시된 모듈을 사용합니다.
        tray_icon = TrayIcon(config_manager, icon_path, app)
    except Exception as e:
        logging.critical(f"애플리케이션 초기화 실패: {e}", exc_info=True)
        return
        
    logging.info("Ariel 클라이언트 이벤트 루프 시작.")
    sys.exit(app.exec())

if __name__ == '__main__':
    main()