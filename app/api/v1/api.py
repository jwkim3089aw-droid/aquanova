from fastapi import APIRouter

# Endpoints Import
# (만약 health, user_settings, reports 파일이 없다면 해당 라인은 주석 처리하거나 지워주세요)
from app.api.v1.endpoints import (
    simulation,
    membranes,
    health,
    user_settings,
    reports,
)

api_router = APIRouter()

# ==============================================================================
# 1. Core Engine (핵심 시뮬레이션)
# ==============================================================================
api_router.include_router(simulation.router, prefix="/simulation", tags=["Simulation"])

# ==============================================================================
# 2. Data & Resources (데이터 조회 및 설정)
# ==============================================================================
api_router.include_router(membranes.router, prefix="/membranes", tags=["Membranes"])
api_router.include_router(
    user_settings.router, prefix="/user-settings", tags=["Settings"]
)

# ==============================================================================
# 3. Features (리포트 등 부가 기능)
# ==============================================================================
api_router.include_router(reports.router, prefix="/reports", tags=["Reports"])

# ==============================================================================
# 4. System (헬스 체크)
# ==============================================================================
api_router.include_router(health.router, tags=["Health"])
