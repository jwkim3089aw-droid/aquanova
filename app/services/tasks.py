# app/services/tasks.py
from __future__ import annotations

import traceback
from pathlib import Path
from uuid import UUID
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from loguru import logger
from rq import get_current_job

# DB 관련 (Models는 순환 참조 위험이 적으므로 상단 유지)
from app.core.config import settings
from app.db.session import SessionLocal
from app.db.models.report_job import ReportJob, ReportStatus
from app.core.fs import ensure_dirs, report_output_path

# =========================================================
# Helper Functions (Dependencies minimized)
# =========================================================


def _derive_pdf_kpi(streams: list[dict], kpi: dict) -> dict:
    """PDF 표시용 KPI에 permeate/feed 유량을 보강"""
    kd = dict(kpi or {})
    try:
        if "permeate_m3h" not in kd:
            kd["permeate_m3h"] = sum(
                float(s.get("flow_m3h", 0.0))
                for s in (streams or [])
                if isinstance(s.get("label"), str) and "permeate" in s["label"].lower()
            )
    except Exception:
        pass
    try:
        if "feed_m3h" not in kd:
            feed = next(
                (
                    s
                    for s in (streams or [])
                    if str(s.get("label", "")).lower() == "feed"
                ),
                None,
            )
            if feed and feed.get("flow_m3h") is not None:
                kd["feed_m3h"] = float(feed["flow_m3h"])
    except Exception:
        pass
    return kd


def _get_user_conversions(project_id: str | None, user_id: str | None) -> Any:
    """DB에서 사용자/프로젝트별 단위 설정 로드 (Import 격리)"""
    # 여기서만 필요한 모듈 로드
    from app.services.units import Units, compute_conversions
    from app.db.models.user_settings import UserSettings

    db = SessionLocal()
    try:
        # 테이블 없으면 생성 시도 (안전장치)
        try:
            UserSettings.__table__.create(bind=db.bind, checkfirst=True)
        except Exception:
            pass

        query = db.query(UserSettings).filter(
            (
                (UserSettings.project_id == project_id)
                if project_id
                else UserSettings.project_id.is_(None)
            ),
            (
                (UserSettings.user_id == user_id)
                if user_id
                else UserSettings.user_id.is_(None)
            ),
        )
        row = query.first()

        if not row:
            # 없으면 기본값 생성
            row = UserSettings(project_id=project_id, user_id=user_id)
            db.add(row)
            db.commit()
            db.refresh(row)

        return compute_conversions(
            Units(
                row.units_flow,
                row.units_pressure,
                row.units_temperature,
                row.units_flux,
            )
        )
    except Exception as e:
        logger.warning(f"Failed to load user units: {e}")
        return compute_conversions(Units())  # 기본 SI 반환
    finally:
        db.close()


# =========================================================
# Main Task (Shared Task)
# =========================================================


