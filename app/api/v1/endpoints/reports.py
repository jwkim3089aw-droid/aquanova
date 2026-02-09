# app/api/v1/endpoints/reports.py
from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

# Redis/RQ (optional)
try:
    import redis
    from rq import Queue, Retry, Worker, job as rq_job

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
logger = logging.getLogger(__name__)

QUEUE_NAME = "reports"


# -----------------------------------------------------------------------------
# JSON normalize helpers
# -----------------------------------------------------------------------------
def _ensure_dict(v: Any) -> Optional[Dict[str, Any]]:
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


def _ensure_list(v: Any) -> Optional[List[Any]]:
    if v is None:
        return None
    if isinstance(v, list):
        return v
    if isinstance(v, str):
        try:
            parsed = json.loads(v)
            if isinstance(parsed, list):
                return parsed
        except (json.JSONDecodeError, TypeError):
            pass
    return None


# -----------------------------------------------------------------------------
# Status mapping
# -----------------------------------------------------------------------------
def _api_status(db_status: ReportStatus) -> str:
    """
    DB: queued | running | succeeded | failed
    API/UI: queued | started | succeeded | failed
    """
    s = db_status.value if isinstance(db_status, ReportStatus) else str(db_status)
    return "started" if s == "running" else s


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


# -----------------------------------------------------------------------------
# Path base helpers
# -----------------------------------------------------------------------------
def _code_root() -> Path:
    """
    .../code/app/api/v1/endpoints/reports.py 기준으로 code 루트를 계산.
    Windows 서비스(nssm)에서 CWD가 흔들려도 안전하게 파일 경로를 잡기 위해 사용.
    """
    try:
        return Path(__file__).resolve().parents[4]  # .../code
    except Exception:
        return Path.cwd()


def _reports_output_dir() -> Path:
    d = _code_root() / "reports" / "outputs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _try_unmojibake_path(p: str) -> Optional[str]:
    """
    Windows 한글 경로가 UTF-8 bytes를 latin1로 잘못 해석해
    '프로젝트' -> 'íë¡ì ...' 같은 모지바케로 저장된 경우 복구 시도.
    """
    if not p:
        return None
    try:
        fixed = p.encode("latin1").decode("utf-8")
        return fixed
    except Exception:
        return None


def _resolve_pdf_path(
    job_id: uuid.UUID, artifact_path: Optional[str]
) -> Optional[Path]:
    """
    PDF 존재 경로를 최대한 robust하게 찾아낸다.

    우선순위:
      1) DB artifact_path (절대/상대 모두 지원)
      2) artifact_path 모지바케 복구본
      3) app.core.fs.find_report_pdf(job_id)
      4) <code_root>/reports/outputs/<job_id>.pdf
      5) outputs 폴더 glob(<job_id>*.pdf)
    """
    out_dir = _reports_output_dir()
    candidates: List[Path] = []

    def _as_path(s: str) -> Path:
        p = Path(s)
        return p if p.is_absolute() else (_code_root() / p)

    if artifact_path:
        try:
            candidates.append(_as_path(artifact_path))
        except Exception:
            pass

        fixed = _try_unmojibake_path(artifact_path)
        if fixed and fixed != artifact_path:
            try:
                candidates.append(_as_path(fixed))
            except Exception:
                pass

    alt = find_report_pdf(str(job_id))
    if alt:
        try:
            candidates.append(alt if alt.is_absolute() else (_code_root() / alt))
        except Exception:
            pass

    candidates.append(out_dir / f"{job_id}.pdf")
    candidates.extend(out_dir.glob(f"{job_id}*.pdf"))

    for p in candidates:
        try:
            if p.exists() and p.is_file():
                return p.resolve()
        except Exception:
            continue

    return None


def _coerce_store_path(p: Path) -> str:
    """
    DB에는 절대경로로 저장(서비스/워커에서 CWD 흔들려도 안전).
    """
    try:
        return str(p.resolve())
    except Exception:
        return str(p)


