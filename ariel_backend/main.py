# main.py
import logging
from fastapi import FastAPI
from ariel_backend.api.v1 import endpoints

# 기본 로거 설정
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

app = FastAPI(
    title="Project Ariel Backend",
    description="Provides STT and OCR services for the Ariel client.",
    version="1.0.0"
)

# API v1 라우터 포함
app.include_router(endpoints.router, prefix="/api/v1")

@app.get("/", tags=["Root"])
async def read_root():
    return {"message": "Welcome to the Project Ariel Backend API."}