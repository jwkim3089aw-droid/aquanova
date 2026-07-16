# app/api/v1/endpoints/reports.py
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from loguru import logger
from sqlalchemy.orm import Session

try:
    import redis
    from rq import Queue, Retry, Worker
    from rq.job import Job as RqJob

    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

from app.core.config import settings
from app.core.fs import find_report_pdf
from app.db.models import ReportJob, ReportStatus, Scenario
from app.db.session import get_db
from app.services.tasks import task_generate_report
from ..schemas import (
    EnqueueReportIn,
    EnqueueReportOut,
    ReportStatusOut,
    SimulationRequest,
)

router = APIRouter()
QUEUE_NAME = "reports"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_json(v: Any, default_type: type) -> Any:
    if isinstance(v, default_type):
        return v
    if isinstance(v, str):
        try:
            parsed = json.loads(v)
            if isinstance(parsed, default_type):
                return parsed
        except Exception:
            pass
    return default_type()


def _get_code_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _get_out_dir() -> Path:
    d = _get_code_root() / "reports" / "outputs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _resolve_pdf(job_id: uuid.UUID, artifact_path: str | None) -> Path | None:
    job_id_str = str(job_id)
    candidates = []

    def _add(p: str | Path | None):
        if not p:
            return
        path = Path(p)
        candidates.append(path if path.is_absolute() else _get_code_root() / path)

    if artifact_path:
        _add(artifact_path)
        try:
            _add(artifact_path.encode("latin1").decode("utf-8"))
        except Exception:
            pass

    _add(find_report_pdf(job_id_str))
    out_dir = _get_out_dir()
    candidates.append(out_dir / f"{job_id_str}.pdf")
    candidates.extend(out_dir.glob(f"{job_id_str}*.pdf"))

    return next((p.resolve() for p in candidates if p.exists() and p.is_file()), None)


def _is_e2e_payload(payload: dict) -> bool:
    pid = str(payload.get("project_id", "")).strip().lower()
    sim_id = str(payload.get("simulation_id", "")).strip().lower()
    return pid == "e2e" or sim_id.startswith("e2e-")


def _is_e2e_job(db: Session, job: ReportJob) -> bool:
    if not getattr(job, "scenario_id", None):
        return False
    scn = db.get(Scenario, job.scenario_id)
    return (
        _is_e2e_payload(_parse_json(getattr(scn, "input_json", None), dict))
        if scn
        else False
    )


def _db_session():
    try:
        from app.db.session import SessionLocal

        return SessionLocal()
    except Exception:
        from sqlalchemy.orm import sessionmaker
        from app.db.session import engine

        return sessionmaker(
            bind=engine, autoflush=False, autocommit=False, future=True
        )()


def _update_job(
    job_id: uuid.UUID,
    status: ReportStatus,
    artifact: str | None = None,
    error: str | None = None,
):
    with _db_session() as db:
        job = db.get(ReportJob, job_id)
        if not job or job.status in (ReportStatus.succeeded, ReportStatus.failed):
            return
        job.status = status

        if status == ReportStatus.succeeded and artifact:
            job.artifact_path = artifact
        elif error:
            job.error_message = str(error)[:500]

        if status == ReportStatus.running:
            job.started_at = _now()
        elif status in (ReportStatus.succeeded, ReportStatus.failed):
            job.finished_at = _now()
        db.commit()


def _generate_fast_e2e_pdf(
    pdf_path: Path, job_id: uuid.UUID, payload: Dict[str, Any]
) -> Path:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    c = canvas.Canvas(str(pdf_path), pagesize=A4)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(72, A4[1] - 72, "AquaNova Report (E2E Fast)")
    c.setFont("Helvetica", 11)
    y = A4[1] - 100
    for k in ["scenario_id", "project_id", "simulation_id"]:
        c.drawString(72, y, f"{k}: {payload.get(k)}")
        y -= 16
    c.drawString(72, y, f"job_id: {job_id}")
    c.showPage()
    c.save()
    return pdf_path


