# app\api\v1\endpoints\simulation.py
from fastapi import APIRouter, HTTPException
from loguru import logger

from app.api.v1.schemas import SimulationRequest, ScenarioOutput
from app.services.simulation.engine import SimulationEngine

router = APIRouter(tags=["simulations"])


@router.post("/run", response_model=ScenarioOutput)
def run_simulation(request: SimulationRequest):
    """
    [통합 시뮬레이션 실행]
    - 입력: SimulationRequest (자동 검증됨)
    - 실행: SimulationEngine이 알아서 모듈별 계산 수행
    - 반환: ScenarioOutput
    """
    logger.info(f"🚀 [Simulation Start] ID: {request.simulation_id}")

    try:
        # 1. 엔진 인스턴스 생성
        engine = SimulationEngine()

        # 2. 실행 (단 한 줄)
        result = engine.run(request)

        return result

    except ValueError as e:
        logger.warning(f"⚠️ Validation Error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("🔥 Internal Simulation Error")
        raise HTTPException(status_code=500, detail=str(e))
