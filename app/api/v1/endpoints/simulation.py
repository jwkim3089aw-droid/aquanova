# app/api/v1/endpoints/simulation.py
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.models import Scenario
from app.db.session import get_db
from app.schemas.simulation import ScenarioOutput, SimulationRequest
from app.services.simulation.engine import SimulationEngine
from app.services.simulation.wave_corrected_engine import (
    run_simulation_with_optional_wave_correction,
)


# --- V123A public precision report sanitizer ---
def _v123a_public_precision_report(report):
    if not isinstance(report, dict):
        return report

    corrections = []
    for item in report.get("corrections") or []:
        if not isinstance(item, dict):
            continue
        corrections.append(
            {
                "metric": item.get("metric"),
                "status": item.get("status"),
                "raw_value": item.get("raw_value"),
                "corrected_value": item.get("corrected_value"),
            }
        )

    return {
        "schema_version": "aquanova.precision_report.v123",
        "enabled": bool(report.get("enabled", False)),
        "mode": "precision" if report.get("enabled", False) else "raw",
        "status": report.get("status"),
        "applied_count": int(report.get("applied_count") or 0),
        "skipped_count": int(report.get("skipped_count") or 0),
        "process_type": report.get("process_type"),
        "scope": report.get("regime") or report.get("scope"),
        "corrections": corrections,
    }


def _v123a_sanitize_simulation_response_public(obj):
    if obj is None:
        return obj

    if isinstance(obj, dict):
        if "precision_report" in obj:
            obj["precision_report"] = _v123a_public_precision_report(
                obj.get("precision_report")
            )
        return obj

    try:
        if hasattr(obj, "precision_report"):
            obj.precision_report = _v123a_public_precision_report(
                getattr(obj, "precision_report", None)
            )
    except Exception:
        pass
    return obj



# Project 모델 안전한 가져오기
try:
    from app.db.models import Project
except ImportError:
    Project = None

router = APIRouter(tags=["simulations"])

# =============================================================================
# 1. Private Domain Logic (ID & Persistence)
# =============================================================================


class _SimulationService:
    """엔드포인트에서 호출하는 비즈니스 로직 및 영속화 서비스 클래스"""

    @staticmethod
    def resolve_project_uuid(project_id_raw: Any, fallback: str) -> uuid.UUID:
        """문자열 아이디를 결정론적 UUID v5로 변환"""
        if isinstance(project_id_raw, uuid.UUID):
            return project_id_raw

        try:
            return uuid.UUID(str(project_id_raw).strip())
        except (ValueError, AttributeError):
            # URL 네임스페이스를 기준으로 프로젝트 식별자 생성
            name = str(project_id_raw).strip() if project_id_raw else fallback
            return uuid.uuid5(uuid.NAMESPACE_URL, f"aquanova:project:{name}")

    @staticmethod
    def ensure_project(db: Session, project_uuid: uuid.UUID, name: str) -> None:
        """프로젝트 행 존재 보장 (Upsert 개념)"""
        if Project is None or db.get(Project, project_uuid):
            return

        new_project = Project(
            id=project_uuid,
            name=name or "Default Project",
            description="Auto-created by simulation engine",
        )
        db.add(new_project)
        try:
            db.flush()
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to ensure project: {e}")

    @classmethod
    def persist_scenario(
        self, db: Session, request: SimulationRequest, result: ScenarioOutput
    ) -> uuid.UUID:
        """시뮬레이션 입력과 결과를 DB에 박제"""
        project_id_raw = getattr(request, "project_id", "default")
        project_uuid = self.resolve_project_uuid(
            project_id_raw, str(request.simulation_id)
        )

        self.ensure_project(db, project_uuid, str(project_id_raw))

        new_scenario = Scenario(
            id=uuid.uuid4(),
            project_id=project_uuid,
            name=request.scenario_name or f"Sim-{datetime.now().strftime('%m%d%H%M')}",
            input_json=request.model_dump(),
            output_json=result.model_dump(),
        )

        db.add(new_scenario)
        db.commit()
        db.refresh(new_scenario)
        return new_scenario.id


# =============================================================================
# 2. HTTP Endpoints (Controller)
# =============================================================================


