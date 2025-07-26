# Python 3.9 버전을 기반 이미지로 사용
FROM python:3.9-slim

# 컨테이너 내 작업 디렉토리 설정
WORKDIR /app

# 위에서 정의한 requirements.txt를 컨테이너에 복사
COPY ./requirements.txt /app/requirements.txt

# 복사된 requirements.txt를 사용하여 의존성 설치
RUN pip install --no-cache-dir --upgrade -r /app/requirements.txt

# 현재 디렉토리의 모든 소스 코드를 컨테이너의 /app 디렉토리로 복사
COPY . /app

# 컨테이너 실행 시 FastAPI 서버를 구동하는 명령어
# (ariel_backend 루트에 main.py가 있다고 가정)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]