def _run_report_inproc_background(
    job_id_str: str, payload: dict, units: str | None, pid: str | None, uid: str | None
):
    job_id = uuid.UUID(job_id_str)
    try:
        ret = task_generate_report(payload, job_id_str, units, pid, uid)
        found = _resolve_pdf(job_id, str(ret) if isinstance(ret, (str, Path)) else None)
        if found:
            _update_job(job_id, ReportStatus.succeeded, artifact=str(found))
        else:
            _update_job(
                job_id, ReportStatus.failed, error="PDF file was not found on disk."
            )
    except Exception as e:
        logger.exception("In-process report generation crashed.")
        _update_job(job_id, ReportStatus.failed, error=str(e))


def task_generate_report_rq(
    payload: dict, job_id_str: str, units: str | None, pid: str | None, uid: str | None
):
    job_id = uuid.UUID(job_id_str)
    _update_job(job_id, ReportStatus.running)
    try:
        ret = task_generate_report(payload, job_id_str, units, pid, uid)
        found = _resolve_pdf(job_id, str(ret) if isinstance(ret, (str, Path)) else None)
        if found:
            _update_job(job_id, ReportStatus.succeeded, artifact=str(found))
            return str(found)
        _update_job(
            job_id, ReportStatus.failed, error="PDF file was not found on disk."
        )
        return None
    except Exception as e:
        _update_job(job_id, ReportStatus.failed, error=str(e))
        raise