# -----------------------------------------------------------------------------
# ✅ Server-side PDF gate (default OFF)
# -----------------------------------------------------------------------------
def _server_pdf_enabled() -> bool:
    """
    서버 PDF(ReportLab/RQ/inproc) 플로우를 기본적으로 비활성.
    UI Detailed Report + client export 전환 이후, 실수로 백엔드 엔드포인트를 호출해도
    명확히 차단하기 위한 가드.
    """
    return os.getenv("AQUANOVA_SERVER_PDF_ENABLED", "0").strip().lower() in (
        "1",
        "true",
        "yes",
    )


def _is_e2e_job(db: Session, job_row: ReportJob) -> bool:
    """
    download 같은 곳에서 '이 job이 e2e인지' 판정.
    Scenario.input_json 안에 project_id / simulation_id가 남아있는 경우를 우선 신뢰.
    """
    try:
        scenario_id = getattr(job_row, "scenario_id", None)
        if not scenario_id:
            return False

        scn = db.get(Scenario, scenario_id)
        if not scn:
            return False

        raw = getattr(scn, "input_json", None)
        d = _ensure_dict(raw) or {}

        pid = str(d.get("project_id") or "").strip().lower()
        sim_id = str(d.get("simulation_id") or "").strip().lower()

        return pid == "e2e" or sim_id.startswith("e2e-")
    except Exception:
        return False


# -----------------------------------------------------------------------------
# E2E helpers
# -----------------------------------------------------------------------------
def _is_e2e_payload(task_payload: Dict[str, Any]) -> bool:
    pid = str(task_payload.get("project_id") or "").strip().lower()
    sim_id = str(task_payload.get("simulation_id") or "").strip().lower()
    return pid == "e2e" or sim_id.startswith("e2e-")


def _write_minimal_pdf(
    pdf_path: Path, job_id: uuid.UUID, task_payload: Dict[str, Any]
) -> None:
    """
    E2E용 '초경량' PDF
    """
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    pdf_path.parent.mkdir(parents=True, exist_ok=True)

    c = canvas.Canvas(str(pdf_path), pagesize=A4)
    _, h = A4

    y = h - 72
    c.setFont("Helvetica-Bold", 16)
    c.drawString(72, y, "AquaNova Report (E2E Fast)")
    y -= 28

    c.setFont("Helvetica", 11)
    c.drawString(72, y, f"job_id     : {job_id}")
    y -= 16
    c.drawString(72, y, f"scenario_id: {task_payload.get('scenario_id')}")
    y -= 16
    c.drawString(72, y, f"project_id : {task_payload.get('project_id')}")
    y -= 16
    c.drawString(72, y, f"simulation : {task_payload.get('simulation_id')}")
    y -= 24

    c.setFont("Helvetica-Oblique", 10)
    c.drawString(72, y, "This PDF was generated by the in-process E2E fast path.")
    c.showPage()
    c.save()


# -----------------------------------------------------------------------------
# DB session helpers for background/RQ finalize (✅ SessionLocal 없으면 engine으로 생성)
# -----------------------------------------------------------------------------
def _get_session_local():
    """
    우선: app.db.session.SessionLocal
    없으면: app.db.session.engine 기반 sessionmaker로 fallback
    """
    try:
        from app.db.session import SessionLocal  # type: ignore

        return SessionLocal
    except Exception:
        from sqlalchemy.orm import sessionmaker

        try:
            from app.db.session import engine  # type: ignore

            return sessionmaker(
                bind=engine, autoflush=False, autocommit=False, future=True
            )
        except Exception as e:
            raise RuntimeError(
                "Cannot create DB session for report background task"
            ) from e


