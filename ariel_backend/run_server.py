# ariel_backend/run_server.py (이 코드로 전체 교체)

import sys
import os
import uvicorn
from fastapi import FastAPI
import logging
from typing import List

# ModuleNotFoundError를 해결하기 위해 프로젝트 루트를 시스템 경로에 추가합니다.
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.append(project_root)

os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

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

@app.on_event("startup")
async def startup_event():
    """
    [V12.2 수정] FastAPI 서버가 시작될 때 실행됩니다.
    사용 가능한 모든 STT 모델을 메모리에 미리 로드합니다.
    """
    logger.info("Server startup sequence initiated...")
    try:
        # 클라이언트의 ConfigManager를 사용하여 설정 로드
        config = ConfigManager()
        # [핵심 수정] 로드할 모델 목록과 장치/계산 유형 설정을 가져옵니다.
        # 이 값들이 설정에 없으면 합리적인 기본값을 사용합니다.
        model_sizes_to_load: List[str] = config.get("stt_available_models", ["tiny", "base", "small", "medium"])
        device: str = config.get("stt_device", "auto")
        compute_type: str = config.get("stt_compute_type", "auto")
        
        logger.info(f"Configuration loaded. Attempting to load models: {model_sizes_to_load}")
        
        # [핵심 수정] stt_service의 load_models 메서드를 호출하여 모든 모델을 메모리에 올립니다.
        stt_service.load_models(
            model_sizes=model_sizes_to_load,
            device=device,
            compute_type=compute_type
        )
        
    except Exception as e:
        logger.critical(f"A critical error occurred during model loading: {e}", exc_info=True)
        logger.critical("STT service will be unavailable. Please check the model configuration and files.")

# /api/v1 접두사를 사용하여 v1 엔드포인트 라우터 포함
app.include_router(endpoints.router, prefix="/api/v1", tags=["v1"])

@app.get("/")
def read_root():
    return {"message": "Welcome to Ariel Backend API"}

if __name__ == "__main__":
    logger.info("Starting Ariel Backend server...")
    uvicorn.run("ariel_backend.run_server:app", host="127.0.0.1", port=8000, reload=False)