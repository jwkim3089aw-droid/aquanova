# app/db/models/report_job.py
from __future__ import annotations
from enum import Enum
from typing import Optional
from datetime import datetime
from uuid import UUID

from sqlalchemy import String, Integer, Text, ForeignKey, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base, UUIDMixin, TimestampMixin


class ReportStatus(str, Enum):
    # ✅ API 표준
    queued = "queued"
    started = "started"
    succeeded = "succeeded"
    failed = "failed"

    # ✅ DB 레거시 호환 (기존 running 값이 DB에 남아있을 수 있음)
    running = "running"


class ReportJob(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "report_job"

    scenario_id: Mapped[UUID] = mapped_column(
        ForeignKey("scenario.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[ReportStatus] = mapped_column(default=ReportStatus.queued)
    queue: Mapped[str] = mapped_column(String(40), default="reports")
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[Optional[str]] = mapped_column(Text())
    artifact_path: Mapped[Optional[str]] = mapped_column(String(500))
    enqueued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    scenario: Mapped["Scenario"] = relationship(back_populates="report_jobs")