def _finalize_job(
    job_id: uuid.UUID,
    *,
    status: ReportStatus,
    artifact_path: Optional[str] = None,
    error_message: Optional[str] = None,
) -> None:
    """
    job 상태를 최종(succeeded/failed)로 확정.
    - 이미 최종 상태면 덮어쓰지 않음
    """
    SessionLocal = _get_session_local()
    db = SessionLocal()
    try:
        job_row = db.get(ReportJob, job_id)
        if not job_row:
            return

        if job_row.status in (ReportStatus.succeeded, ReportStatus.failed):
            return

        job_row.status = status

        if status == ReportStatus.succeeded:
            if artifact_path:
                job_row.artifact_path = artifact_path
        else:
            if error_message:
                job_row.error_message = str(error_message)[:500]

        job_row.finished_at = _now_utc()
        db.commit()
    finally:
        db.close()


def _mark_running(job_uuid: uuid.UUID) -> None:
    SessionLocal = _get_session_local()
    db = SessionLocal()
    try:
        job_row = db.get(ReportJob, job_uuid)
        if not job_row:
            return
        if job_row.status in (ReportStatus.succeeded, ReportStatus.failed):
            return
        job_row.status = ReportStatus.running
        job_row.started_at = _now_utc()
        db.commit()
    finally:
        db.close()


# -----------------------------------------------------------------------------
# Exec mode inference
# -----------------------------------------------------------------------------
def _infer_exec_mode_from_queue(job_row: ReportJob) -> str:
    q = str(getattr(job_row, "queue", "") or "").strip().lower()
    if q.startswith("rq:"):
        return "rq"
    if q == "inproc":
        return "inproc"
    return "unknown"


def _infer_exec_mode_with_redis_fallback(job_row: ReportJob) -> str:
    base = _infer_exec_mode_from_queue(job_row)
    if base != "unknown":
        return base

    if not REDIS_AVAILABLE:
        return base

    try:
        r = redis.from_url(settings.REDIS_URL)
        if not r.ping():
            return base
        rqj = rq_job.Job.fetch(str(job_row.id), connection=r)  # type: ignore
        if rqj is not None:
            return "rq"
    except Exception:
        pass

    return base


# -----------------------------------------------------------------------------
# RQ selection gates
# -----------------------------------------------------------------------------
def _use_rq() -> bool:
    return os.getenv("AQUANOVA_REPORTS_USE_RQ", "0").strip().lower() in (
        "1",
        "true",
        "yes",
    )


def _rq_has_worker_for_queue(r, queue_name: str) -> bool:
    if not REDIS_AVAILABLE:
        return False
    try:
        workers = Worker.all(connection=r)  # type: ignore
        for w in workers:
            try:
                if hasattr(w, "queue_names"):
                    qnames = list(w.queue_names())  # type: ignore
                else:
                    qnames = [q.name for q in getattr(w, "queues", [])]
                if queue_name in qnames:
                    return True
            except Exception:
                continue
        return False
    except Exception:
        return False


# -----------------------------------------------------------------------------
# Common "find pdf after generation"
# -----------------------------------------------------------------------------
def _find_pdf_after_generation(ret: Any, job_id: uuid.UUID) -> Optional[Path]:
    job_id_str = str(job_id)
    candidates: List[Path] = []

    if isinstance(ret, (str, Path)):
        try:
            p = Path(ret)
            candidates.append(p if p.is_absolute() else (_code_root() / p))
        except Exception:
            pass

    alt = find_report_pdf(job_id_str)
    if alt:
        try:
            candidates.append(alt if alt.is_absolute() else (_code_root() / alt))
        except Exception:
            pass

    out_dir = _reports_output_dir()
    candidates.append(out_dir / f"{job_id_str}.pdf")
    candidates.extend(out_dir.glob(f"{job_id_str}*.pdf"))

    for p in candidates:
        try:
            if p.exists() and p.is_file():
                return p.resolve()
        except Exception:
            continue

    return None


