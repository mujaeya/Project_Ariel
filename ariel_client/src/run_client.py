import sys
import logging
import ctypes
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtGui import QIcon
from PySide6.QtCore import QTranslator, QLocale, QLibraryInfo

# 상대 경로 임포트
from .utils import resource_path, setup_logging
from .config_manager import ConfigManager
from .gui.tray_icon import TrayIcon

# [핵심 기능 유지] 오디오 프로세서를 선제적으로 로드하여 초기화 충돌을 방지합니다.
try:
    from .core.audio_processor import AudioProcessor
    logging.info("초기화 충돌 방지를 위해 audio_processor를 선제적으로 로드했습니다.")
except ImportError as e:
    # 이 오류는 심각한 문제일 수 있으므로 로깅 레벨을 error로 유지합니다.
    logging.error(f"Audio processor 로드 실패: {e}")
    # 필요한 경우 사용자에게 알림을 표시할 수 있습니다.
except Exception as e:
    logging.error(f"audio_processor 로드 중 예기치 않은 오류 발생: {e}")


def main():
    try:
        # Windows 환경에서 DPI 인식 및 작업 표시줄 아이콘 해상도 문제 해결
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
        myappid = 'mycompany.myproduct.subproduct.version'
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except (AttributeError, TypeError):
        # AttributeError/TypeError는 비-Windows 환경에서 발생하므로 경고만 로깅합니다.
        logging.warning("DPI 또는 AppUserModelID 설정은 Windows 환경에서만 적용됩니다.")
    except Exception as e:
        # 그 외의 예외는 설정 실패로 간주하고 경고합니다.
        logging.warning(f"DPI 또는 AppUserModelID 설정 실패: {e}")

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    # 로깅 설정 초기화
    setup_logging()
    
    # 설정 관리자 인스턴스 생성
    config_manager = ConfigManager()

    # --- 다국어(i18n) 지원 로직 ---
    translator = QTranslator(app)
    
    # 설정 파일 또는 시스템에서 언어 코드 가져오기 ('ko_KR' -> 'ko')
    lang_code = config_manager.get('app_language', QLocale.system().name().split('_')[0])
    
    # Qt 기본 번역 로드 (예: 'OK', 'Cancel' 버튼)
    qt_translator = QTranslator(app)
    qt_translation_path = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
    if qt_translator.load(QLocale(lang_code), "qtbase", "_", qt_translation_path):
        app.installTranslator(qt_translator)
    
    # 애플리케이션 자체 번역 파일 로드
    translation_file = resource_path(f'translations/ariel_{lang_code}.qm')
    if translator.load(translation_file):
        app.installTranslator(translator)
        logging.info(f"'{lang_code}' 언어 번역 파일을 로드했습니다.")
    else:
        logging.warning(f"'{lang_code}' 언어 번역 파일({translation_file})을 찾을 수 없습니다. 기본 언어(영어)로 실행됩니다.")
    # --- 다국어 로직 끝 ---

    try:
        # [개선] 아이콘을 QIcon 객체로 먼저 로드하여 유효성을 검사합니다.
        app_icon = QIcon(resource_path("assets/icons/app_icon.ico"))
        if app_icon.isNull():
            # 아이콘 로드 실패 시 사용자에게 명확한 오류 메시지를 표시하고 종료합니다.
            error_msg = "애플리케이션 아이콘(app_icon.ico) 로드에 실패했습니다. assets/icons 폴더에 파일이 있는지 확인해주세요."
            logging.critical(error_msg)
            QMessageBox.critical(None, "파일 누락", error_msg)
            sys.exit(1)

        # [개선] 모든 창(QMessageBox 등)에 기본 아이콘을 설정합니다.
        app.setWindowIcon(app_icon)

        # TrayIcon을 초기화할 때 아이콘 경로 대신 QIcon 객체를 직접 전달합니다.
        tray_icon = TrayIcon(config_manager, app_icon, app)

    except Exception as e:
        # 초기화 중 다른 예외 발생 시에도 사용자에게 알리고 종료합니다.
        logging.critical(f"애플리케이션 초기화 중 심각한 오류 발생: {e}", exc_info=True)
        QMessageBox.critical(None, "실행 오류", f"프로그램 실행 중 심각한 오류가 발생했습니다: {e}")
        sys.exit(1)
    
    logging.info("Ariel 클라이언트 이벤트 루프 시작.")
    sys.exit(app.exec())

if __name__ == "__main__":
    main()