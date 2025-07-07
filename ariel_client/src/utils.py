import os
import sys
import logging
from logging.config import dictConfig

def resource_path(relative_path: str) -> str:
    """
    [수정] 개발 환경 및 PyInstaller 패키징 환경 모두에서 리소스 파일의 절대 경로를 반환합니다.
    실행 방식에 상관없이 안정적으로 작동하도록 수정되었습니다.
    """
    try:
        # PyInstaller로 패키징된 경우, _MEIPASS에 임시 폴더 경로가 저장됩니다.
        base_path = sys._MEIPASS
    except Exception:
        # 개발 환경에서는 이 파일(utils.py)이 있는 'src' 폴더를 기준으로 경로를 설정합니다.
        base_path = os.path.dirname(os.path.abspath(__file__))
        
    return os.path.join(base_path, relative_path)

def setup_logging():
    """프로젝트 전반의 로깅 설정을 초기화합니다."""
    log_config = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'default': {
                'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                'datefmt': '%Y-%m-%d %H:%M:%S',
            },
        },
        'handlers': {
            'console': {
                'class': 'logging.StreamHandler',
                'formatter': 'default',
                'level': 'INFO',
            },
        },
        'root': {
            'handlers': ['console'],
            'level': 'INFO',
        },
    }
    dictConfig(log_config)
    logging.info("로깅 시스템 초기화 완료.")