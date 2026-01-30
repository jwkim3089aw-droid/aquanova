# ./app/db/models/project.py

from __future__ import annotations
from typing import Optional, List

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base, UUIDMixin, TimestampMixin

class Project(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "project"

    name: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text())

    scenarios: Mapped[List["Scenario"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan"
    )
