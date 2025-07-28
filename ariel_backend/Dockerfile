# Dockerfile
# 1. 베이스 이미지 선택
FROM python:3.10-slim

# 2. 작업 디렉토리 설정
WORKDIR /app

# 3. 의존성 설치 (코드를 복사하기 전에 설치하여 Docker 빌드 캐시를 활용)
COPY ./requirements.txt .
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# 4. 소스 코드 및 모델 폴더 복사
COPY . .

# 5. FastAPI 서버가 사용할 포트 노출
EXPOSE 8000

# 6. 컨테이너 시작 시 실행될 기본 명령어
# (docker-compose에서 --reload 옵션으로 덮어쓸 예정)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]