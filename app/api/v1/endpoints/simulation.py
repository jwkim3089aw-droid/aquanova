# app/api/v1/endpoints/simulation.py
from __future__ import annotations

import uuid
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from sqlalchemy.orm import Session

from app.api.v1.schemas import SimulationRequest, ScenarioOutput
from app.db.models import Scenario
from app.db.session import get_db
from app.services.simulation.engine import SimulationEngine

# Project 모델이 없을 수도 있으니(모듈 구조/순환참조 등), 안전하게 import
try:
    from app.db.models import Project  # type: ignore
except Exception:
    Project = None  # type: ignore


router = APIRouter(tags=["simulations"])


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def _to_dict(obj: Any) -> Dict[str, Any]:
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    return dict(obj)


def _try_parse_uuid(v: Any) -> Optional[uuid.UUID]:
    if v is None:
        return None
    if isinstance(v, uuid.UUID):
        return v
    try:
        return uuid.UUID(str(v).strip())
    except Exception:
        return None


def _coerce_project_uuid(project_id_raw: Any, *, fallback_key: str) -> uuid.UUID:
    """
    project_id_raw가:
      - uuid.UUID or UUID string -> 그대로 UUID로
      - 'e2e' 같은 문자열        -> uuid5로 deterministic UUID 생성
      - None/빈값               -> fallback_key 기반 uuid5
    """
    u = _try_parse_uuid(project_id_raw)
    if u is not None:
        return u

    if isinstance(project_id_raw, str) and project_id_raw.strip():
        key = project_id_raw.strip()
        return uuid.uuid5(uuid.NAMESPACE_URL, f"project:{key}")

    return uuid.uuid5(uuid.NAMESPACE_URL, f"project:{fallback_key}")


def _ensure_project_row(db: Session, project_uuid: uuid.UUID, project_key: str) -> None:
    """
    FK가 엄격한 DB에서 Scenario.project_id 삽입이 실패하지 않도록,
    Project 모델이 존재하면 해당 UUID의 row를 미리 보장한다.

    - commit 하지 않고 flush만 수행: 이후 Scenario commit과 함께 한 트랜잭션으로 커밋됨.
    """
    if Project is None:
        # Project 모델이 import 불가인데 FK가 켜져있으면 Scenario insert에서 실패할 수 있음.
        # (그 경우 DB 에러 detail로 확인 가능)
        return

    existing = db.get(Project, project_uuid)
    if existing:
        return

    p = Project()  # type: ignore

    # id 강제 주입 (UUIDMixin이 있어도 안전)
    if hasattr(p, "id"):
        setattr(p, "id", project_uuid)

    # Project.name은 보통 NOT NULL이므로 반드시 채워준다
    name_value = project_key.strip() if project_key else "default"
    if hasattr(p, "name"):
        setattr(p, "name", name_value)
    else:
        # name 필드가 다른 이름이면 best-effort
        for f in ("project_name", "title"):
            if hasattr(p, f):
                setattr(p, f, name_value)
                break

    # description optional이면 채워줌
    if hasattr(p, "description"):
        try:
            setattr(p, "description", "auto-created by /simulation/run")
        except Exception:
            pass

    db.add(p)
    # flush로 INSERT만 날려 FK 참조 가능하게 만듦
    db.flush()


# -----------------------------------------------------------------------------
# Endpoint
# -----------------------------------------------------------------------------
@router.post("/run", response_model=ScenarioOutput)
def run_simulation(request: SimulationRequest, db: Session = Depends(get_db)):
    logger.info(f"🚀 [Simulation Start] ID: {request.simulation_id}")

    try:
        # 1) Run engine
        engine = SimulationEngine()
        result = engine.run(request)

        # 2) Normalize payload/result
        req_dict: Dict[str, Any] = request.model_dump()
        res_dict: Dict[str, Any] = _to_dict(result)

        # 3) Resolve project UUID (project_id가 'e2e'여도 DB는 UUID로 저장)
        project_key_raw = req_dict.get("project_id")
        fallback_key = str(req_dict.get("simulation_id") or "default")
        project_uuid = _coerce_project_uuid(project_key_raw, fallback_key=fallback_key)

        # FK 보장 (가능한 경우)
        _ensure_project_row(db, project_uuid, str(project_key_raw or "default"))

        # 4) Persist Scenario
        scn = Scenario()

        # ✅ UUID 컬럼 방어: id/project_id는 uuid.UUID 객체
        if hasattr(scn, "id"):
            scn.id = uuid.uuid4()

        scn.project_id = project_uuid
        scn.name = (
            req_dict.get("scenario_name") or req_dict.get("simulation_id") or "Untitled"
        )
        scn.input_json = req_dict

        db.add(scn)
        db.commit()
        db.refresh(scn)

        # 5) Return response with persisted scenario_id
        scenario_id_str = str(scn.id)

        if hasattr(result, "model_copy"):
            return result.model_copy(update={"scenario_id": scenario_id_str})

        res_dict["scenario_id"] = scenario_id_str
        return res_dict

    except ValueError as e:
        logger.warning(f"⚠️ Validation Error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("🔥 Internal Simulation Error")
        raise HTTPException(status_code=500, detail=str(e))