# -----------------------------------------------------------------------------
# RQ wrapper
# -----------------------------------------------------------------------------
def task_generate_report_rq(
    task_payload: Dict[str, Any],
    job_id_str: str,
    out_units: Optional[str],
    project_id: Optional[str],
    user_id: Optional[str],
) -> Optional[str]:
    job_uuid = uuid.UUID(job_id_str)
    _mark_running(job_uuid)

    try:
        if (
            _is_e2e_payload(task_payload)
            and os.getenv("AQUANOVA_E2E_FAST_REPORT", "1") != "0"
        ):
            pdf_path = _reports_output_dir() / f"{job_uuid}.pdf"
            _write_minimal_pdf(pdf_path, job_uuid, task_payload)
            _finalize_job(
                job_uuid,
                status=ReportStatus.succeeded,
                artifact_path=_coerce_store_path(pdf_path),
            )
            return _coerce_store_path(pdf_path)

        ret = task_generate_report(
            task_payload, job_id_str, out_units, project_id, user_id
        )
        found = _find_pdf_after_generation(ret, job_uuid)
        if found:
            _finalize_job(
                job_uuid,
                status=ReportStatus.succeeded,
                artifact_path=_coerce_store_path(found),
            )
            return _coerce_store_path(found)

        _finalize_job(
            job_uuid,
            status=ReportStatus.failed,
            error_message="Report generation finished but PDF file was not found on disk.",
        )
        return None

    except Exception as e:
        _finalize_job(job_uuid, status=ReportStatus.failed, error_message=str(e))
        raise


# -----------------------------------------------------------------------------
# In-proc background runner
# -----------------------------------------------------------------------------
def _run_report_inproc_background(
    job_id_str: str,
    task_payload: Dict[str, Any],
    out_units: Optional[str],
    project_id: Optional[str],
    user_id: Optional[str],
) -> None:
    try:
        job_uuid = uuid.UUID(job_id_str)

        if (
            _is_e2e_payload(task_payload)
            and os.getenv("AQUANOVA_E2E_FAST_REPORT", "1") != "0"
        ):
            pdf_path = _reports_output_dir() / f"{job_uuid}.pdf"
            _write_minimal_pdf(pdf_path, job_uuid, task_payload)
            _finalize_job(
                job_uuid,
                status=ReportStatus.succeeded,
                artifact_path=_coerce_store_path(pdf_path),
            )
            return

        ret = task_generate_report(
            task_payload, job_id_str, out_units, project_id, user_id
        )
        found = _find_pdf_after_generation(ret, job_uuid)
        if found:
            _finalize_job(
                job_uuid,
                status=ReportStatus.succeeded,
                artifact_path=_coerce_store_path(found),
            )
        else:
            _finalize_job(
                job_uuid,
                status=ReportStatus.failed,
                error_message="Report generation finished but PDF file was not found on disk.",
            )

    except Exception as e:
        try:
            _finalize_job(
                uuid.UUID(job_id_str), status=ReportStatus.failed, error_message=str(e)
            )
        except Exception:
            logger.exception("Failed to finalize report job after exception.")
        logger.exception("Report generation crashed.")


