from __future__ import annotations
from datetime import datetime
from uuid import uuid4
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, DateTime, UniqueConstraint
from sqlalchemy.sql import func
from .base import Base

class UserSettings(Base):
    __tablename__ = "user_settings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))

    # 스코프(둘 다 None이면 글로벌 1행)
    project_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    user_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    units_flow: Mapped[str] = mapped_column(String(16), default="m3/h")
    units_pressure: Mapped[str] = mapped_column(String(16), default="bar")
    units_temperature: Mapped[str] = mapped_column(String(16), default="C")
    units_flux: Mapped[str] = mapped_column(String(16), default="LMH")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("project_id", "user_id", name="uq_user_settings_scope"),
    )
