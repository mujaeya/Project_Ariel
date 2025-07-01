# src/utils.py (새 파일)
import sys
import os

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller/Nuitka """
    try:
        # PyInstaller/Nuitka가 생성한 임시 폴더에서 실행될 때의 경로
        base_path = sys._MEIPASS
    except Exception:
        # 일반 개발 환경에서 실행될 때의 경로 (프로젝트 루트)
        base_path = os.path.abspath(".")
        
    return os.path.join(base_path, relative_path)