import os
from pathlib import Path

def display_project_structure(root_dir=".", indent="", ignored_dirs=None, ignored_files=None):
    """
    프로젝트의 디렉토리 구조를 트리 형태로 출력합니다.
    특정 디렉토리와 파일을 무시할 수 있습니다.
    """
    if ignored_dirs is None:
        # 무시할 폴더 목록: 필요에 따라 추가하세요.
        ignored_dirs = {".git", ".idea", "venv", "__pycache__", "dist", "build"}
    if ignored_files is None:
        # 무시할 파일 목록
        ignored_files = {".gitignore", ".env"}

    # 현재 경로를 Path 객체로 변환
    root_path = Path(root_dir)
    if not root_path.is_dir():
        return

    # 현재 디렉토리의 내용물을 리스트로 변환 후 정렬
    items = sorted(list(root_path.iterdir()), key=lambda x: (x.is_file(), x.name.lower()))
    
    # 마지막 아이템을 확인하기 위해 리스트 생성
    printable_items = [item for item in items if item.name not in ignored_dirs and item.name not in ignored_files]

    for i, item in enumerate(printable_items):
        is_last = (i == len(printable_items) - 1)
        
        # 트리 모양 결정
        connector = "└── " if is_last else "├── "
        print(f"{indent}{connector}{item.name}")
        
        # 디렉토리일 경우 재귀적으로 호출
        if item.is_dir():
            new_indent = indent + ("    " if is_last else "│   ")
            display_project_structure(item, new_indent, ignored_dirs, ignored_files)


if __name__ == "__main__":
    # 스크립트가 위치한 곳을 기준으로 프로젝트 구조를 출력합니다.
    print(f"{Path.cwd().name}/")
    display_project_structure()