# app/services/tasks.py
from __future__ import annotations

import traceback
from pathlib import Path
from uuid import UUID
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from loguru import logger
from rq import get_current_job

from app.core.config import settings
from app.db.session import SessionLocal
from app.db.models.report_job import ReportJob, ReportStatus
from app.core.fs import ensure_dirs, report_output_path


def _derive_pdf_kpi(streams: list[dict], kpi: dict) -> dict:
    """PDF 표시용 KPI 데이터 보강 (유량 합산 등)"""
    kd = dict(kpi or {})
    try:
        if "permeate_m3h" not in kd:
            kd["permeate_m3h"] = sum(
                float(s.get("flow_m3h", 0.0))
                for s in (streams or [])
                if "permeate" in str(s.get("label", "")).lower()
            )

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
    except Exception as e:
        logger.debug(f"KPI derivation skipped: {e}")
    return kd


def _get_user_conversions(project_id: str | None, user_id: str | None) -> Any:
    """사용자/프로젝트별 단위 설정 로드 (순환 참조 방지용 내부 Import)"""
    from app.utils.units import Units, compute_conversions
    from app.db.models.user_settings import UserSettings

    with SessionLocal() as db:
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


def task_generate_report(
    payload: dict,
    job_id: str,
    out_units: str | None = None,
    scope_project_id: str | None = None,
    scope_user_id: str | None = None,
    in_units: str | None = None,
) -> dict:
    """리포트 생성 메인 태스크 (Celery/RQ)"""
    try:
        from pydantic import ValidationError
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import A4

        from app.reports.templates.cover import draw_cover
        from app.reports.templates.summary import draw_system_summary
        from app.reports.templates.stage_metrics import draw_stage_metrics_page

        from app.schemas.simulation import ScenarioInput
        from app.services.simulation.engine import SimulationEngine

        # 신규 모듈화된 units 패키지 Import 적용
        from app.utils.units import (
            Units,
            compute_conversions,
            apply_display_to_engine,
            to_display_streams,
            to_display_kpi,
            to_display_stage_metrics,
            unit_labels,
        )
    except ImportError as e:
        logger.error(f"Critical import failed: {e}")
        return {"status": "failed", "error": str(e)}

    job_uuid = UUID(str(job_id))
    logger.info(f"🚀 [JOB={job_uuid}] Starting report generation...")
    ensure_dirs()

    with SessionLocal() as db:
        job = db.get(ReportJob, job_uuid)
        if not job:
            return {"error": "Job not found"}
        job.status = ReportStatus.started
        job.started_at = datetime.now(timezone.utc)
        db.commit()

    pdf_path = report_output_path(str(job_uuid))

    try:
        is_display_in = (in_units or "").lower() == "display"
        is_display_out = (out_units or "").lower() == "display"
        conv_for_scope = None

        if is_display_in or is_display_out:
            sim_preview = ScenarioInput(**payload)
            pid = scope_project_id or sim_preview.project_id
            conv_for_scope = _get_user_conversions(
                str(pid) if pid else None, scope_user_id
            )

        payload_engine = payload
        if is_display_in and conv_for_scope:
            payload_engine = apply_display_to_engine(payload, conv_for_scope)

        sim_in = ScenarioInput(**payload_engine)
        engine = SimulationEngine()
        sim_out = engine.run(sim_in)

        streams = [s.model_dump() for s in sim_out.streams]
        kpi = sim_out.kpi.model_dump()
        stage_metrics = [m.model_dump() for m in (sim_out.stage_metrics or [])]

        units_label_map = {"flow": "m3/h", "pressure": "bar", "flux": "LMH"}

        if is_display_out:
            conv = conv_for_scope or compute_conversions(Units())
            streams = to_display_streams(streams, conv)
            kpi = to_display_kpi(kpi, conv)
            stage_metrics = to_display_stage_metrics(stage_metrics, conv) or []
            units_label_map = unit_labels(conv)
        else:
            kpi = to_display_kpi(kpi, {})
            stage_metrics = to_display_stage_metrics(stage_metrics, {}) or []

        kpi_pdf = _derive_pdf_kpi(streams, kpi)

        c = canvas.Canvas(str(pdf_path), pagesize=A4)
        draw_cover(c, scenario_name=sim_in.scenario_name)
        draw_system_summary(
            c,
            streams=streams,
            kpi=kpi_pdf,
            units=units_label_map,
            stage_metrics=stage_metrics,
        )

        if stage_metrics:
            c.showPage()
            draw_stage_metrics_page(
                c, stage_metrics=stage_metrics, units=units_label_map
            )

        c.save()

        with SessionLocal() as db:
            job = db.get(ReportJob, job_uuid)
            if job:
                try:
                    rel_path = pdf_path.relative_to(Path.cwd())
                except ValueError:
                    rel_path = pdf_path
                job.status = ReportStatus.succeeded
                job.artifact_path = rel_path.as_posix()
                job.finished_at = datetime.now(timezone.utc)
                db.commit()

        return {"artifact_path": str(pdf_path)}

    except Exception as e:
        logger.exception(f"❌ [JOB={job_uuid}] Failed: {e}")
        err_msg = (
            f"Validation Error: {e}" if "ValidationError" in str(type(e)) else str(e)
        )

        with SessionLocal() as db:
            job = db.get(ReportJob, job_uuid)
            if job:
                job.status = ReportStatus.failed
                job.error_message = err_msg[:500]
                job.finished_at = datetime.now(timezone.utc)
                db.commit()

        try:
            rq_job = get_current_job()
            if rq_job:
                rq_job.meta["error_message"] = err_msg[:500]
                rq_job.save_meta()
        except:
            pass

        raise e
