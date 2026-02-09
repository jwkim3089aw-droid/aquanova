# app/db/models/scenario.py
from __future__ import annotations

from typing import List
from uuid import UUID

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from .base import Base, UUIDMixin, TimestampMixin


class Scenario(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "scenario"

    # NOTE:
    # - DB 컬럼이 UUID라면, 여기는 반드시 uuid.UUID 타입이 들어와야 함.
    # - API에서 project_id가 "e2e" 같은 문자열로 오더라도, 저장 직전에 UUID로 변환해서 넣도록 엔드포인트에서 처리.
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("project.id", ondelete="CASCADE"),
        index=True,
    )

    name: Mapped[str] = mapped_column(String(120), index=True)
    input_json: Mapped[dict] = mapped_column(JSON, default=dict)

    project: Mapped["Project"] = relationship(back_populates="scenarios")
    report_jobs: Mapped[List["ReportJob"]] = relationship(
        back_populates="scenario",
        cascade="all, delete-orphan",
    )
