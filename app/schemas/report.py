# app/schemas/report.py
from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional, Union
from uuid import UUID

from pydantic import Field, model_validator

from .common import AppBaseModel

# ✅ API 표준(=UI 상태)로 고정
ReportStatusUI = Literal["queued", "started", "succeeded", "failed"]

# ✅ 실행 경로 (운영/테스트 공용 표준)
ReportExecMode = Literal["rq", "inproc", "unknown"]

# ✅ out_units 표준(현재 API에서 사용)
ReportOutUnits = Literal["display", "metric"]


class EnqueueReportIn(AppBaseModel):
    """
    리포트 생성 요청 입력
    - scenario_id: UUID 권장 (문자열 UUID도 허용)
    """

    scenario_id: Union[UUID, str] = Field(
        ...,
        description="Scenario UUID (UUID or UUID string)",
        examples=["728562b2-04f8-4dc8-9b3e-4519e416646b"],
    )


class EnqueueReportOut(AppBaseModel):
    """
    리포트 생성 요청 응답
    - mode: 실행 경로 표준 필드
    - debug_exec_mode: 하위호환(legacy) 필드 (mode와 항상 동일)
    """

    job_id: UUID = Field(..., description="Report job UUID")

    # ✅ 표준
    mode: Optional[ReportExecMode] = Field(
        default=None,
        description='Execution mode: "rq" | "inproc" | "unknown"',
    )

    # ✅ legacy 호환
    debug_exec_mode: Optional[ReportExecMode] = Field(
        default=None,
        description='(legacy) Same as mode: "rq" | "inproc" | "unknown"',
    )

    @model_validator(mode="after")
    def _sync_modes(self):
        if self.mode is None and self.debug_exec_mode is not None:
            self.mode = self.debug_exec_mode
        if self.debug_exec_mode is None and self.mode is not None:
            self.debug_exec_mode = self.mode
        return self


class ReportStatusOut(AppBaseModel):
    """
    리포트 상태 조회 응답
    """

    job_id: UUID = Field(..., description="Report job UUID")
    status: ReportStatusUI = Field(
        ..., description="queued | started | succeeded | failed"
    )

    artifact_path: Optional[str] = Field(
        default=None, description="PDF path on server disk"
    )
    artifact_exists: Optional[bool] = Field(
        default=None, description="Whether PDF exists on disk"
    )
    error_message: Optional[str] = Field(
        default=None, description="Failure message (if any)"
    )

    enqueued_at: Optional[datetime] = Field(default=None)
    started_at: Optional[datetime] = Field(default=None)
    finished_at: Optional[datetime] = Field(default=None)

    # ✅ 디버그/추적용(있어도 되고 없어도 됨)
    scenario_id: Optional[UUID] = Field(default=None)
    out_units: Optional[ReportOutUnits] = Field(default=None)

    # ✅ 표준
    mode: Optional[ReportExecMode] = Field(
        default=None,
        description='Execution mode: "rq" | "inproc" | "unknown"',
    )

    # ✅ legacy 호환
    debug_exec_mode: Optional[ReportExecMode] = Field(
        default=None,
        description='(legacy) Same as mode: "rq" | "inproc" | "unknown"',
    )

    @model_validator(mode="after")
    def _sync_modes(self):
        if self.mode is None and self.debug_exec_mode is not None:
            self.mode = self.debug_exec_mode
        if self.debug_exec_mode is None and self.mode is not None:
            self.debug_exec_mode = self.mode
        return self
