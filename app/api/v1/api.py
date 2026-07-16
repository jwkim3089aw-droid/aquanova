# app/api/v1/api.py
from fastapi import APIRouter

from app.api.v1.endpoints import (
    simulation,
    membranes,
    health,
    user_settings,
    reports,
    logs,
)

api_router = APIRouter()

# 1. Core Engine
api_router.include_router(simulation.router, prefix="/simulation", tags=["Simulation"])

# 2. Data & Resources
api_router.include_router(membranes.router, prefix="/membranes", tags=["Membranes"])
api_router.include_router(
    user_settings.router, prefix="/user-settings", tags=["Settings"]
)

# 3. Features
api_router.include_router(reports.router, prefix="/reports", tags=["Reports"])

# 4. System & Diagnostics
api_router.include_router(health.router, tags=["Health"])
api_router.include_router(logs.router, prefix="/logs", tags=["Logs"])
