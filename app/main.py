# app\main.py
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Dict, Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

# Config & Logger
from app.core.config import settings
from app.core.logging import logger, setup_logging

# Routers (통합 라우터 하나만 Import)
from app.api.v1.api import api_router


# ==============================================================================
# 1. Lifespan (수명 주기 관리)
# ==============================================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    서버 시작/종료 시 실행될 로직
    """
    # [Startup]
    setup_logging()
    env = getattr(settings, "APP_ENV", "local")
    logger.info(f"🚀 AquaNova Server Starting... (Env: {env})")

    yield

    # [Shutdown]
    logger.info("🛑 AquaNova Server Shutting Down...")


# ==============================================================================
# 2. FastAPI App 초기화
# ==============================================================================
app = FastAPI(
    title=settings.PROJECT_NAME,
    version="0.1.0",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan,
)

# ==============================================================================
# 3. Middleware (CORS)
# ==============================================================================
# 개발 편의를 위해 모든 출처 허용 (배포 시 settings.BACKEND_CORS_ORIGINS 사용 권장)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==============================================================================
# 4. Router Registration
# ==============================================================================
# 모든 API 엔드포인트는 api_router를 통해 통합 관리됩니다.
app.include_router(api_router, prefix=settings.API_V1_STR)


# ==============================================================================
# 5. Root Endpoint
# ==============================================================================
@app.get("/", include_in_schema=False)
def root() -> Dict[str, Any]:
    """서버 상태 확인용 루트 엔드포인트"""
    return {
        "message": "Welcome to AquaNova API",
        "docs_url": "/docs",
        "redoc_url": "/redoc",
        "status": "running",
    }


@app.get("/health", include_in_schema=False)
def health_check():
    """로드밸런서용 단순 헬스 체크"""
    return {"status": "ok"}