def task_generate_report(
    payload: dict,
    job_id: str,
    out_units: str | None = None,  # 'display'면 표시단위로 렌더
    scope_project_id: str | None = None,
    scope_user_id: str | None = None,
    in_units: str | None = None,  # 입력이 display 단위면 "display"
) -> dict:
    """
    Celery/RQ 리포트 생성 태스크
    [중요] 순환 참조 방지를 위해 무거운 Import는 함수 내부에서 수행합니다.
    """

    # -----------------------------------------------------
    # 1. Lazy Imports (순환 참조 해결의 핵심)
    # -----------------------------------------------------
    try:
        from pydantic import ValidationError
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import A4

        # Templates
        from app.reports.templates.cover import draw_cover
        from app.reports.templates.summary import draw_system_summary
        from app.reports.templates.stage_metrics import draw_stage_metrics_page

        # Simulation Logic
        from app.api.v1.schemas import ScenarioInput
        from app.services.simulation.engine import run_l1_simulation

        # Unit Services
        from app.services.units import Units, compute_conversions
        from app.services.units_apply import apply_display_to_engine
        from app.services.units_apply_out import (
            to_display_streams,
            to_display_kpi,
            to_display_stage_metrics,
            unit_labels,
        )
    except ImportError as e:
        logger.critical(f"Import failed inside task: {e}")
        return {"status": "failed", "error": str(e)}

    # -----------------------------------------------------
    # 2. Job Initialization
    # -----------------------------------------------------
    job_uuid = UUID(str(job_id))
    logger.info(f"🚀 [JOB={job_uuid}] Starting Report Generation")
    ensure_dirs()

    # DB 상태 업데이트: Running
    db = SessionLocal()
    try:
        job = db.get(ReportJob, job_uuid)
        if job:
            job.status = ReportStatus.started  # ✅ running -> started
            job.started_at = datetime.now(timezone.utc)
            job.error_message = None
            db.add(job)
            db.commit()
        else:
            logger.warning(f"[JOB={job_uuid}] Not found in DB")
            return {"error": "Job not found"}
    finally:
        db.close()

    pdf_path = report_output_path(str(job_uuid))

    # -----------------------------------------------------
    # 3. Execution Logic
    # -----------------------------------------------------
    try:
        # A. 단위 변환 로직 (Display -> Engine)
        conv_for_scope = None
        is_display_in = (in_units or "").lower() == "display"
        is_display_out = (out_units or "").lower() == "display"

        if is_display_in or is_display_out:
            # 임시 파싱으로 프로젝트 ID 확인
            sim_preview = ScenarioInput(**payload)
            pid = scope_project_id or sim_preview.project_id
            conv_for_scope = _get_user_conversions(
                str(pid) if pid else None, scope_user_id
            )

        payload_engine = payload
        if is_display_in and conv_for_scope:
            payload_engine = apply_display_to_engine(payload, conv_for_scope)

        # B. 시뮬레이션 실행 (Engine)
        sim_in = ScenarioInput(**payload_engine)
        sim_out = run_l1_simulation(sim_in)

        # C. 결과 데이터 추출 (SI 기준)
        streams = [s.model_dump() for s in sim_out.streams]
        kpi = sim_out.kpi.model_dump()
        stage_metrics = [m.model_dump() for m in (sim_out.stage_metrics or [])]

        # D. 출력 단위 변환 (Engine -> Display)
        units_label_map = {
            "flow": "m3/h",
            "pressure": "bar",
            "flux": "LMH",
        }  # Default SI

        # 키 표준화 (snake_case)
        kpi = to_display_kpi(kpi, {})
        stage_metrics = to_display_stage_metrics(stage_metrics, {}) or []

        if is_display_out:
            conv = conv_for_scope or compute_conversions(Units())
            streams = to_display_streams(streams, conv)
            kpi = to_display_kpi(kpi, conv)
            stage_metrics = to_display_stage_metrics(stage_metrics, conv) or []
            units_label_map = unit_labels(conv)

        kpi_pdf = _derive_pdf_kpi(streams, kpi)

        # E. PDF 그리기 (ReportLab)
        c = canvas.Canvas(str(pdf_path), pagesize=A4)

        # 1) Cover
        draw_cover(c, scenario_name=sim_in.scenario_name)

        # 2) System Summary
        draw_system_summary(
            c,
            streams=streams,
            kpi=kpi_pdf,
            units=units_label_map,
            stage_metrics=stage_metrics,
        )

        # 3) Stage Metrics (Detail Pages)
        if stage_metrics:
            c.showPage()
            draw_stage_metrics_page(
                c, stage_metrics=stage_metrics, units=units_label_map
            )

        c.save()
        logger.info(f"✅ [JOB={job_uuid}] PDF Saved at {pdf_path}")

        # -------------------------------------------------
        # 4. Finalize (Success)
        # -------------------------------------------------
        db = SessionLocal()
        try:
            job = db.get(ReportJob, job_uuid)
            if job:
                try:
                    # 상대 경로로 저장
                    rel_path = pdf_path.relative_to(Path.cwd())
                except ValueError:
                    rel_path = pdf_path

                job.status = ReportStatus.succeeded
                job.artifact_path = rel_path.as_posix()
                job.finished_at = datetime.now(timezone.utc)
                db.add(job)
                db.commit()
        finally:
            db.close()

        return {"artifact_path": str(pdf_path)}

    except Exception as e:
        # -------------------------------------------------
        # 5. Error Handling
        # -------------------------------------------------
        logger.exception(f"❌ [JOB={job_uuid}] Failed: {e}")

        err_msg = str(e)
        if "ValidationError" in str(type(e)):
            err_msg = f"Validation Error: {e}"

        db = SessionLocal()
        try:
            job = db.get(ReportJob, job_uuid)
            if job:
                job.status = ReportStatus.failed
                job.error_message = err_msg[:500]
                job.finished_at = datetime.now(timezone.utc)
                db.add(job)
                db.commit()
        finally:
            db.close()

        # RQ Job Meta 업데이트
        try:
            rq_job = get_current_job()
            if rq_job:
                rq_job.meta["error_message"] = err_msg[:500]
                rq_job.save_meta()
        except Exception:
            pass

        raise e
