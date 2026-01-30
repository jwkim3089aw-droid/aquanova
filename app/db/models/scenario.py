# ./app/db/models/scenario.py

from __future__ import annotations
from typing import List
from uuid import UUID
from sqlalchemy import String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON
from .base import Base, UUIDMixin, TimestampMixin

class Scenario(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "scenario"

    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("project.id", ondelete="CASCADE"),
        index=True
    )
    name: Mapped[str] = mapped_column(String(120), index=True)
    input_json: Mapped[dict] = mapped_column(JSON, default=dict)

    project: Mapped["Project"] = relationship(back_populates="scenarios")
    report_jobs: Mapped[List["ReportJob"]] = relationship(
        back_populates="scenario",
        cascade="all, delete-orphan"
    )