# -----------------------------------------------------------------------------
# Endpoint: POST /reports/enqueue
# -----------------------------------------------------------------------------
@router.post("/enqueue", response_model=EnqueueReportOut)
def enqueue_report(
    payload: EnqueueReportIn,
    background_tasks: BackgroundTasks,
    out_units: Optional[str] = Query(default=None),
    project_id: Optional[str] = Query(default=None),
    user_id: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
):
    """
    기본: inproc background
    ✅ E2E fast path는 요청 안에서 즉시 생성 + succeeded 확정(=started에 걸리는 문제 제거)

    ✅ 서버 PDF(ReportLab/RQ/inproc) 플로우는 기본 비활성.
       UI Detailed Report + client PDF export를 기본 경로로 사용.
    """

    # 0) scenario_id UUID
    try:
        scenario_uuid = payload.scenario_id
        if not isinstance(scenario_uuid, uuid.UUID):
            scenario_uuid = uuid.UUID(str(scenario_uuid))
    except Exception:
        raise HTTPException(
            status_code=422, detail="Invalid scenario_id (must be UUID)."
        )

    # 1) scenario fetch
    scn = db.get(Scenario, scenario_uuid)
    if not scn:
        raise HTTPException(
            status_code=404, detail=f"Scenario not found: {scenario_uuid}"
        )

    scenario_id_str = str(getattr(scn, "id"))

    # 2) input_json normalize -> SimulationRequest
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
            "stages": _ensure_list(
                getattr(scn, "stages", None) or getattr(scn, "stages_json", None)
            )
            or [],
            "options": _ensure_dict(getattr(scn, "options", None)) or {},
        }

    try:
        sim_req = SimulationRequest(**in_dict)
    except Exception as e:
        raise HTTPException(
            status_code=409, detail=f"Invalid scenario data structure: {str(e)}"
        )

    task_payload = sim_req.model_dump()
    task_payload["scenario_id"] = scenario_id_str

    # ✅ Server PDF flow is disabled by default (except E2E)
    if (not _server_pdf_enabled()) and (not _is_e2e_payload(task_payload)):
        raise HTTPException(
            status_code=410,
            detail=(
                "Server-side PDF report generation is disabled. "
                "Use UI 'Detailed Report' and client-side PDF export."
            ),
        )

    # 3) create job (queued)
    job_row = ReportJob(
        scenario_id=scn.id,
        status=ReportStatus.queued,
        queue="inproc",
    )
    db.add(job_row)
    db.commit()
    db.refresh(job_row)

    # ✅ 디버깅/추적용 컬럼이 있으면 기록(없어도 안전)
    if hasattr(job_row, "out_units"):
        try:
            setattr(job_row, "out_units", out_units)
        except Exception:
            pass
    db.commit()

    # ✅ E2E fast path: "즉시" PDF 생성 + succeeded 확정
    if (
        _is_e2e_payload(task_payload)
        and os.getenv("AQUANOVA_E2E_FAST_REPORT", "1") != "0"
    ):
        try:
            job_row.status = ReportStatus.running
            job_row.started_at = _now_utc()
            db.commit()

            pdf_path = _reports_output_dir() / f"{job_row.id}.pdf"
            _write_minimal_pdf(pdf_path, job_row.id, task_payload)

            job_row.status = ReportStatus.succeeded
            job_row.artifact_path = _coerce_store_path(pdf_path)
            job_row.finished_at = _now_utc()
            db.commit()

            return EnqueueReportOut(
                job_id=job_row.id, mode="inproc", debug_exec_mode="inproc"
            )
        except Exception as e:
            job_row.status = ReportStatus.failed
            job_row.error_message = (
                str(e)[:500] if hasattr(job_row, "error_message") else None
            )
            job_row.finished_at = _now_utc()
            db.commit()
            raise

    # 4) (옵션) RQ 경로
    force_inproc = _is_e2e_payload(task_payload) and os.getenv(
        "AQUANOVA_E2E_ALLOW_RQ", "0"
    ).strip().lower() not in (
        "1",
        "true",
        "yes",
    )

    if REDIS_AVAILABLE and _use_rq() and not force_inproc:
        try:
            r = redis.from_url(settings.REDIS_URL)
            if not r.ping():
                raise RuntimeError("Redis ping failed")

            if not _rq_has_worker_for_queue(r, QUEUE_NAME):
                raise RuntimeError(f"No RQ worker listening to '{QUEUE_NAME}' queue")

            job_row.queue = f"rq:{QUEUE_NAME}"
            db.commit()

            q = Queue(QUEUE_NAME, connection=r)
            q.enqueue(
                task_generate_report_rq,
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

            return EnqueueReportOut(job_id=job_row.id, mode="rq", debug_exec_mode="rq")

        except Exception as e:
            logger.warning(
                f"Redis/RQ not usable ({e}). Falling back to in-process background execution."
            )

    # ---- In-process background path ----
    job_row.queue = "inproc"
    job_row.status = ReportStatus.running
    job_row.started_at = _now_utc()
    db.commit()

    background_tasks.add_task(
        _run_report_inproc_background,
        str(job_row.id),
        task_payload,
        out_units,
        project_id,
        user_id,
    )

    return EnqueueReportOut(job_id=job_row.id, mode="inproc", debug_exec_mode="inproc")


# -----------------------------------------------------------------------------
# Endpoint: GET /reports/{job_id}
# -----------------------------------------------------------------------------
@router.get("/{job_id}", response_model=ReportStatusOut)
def get_report_status(job_id: uuid.UUID, db: Session = Depends(get_db)):
    job_row = db.get(ReportJob, job_id)
    if not job_row:
        raise HTTPException(status_code=404, detail="Report job not found")

    error_message = getattr(job_row, "error_message", None)

    mode = _infer_exec_mode_with_redis_fallback(job_row)

    # RQ failed -> error_message 보강
    if REDIS_AVAILABLE and job_row.status in (
        ReportStatus.queued,
        ReportStatus.running,
    ):
        try:
            r = redis.from_url(settings.REDIS_URL)
            if r.ping():
                rqj = rq_job.Job.fetch(str(job_id), connection=r)  # type: ignore
                if rqj and rqj.get_status() == "failed":
                    if rqj.exc_info:
                        error_message = rqj.exc_info.splitlines()[-1][:500]
        except Exception:
            pass

    resolved = _resolve_pdf_path(job_id, getattr(job_row, "artifact_path", None))
    if resolved is not None:
        correct = _coerce_store_path(resolved)
        if getattr(job_row, "artifact_path", None) != correct:
            try:
                job_row.artifact_path = correct
                db.add(job_row)
                db.commit()
                db.refresh(job_row)
            except Exception:
                db.rollback()

    artifact_exists = bool(resolved and resolved.exists())

    return ReportStatusOut(
        job_id=job_row.id,
        status=_api_status(job_row.status),
        artifact_path=(
            str(resolved) if resolved else getattr(job_row, "artifact_path", None)
        ),
        artifact_exists=artifact_exists,
        error_message=error_message,
        enqueued_at=getattr(job_row, "enqueued_at", None),
        started_at=getattr(job_row, "started_at", None),
        finished_at=getattr(job_row, "finished_at", None),
        scenario_id=getattr(job_row, "scenario_id", None),
        out_units=getattr(job_row, "out_units", None),
        mode=mode,
        debug_exec_mode=mode,
    )


# -----------------------------------------------------------------------------
# Endpoint: GET /reports/{job_id}/download
# -----------------------------------------------------------------------------
@router.get("/{job_id}/download")
def download_report(job_id: uuid.UUID, db: Session = Depends(get_db)):
    job_row = db.get(ReportJob, job_id)
    if not job_row:
        raise HTTPException(status_code=404, detail="Report job not found")

    # ✅ Server PDF download is disabled by default (except E2E)
    if (not _server_pdf_enabled()) and (not _is_e2e_job(db, job_row)):
        raise HTTPException(
            status_code=410,
            detail=(
                "Server-side PDF download is disabled. "
                "Use UI 'Detailed Report' and client-side PDF export."
            ),
        )

    if job_row.status == ReportStatus.failed:
        raise HTTPException(
            status_code=409, detail=f"Report generation failed: {job_row.error_message}"
        )

    if job_row.status != ReportStatus.succeeded:
        raise HTTPException(
            status_code=409,
            detail=f"Report is not ready. Status: {_api_status(job_row.status)}",
        )

    resolved = _resolve_pdf_path(job_id, getattr(job_row, "artifact_path", None))
    if resolved is None:
        raise HTTPException(
            status_code=404,
            detail="Report generation finished but PDF file was not found on disk.",
        )

    correct = _coerce_store_path(resolved)
    if getattr(job_row, "artifact_path", None) != correct:
        try:
            job_row.artifact_path = correct
            db.add(job_row)
            db.commit()
        except Exception:
            db.rollback()

    return FileResponse(
        path=correct,
        media_type="application/pdf",
        filename=f"AquaNova_Report_{job_id}.pdf",
    )