@router.post("/run", response_model=ScenarioOutput, response_model_exclude_none=True)
def run_simulation(request: SimulationRequest, db: Session = Depends(get_db)):
    """
    [Core] 수처리 시뮬레이션 엔진 구동
    """
    logger.info(f"🚀 [Simulation] Starting engine for ID: {request.simulation_id}")

    try:
        # 1) 엔진 계산 실행
        # V120: explicit WAVE correction opt-in. Default path stays raw SimulationEngine.
        wave_correction_enabled = bool(
            (
                getattr(request, "precision_mode_enabled", False)
                or getattr(request, "wave_correction_enabled", False)
            )
        )
        calibration_mode = (
            str(getattr(request, "calibration_mode", "") or "").strip().lower()
        )
        wave_correction_enabled = wave_correction_enabled or calibration_mode in {
            "wave",
            "wave_opt_in",
            "precision",
            "calibrated",
            "validated",
            "wave_correction",
            "wave_calibrated",
        }
        if wave_correction_enabled:
            result, correction_report = run_simulation_with_optional_wave_correction(
                request,
                options={"enable_wave_correction": True},
            )
            try:
                if hasattr(result, "model_copy"):
                    result = result.model_copy(
                        update={"precision_report": correction_report}
                    )
                elif hasattr(result, "copy"):
                    result = result.copy(update={"precision_report": correction_report})
                else:
                    setattr(result, "precision_report", correction_report)
            except Exception:
                logger.warning(
                    "WAVE correction report could not be attached to response",
                    exc_info=True,
                )
        else:
            engine = SimulationEngine()
            result = engine.run(request)

        # 2) DB 영속화 (선택 사항: 필요 시 주석 해제)
        # sc_id = _SimulationService.persist_scenario(db, request, result)
        sc_id = uuid.uuid4()  # DB 저장 스킵 시 임시 ID 발급

        # 3) 결과 반환
        return _v123a_sanitize_simulation_response_public(result).model_copy(
            update={"scenario_id": str(sc_id)}
        )

    except ValueError as e:
        logger.warning(f"⚠️ Simulation Validation: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("🔥 Internal Simulation Engine Error")
        raise HTTPException(status_code=500, detail="Internal processing error")


# =============================================================================
# 3. Canvas Management (Save/Load/List)
# =============================================================================


class CanvasSaveRequest(BaseModel):
    scenario_id: Optional[str] = None
    name: str = Field(..., description="시나리오 이름")
    project_id: str = Field(default="default", description="프로젝트 ID")
    canvas_state: dict = Field(..., description="UI 노드 및 엣지 상태 데이터")


class ScenarioListItem(BaseModel):
    id: str
    name: str
    created_at: datetime
    updated_at: Optional[datetime] = None


@router.post("/save", response_model=Dict[str, str])
def save_canvas(req: CanvasSaveRequest, db: Session = Depends(get_db)):
    """프론트엔드 캔버스 상태(Node/Edge)를 Upsert 방식으로 저장"""

    project_uuid = _SimulationService.resolve_project_uuid(
        req.project_id, "canvas_save"
    )
    _SimulationService.ensure_project(db, project_uuid, req.project_id)

    scenario_uuid = None
    if req.scenario_id:
        try:
            scenario_uuid = uuid.UUID(req.scenario_id)
        except ValueError:
            pass

    # Upsert 로직
    scenario = db.get(Scenario, scenario_uuid) if scenario_uuid else None

    if not scenario:
        scenario = Scenario(id=uuid.uuid4(), project_id=project_uuid)
        db.add(scenario)

    scenario.name = req.name
    scenario.input_json = req.canvas_state

    if hasattr(scenario, "updated_at"):
        scenario.updated_at = datetime.utcnow()

    db.commit()
    return {"message": "저장되었습니다.", "scenario_id": str(scenario.id)}


@router.get("/scenarios", response_model=List[ScenarioListItem])
def list_scenarios(db: Session = Depends(get_db)):
    """저장된 시나리오 목록 조회 (최신순 50개)"""
    query = db.query(Scenario)

    if hasattr(Scenario, "created_at"):
        query = query.order_by(Scenario.created_at.desc())
    else:
        query = query.order_by(Scenario.id.desc())

    scenarios = query.limit(50).all()
    return [
        ScenarioListItem(
            id=str(s.id),
            name=s.name or "Untitled",
            created_at=getattr(s, "created_at", datetime.utcnow()),
            updated_at=getattr(s, "updated_at", None),
        )
        for s in scenarios
    ]


@router.get("/scenarios/{scenario_id}")
def get_scenario(scenario_id: str, db: Session = Depends(get_db)):
    """특정 시나리오의 캔버스 데이터 로드"""
    try:
        sc_uuid = uuid.UUID(scenario_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID format")

    scenario = db.get(Scenario, sc_uuid)
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")

    return {
        "id": str(scenario.id),
        "name": scenario.name,
        "canvas_state": scenario.input_json,
    }


@router.delete("/scenarios/{scenario_id}")
def delete_scenario(scenario_id: str, db: Session = Depends(get_db)):
    """시나리오 영구 삭제"""
    try:
        sc_uuid = uuid.UUID(scenario_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID format")

    scenario = db.get(Scenario, sc_uuid)
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")

    db.delete(scenario)
    db.commit()
    return {"message": "Deleted successfully"}
