# ariel_backend/main.py
import os
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
import uvicorn
from fastapi import FastAPI
from api.v1 import endpoints
import logging

# 기본 로깅 설정
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Ariel Backend")

# /api/v1 접두사를 사용하여 v1 엔드포인트 라우터 포함
app.include_router(endpoints.router, prefix="/api/v1")

@app.get("/")
def read_root():
    return {"message": "Welcome to Ariel Backend API"}