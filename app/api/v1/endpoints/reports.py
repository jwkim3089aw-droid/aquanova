# app/api/v1/endpoints/reports.py
from __future__ import annotations

import json
import logging  # 로그 출력을 위해 추가
from uuid import UUID
from pathlib import Path
from typing import Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

# Redis 라이브러리 체크
try:
    import redis
    from rq import Queue, Retry, job

    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

from app.core.config import settings
from app.db.session import get_db
from app.db.models import Scenario, ReportJob, ReportStatus
from app.services.tasks import task_generate_report
from app.core.fs import find_report_pdf
from ..schemas import (
    EnqueueReportIn,
    EnqueueReportOut,
    ReportStatusOut,
    SimulationRequest,
)

router = APIRouter()
logger = logging.getLogger(__name__)  # 로거 설정

# --------------------------------------------------------------------------
# Helper Functions
# --------------------------------------------------------------------------


def _ensure_dict(v: Any) -> Dict[str, Any] | None:
    if v is None:
        return None
    if isinstance(v, dict):
        return v
    if isinstance(v, str):
        try:
            parsed = json.loads(v)
            if isinstance(parsed, dict):
                return parsed
        except (json.JSONDecodeError, TypeError):
            pass
    return None


# --------------------------------------------------------------------------
# Endpoints
# --------------------------------------------------------------------------


@router.post("/enqueue", response_model=EnqueueReportOut)
def enqueue_report(
    payload: EnqueueReportIn,
    out_units: Optional[str] = Query(default=None),
    project_id: Optional[str] = Query(default=None),
    user_id: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
):
    """
    리포트 생성 요청 (Redis가 없으면 동기적으로 즉시 실행)
    """
    # 1. 시나리오 조회
    scenario_id_str = str(payload.scenario_id)
    scn = db.get(Scenario, scenario_id_str)

    if not scn:
        raise HTTPException(
            status_code=404, detail=f"Scenario not found: {scenario_id_str}"
        )

    # 2. 시나리오 데이터 파싱
    raw_input = getattr(scn, "input_json", None)
    in_dict = _ensure_dict(raw_input)

    if in_dict is None:
        in_dict = {
            "project_id": getattr(scn, "project_id", "default"),
            "scenario_name": getattr(scn, "name", None)
            or getattr(scn, "scenario_name", "Untitled"),
            "feed": _ensure_dict(
                getattr(scn, "feed", None) or getattr(scn, "feed_json", None)
            ),
            "stages": _ensure_dict(
                getattr(scn, "stages", None) or getattr(scn, "stages_json", None)
            ),
            "options": _ensure_dict(getattr(scn, "options", None)) or {},
        }

    try:
        sim_req = SimulationRequest(**in_dict)
    except Exception as e:
        raise HTTPException(
            status_code=409, detail=f"Invalid scenario data structure: {str(e)}"
        )

    task_payload = sim_req.model_dump()

    # 3. Job DB 레코드 생성 (일단 Queued 상태로 시작)
    job_row = ReportJob(
        scenario_id=scn.id,
        status=ReportStatus.queued,
        queue="reports",
    )
    db.add(job_row)
    db.commit()
    db.refresh(job_row)

    # 4. 작업 실행 (Redis 시도 -> 실패시 즉시 실행)
    used_redis = False

    if REDIS_AVAILABLE:
        try:
            r = redis.from_url(settings.REDIS_URL)
            if r.ping():  # 실제 연결 체크
                q = Queue("reports", connection=r)
                q.enqueue(
                    task_generate_report,
                    task_payload,
                    str(job_row.id),
                    out_units,
                    project_id,
                    user_id,
                    job_id=str(job_row.id),
                    retry=Retry(max=3, interval=10),
                    ttl=600,
                    result_ttl=86400,
                )
                used_redis = True
        except Exception as e:
            logger.warning(
                f"Redis not available ({e}). Falling back to synchronous execution."
            )

    # Redis를 안 썼거나 실패했다면 -> 여기서 바로 함수 실행 (Fallback)
    if not used_redis:
        try:
            # 상태를 '처리중'으로 변경 (선택 사항)
            job_row.status = ReportStatus.started
            db.commit()

            # 🚀 [핵심] 그냥 함수를 바로 호출해버림! (기다렸다가 끝남)
            task_generate_report(
                task_payload, str(job_row.id), out_units, project_id, user_id
            )
            # task_generate_report 내부에서 DB를 Succeeded로 업데이트함
        except Exception as e:
            job_row.status = ReportStatus.failed
            job_row.error_message = f"Sync Execution Failed: {str(e)}"
            db.commit()
            raise HTTPException(
                status_code=500, detail=f"Report generation failed: {str(e)}"
            )

    return EnqueueReportOut(job_id=job_row.id)


@router.get("/{job_id}", response_model=ReportStatusOut)
def get_report_status(job_id: UUID, db: Session = Depends(get_db)):
    job_row = db.get(ReportJob, job_id)
    if not job_row:
        raise HTTPException(status_code=404, detail="Report job not found")

    error_message = getattr(job_row, "error_message", None)

    # Redis를 사용한 경우에만 RQ 상태 체크
    if REDIS_AVAILABLE and job_row.status in [
        ReportStatus.queued,
        ReportStatus.started,
    ]:
        try:
            r = redis.from_url(settings.REDIS_URL)
            # 연결 확인 후 조회
            if r.ping():
                rq_job = job.Job.fetch(str(job_id), connection=r)
                if rq_job and rq_job.get_status() == "failed":
                    if rq_job.exc_info:
                        error_message = rq_job.exc_info.splitlines()[-1][:500]
        except Exception:
            pass  # Redis 에러 무시 (DB 상태가 진실)

    return ReportStatusOut(
        job_id=job_row.id,
        status=job_row.status.value,
        artifact_path=getattr(job_row, "artifact_path", None),
        error_message=error_message,
        enqueued_at=getattr(job_row, "enqueued_at", None),
        started_at=getattr(job_row, "started_at", None),
        finished_at=getattr(job_row, "finished_at", None),
    )


@router.get("/{job_id}/download")
def download_report(job_id: UUID, db: Session = Depends(get_db)):
    job_row = db.get(ReportJob, job_id)
    if not job_row:
        raise HTTPException(status_code=404, detail="Report job not found")

    # 실패한 경우 에러 메시지 반환
    if job_row.status == ReportStatus.failed:
        raise HTTPException(
            status_code=409, detail=f"Report generation failed: {job_row.error_message}"
        )

    if job_row.status != ReportStatus.succeeded:
        raise HTTPException(
            status_code=409,
            detail=f"Report is not ready. Status: {job_row.status.value}",
        )

    candidates = []
    artifact_path = getattr(job_row, "artifact_path", None)
    if artifact_path:
        p = Path(artifact_path)
        if not p.is_absolute():
            p = Path.cwd() / p
        candidates.append(p)

    alt_path = find_report_pdf(str(job_id))
    if alt_path:
        candidates.append(alt_path)

    for p in candidates:
        if p.exists() and p.is_file():
            return FileResponse(
                path=p,
                media_type="application/pdf",
                filename=f"AquaNova_Report_{job_id}.pdf",
            )

    raise HTTPException(status_code=404, detail="Report file missing on server disk")
