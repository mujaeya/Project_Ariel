import sys
import logging
from logging.config import dictConfig
import ctypes

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTranslator, QLocale, QLibraryInfo

# 상대 경로 임포트
from .utils import resource_path, setup_logging
from .config_manager import ConfigManager
from .gui.tray_icon import TrayIcon

# [수정] 오디오 프로세서 선제적 로드 (기존 코드 유지)
try:
    from .core.audio_processor import AudioProcessor
    logging.info("초기화 충돌 방지를 위해 audio_processor를 선제적으로 로드했습니다.")
except ImportError as e:
    logging.error(f"Audio processor 로드 실패: {e}")
    # 필요한 경우 사용자에게 알림
# ... (중간 생략) ...

def main():
    # Windows에서 DPI 인식 및 작업 표시줄 아이콘 해상도 문제 해결
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
        myappid = 'mycompany.myproduct.subproduct.version'
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except Exception as e:
        logging.warning(f"DPI 또는 AppUserModelID 설정 실패: {e}")

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    setup_logging()
    
    config_manager = ConfigManager()

    # --- [신규] 다국어(i18n) 지원 로직 ---
    translator = QTranslator(app)
    
    # 설정된 언어 또는 시스템 언어 가져오기
    lang_code = config_manager.get('app_language', QLocale.system().name().split('_')[0]) # 'ko_KR' -> 'ko'
    
    # Qt 기본 번역 로드 (예: 'OK', 'Cancel' 버튼 등)
    qt_translator = QTranslator(app)
    qt_translation_path = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
    if qt_translator.load(QLocale(lang_code), "qtbase", "_", qt_translation_path):
        app.installTranslator(qt_translator)
    
    # 우리 앱의 번역 로드
    translation_file = resource_path(f'translations/ariel_{lang_code}.qm')
    if translator.load(translation_file):
        app.installTranslator(translator)
        logging.info(f"'{lang_code}' 언어 번역 파일을 로드했습니다.")
    else:
        logging.warning(f"'{lang_code}' 언어 번역 파일({translation_file})을 찾을 수 없습니다. 기본 언어(영어)로 실행됩니다.")
    # --- 다국어 로직 끝 ---

    try:
        icon_path = resource_path("assets/icons/app_icon.ico")
        tray_icon = TrayIcon(config_manager, icon_path, app)
    except Exception as e:
        logging.critical(f"애플리케이션 초기화 중 심각한 오류 발생: {e}", exc_info=True)
        sys.exit(1)
    
    logging.info("Ariel 클라이언트 이벤트 루프 시작.")
    sys.exit(app.exec())

if __name__ == "__main__":
    main()