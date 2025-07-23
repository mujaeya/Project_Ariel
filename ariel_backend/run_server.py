# ariel_backend/run_server.py (이 코드로 전체 교체)

import sys
import os
import uvicorn
from fastapi import FastAPI
import logging

# [핵심 수정]
# ModuleNotFoundError를 해결하기 위해 프로젝트 루트를 시스템 경로에 추가합니다.
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.append(project_root)

# KMP_DUPLICATE_LIB_OK 설정은 Torch 또는 Numpy와 함께 MKL을 사용할 때
# 발생할 수 있는 충돌을 피하기 위한 것입니다. 경로 설정 다음에 위치해도 무방합니다.
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

# [스프린트 1 수정] 필요한 모듈 임포트
from ariel_backend.api.v1 import endpoints
from ariel_backend.services.stt_service import stt_service
# 클라이언트와 백엔드가 공유하는 config.json을 읽기 위해 ConfigManager를 임포트
from ariel_client.src.config_manager import ConfigManager

# 기본 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("root")


app = FastAPI(title="Ariel Backend")

# [스프린트 1 수정] FastAPI 시작 이벤트 핸들러 추가
@app.on_event("startup")
async def startup_event():
    """
    FastAPI 서버가 시작될 때 실행됩니다.
    설정 파일에서 모델 크기를 읽어와 STT 모델을 로드합니다.
    """
    logger.info("Server startup sequence initiated...")
    try:
        # 클라이언트의 ConfigManager를 사용하여 설정 로드
        config = ConfigManager()
        # 설정에서 모델 크기를 가져옵니다. 값이 없으면 'medium'을 기본값으로 사용합니다.
        model_size = config.get("stt_model_size", "medium")
        
        logger.info(f"Configuration loaded. Attempting to load model: '{model_size}'")
        # stt_service의 load_model 메서드를 호출하여 모델을 메모리에 올립니다.
        stt_service.load_model(model_size=model_size)
        
    except Exception as e:
        logger.critical(f"A critical error occurred during model loading: {e}", exc_info=True)
        logger.critical("STT service will be unavailable. Please check the model configuration and files.")
        # 모델 로딩에 실패해도 서버 자체는 실행될 수 있도록 처리합니다.
        # stt_service는 내부적으로 model이 None으로 유지됩니다.

# /api/v1 접두사를 사용하여 v1 엔드포인트 라우터 포함
app.include_router(endpoints.router, prefix="/api/v1", tags=["v1"])

@app.get("/")
def read_root():
    return {"message": "Welcome to Ariel Backend API"}

if __name__ == "__main__":
    logger.info("Starting Ariel Backend server...")
    uvicorn.run("ariel_backend.run_server:app", host="127.0.0.1", port=8000, reload=False)