@router.post("/enqueue", response_model=EnqueueReportOut)
def enqueue_report(
    payload: EnqueueReportIn,
    background_tasks: BackgroundTasks,
    out_units: str | None = Query(default=None),
    project_id: str | None = Query(default=None),
    user_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    # 문자열 ID를 안전하게 UUID 객체로 변환하여 DB 조회
    scn_uuid = (
        payload.scenario_id
        if isinstance(payload.scenario_id, uuid.UUID)
        else uuid.UUID(str(payload.scenario_id))
    )
    scn = db.get(Scenario, scn_uuid)

    if not scn:
        raise HTTPException(404, "Scenario not found")

    in_dict = _parse_json(getattr(scn, "input_json", None), dict)
    if not in_dict:
        in_dict = {
            "project_id": getattr(scn, "project_id", "default"),
            "scenario_name": getattr(scn, "name", None)
            or getattr(scn, "scenario_name", "Untitled"),
            "feed": _parse_json(
                getattr(scn, "feed", None) or getattr(scn, "feed_json", None), dict
            ),
            "stages": _parse_json(
                getattr(scn, "stages", None) or getattr(scn, "stages_json", None), list
            ),
            "options": _parse_json(getattr(scn, "options", None), dict),
        }

    try:
        sim_req = SimulationRequest(**in_dict)
    except Exception as e:
        raise HTTPException(409, f"Invalid scenario data structure: {e}")

    task_payload = sim_req.model_dump()
    task_payload["scenario_id"] = str(scn.id)

    if os.getenv("AQUANOVA_SERVER_PDF_ENABLED", "0").lower() not in (
        "1",
        "true",
        "yes",
    ) and not _is_e2e_payload(task_payload):
        raise HTTPException(410, "Server-side PDF is disabled. Use client-side export.")

    job = ReportJob(scenario_id=scn.id, status=ReportStatus.queued, queue="inproc")
    if hasattr(job, "out_units"):
        setattr(job, "out_units", out_units)
    db.add(job)
    db.commit()
    db.refresh(job)

    if (
        _is_e2e_payload(task_payload)
        and os.getenv("AQUANOVA_E2E_FAST_REPORT", "1") != "0"
    ):
        try:
            _update_job(job.id, ReportStatus.running)
            pdf_path = _generate_fast_e2e_pdf(
                _get_out_dir() / f"{job.id}.pdf", job.id, task_payload
            )
            _update_job(job.id, ReportStatus.succeeded, artifact=str(pdf_path))
            return EnqueueReportOut(
                job_id=job.id, mode="inproc", debug_exec_mode="inproc"
            )
        except Exception as e:
            _update_job(job.id, ReportStatus.failed, error=str(e))
            raise

    use_rq = os.getenv("AQUANOVA_REPORTS_USE_RQ", "0").lower() in ("1", "true", "yes")
    force_inproc = _is_e2e_payload(task_payload) and os.getenv(
        "AQUANOVA_E2E_ALLOW_RQ", "0"
    ).lower() not in ("1", "true", "yes")

    if REDIS_AVAILABLE and use_rq and not force_inproc:
        try:
            r = redis.from_url(settings.REDIS_URL)
            if not r.ping():
                raise RuntimeError("Redis ping failed")
            if not any(
                QUEUE_NAME
                in (
                    w.queue_names()
                    if hasattr(w, "queue_names")
                    else [q.name for q in getattr(w, "queues", [])]
                )
                for w in Worker.all(connection=r)
            ):
                raise RuntimeError("No RQ worker listening")

            job.queue = f"rq:{QUEUE_NAME}"
            db.commit()
            Queue(QUEUE_NAME, connection=r).enqueue(
                task_generate_report_rq,
                task_payload,
                str(job.id),
                out_units,
                project_id,
                user_id,
                job_id=str(job.id),
                retry=Retry(max=3, interval=10),
                ttl=600,
                result_ttl=86400,
            )
            return EnqueueReportOut(job_id=job.id, mode="rq", debug_exec_mode="rq")
        except Exception as e:
            logger.warning(f"RQ fallback: {e}")

    _update_job(job.id, ReportStatus.running)
    background_tasks.add_task(
        _run_report_inproc_background,
        str(job.id),
        task_payload,
        out_units,
        project_id,
        user_id,
    )
    return EnqueueReportOut(job_id=job.id, mode="inproc", debug_exec_mode="inproc")


@router.get("/{job_id}", response_model=ReportStatusOut)
def get_report_status(job_id: uuid.UUID, db: Session = Depends(get_db)):
    job = db.get(ReportJob, job_id)
    if not job:
        raise HTTPException(404, "Report job not found")

    err = getattr(job, "error_message", None)

    # 스키마(ReportStatusOut)의 제약사항을 준수하기 위해 큐 문자열 검증 및 변환
    raw_queue = getattr(job, "queue", "unknown") or "unknown"
    mode = (
        "rq"
        if raw_queue.startswith("rq")
        else ("inproc" if raw_queue == "inproc" else "unknown")
    )

    if REDIS_AVAILABLE and job.status in (ReportStatus.queued, ReportStatus.running):
        try:
            r = redis.from_url(settings.REDIS_URL)
            if r.ping():
                rqj = RqJob.fetch(str(job_id), connection=r)
                if rqj and rqj.get_status() == "failed" and rqj.exc_info:
                    err = rqj.exc_info.splitlines()[-1][:500]
        except Exception:
            pass

    resolved = _resolve_pdf(job_id, getattr(job, "artifact_path", None))
    if resolved and getattr(job, "artifact_path", None) != str(resolved):
        try:
            job.artifact_path = str(resolved)
            db.commit()
        except Exception:
            db.rollback()

    return ReportStatusOut(
        job_id=job.id,
        status="started" if job.status.value == "running" else job.status.value,
        artifact_path=(
            str(resolved) if resolved else getattr(job, "artifact_path", None)
        ),
        artifact_exists=bool(resolved),
        error_message=err,
        enqueued_at=getattr(job, "enqueued_at", None),
        started_at=getattr(job, "started_at", None),
        finished_at=getattr(job, "finished_at", None),
        scenario_id=getattr(job, "scenario_id", None),
        out_units=getattr(job, "out_units", None),
        mode=mode,
        debug_exec_mode=mode,
    )


@router.get("/{job_id}/download")
def download_report(job_id: uuid.UUID, db: Session = Depends(get_db)):
    job = db.get(ReportJob, job_id)
    if not job:
        raise HTTPException(404, "Report job not found")

    if os.getenv("AQUANOVA_SERVER_PDF_ENABLED", "0").lower() not in (
        "1",
        "true",
        "yes",
    ) and not _is_e2e_job(db, job):
        raise HTTPException(410, "Server-side PDF download disabled.")

    if job.status == ReportStatus.failed:
        raise HTTPException(409, f"Failed: {job.error_message}")
    if job.status != ReportStatus.succeeded:
        raise HTTPException(409, f"Not ready: {job.status.value}")

    resolved = _resolve_pdf(job_id, getattr(job, "artifact_path", None))
    if not resolved:
        raise HTTPException(404, "PDF file not found on disk.")

    return FileResponse(
        path=str(resolved),
        media_type="application/pdf",
        filename=f"AquaNova_Report_{job_id}.pdf",
    )
