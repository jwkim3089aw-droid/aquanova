# app\schemas\report.py
from uuid import UUID
from datetime import datetime
from typing import Optional, Union
from .common import AppBaseModel


class EnqueueReportIn(AppBaseModel):
    # ✅ 문자열도 허용하도록 수정된 버전
    scenario_id: Union[UUID, str]


class EnqueueReportOut(AppBaseModel):
    job_id: UUID


class ReportStatusOut(AppBaseModel):
    job_id: UUID
    status: str
    artifact_path: Optional[str] = None
    error_message: Optional[str] = None
    enqueued_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
