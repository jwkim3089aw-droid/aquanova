# ./app/api/v1/user_settings.py

from __future__ import annotations
from datetime import datetime
from typing import Optional, Tuple
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import inspect  # [ADDED]
from app.db.session import get_db, engine
from app.db.models.user_settings import UserSettings
from ..schemas import UnitsSettingsIn, UnitsSettingsOut
from app.services.units import Units, compute_conversions

router = APIRouter(prefix="/user-settings", tags=["user-settings"])

# [ADDED] 안전 기본 단위(누락 시 자동 보정)
DEFAULT_UNITS = {
    "flow": "m3/h",
    "pressure": "bar",
    "temperature": "C",
    "flux": "LMH",
}


def _ensure_table():
    # 테이블 없으면 생성
    try:
        UserSettings.__table__.create(bind=engine, checkfirst=True)
    except Exception:
        pass


def _migrate_columns():
    """
    [CHANGED]
    - 우선 SQLAlchemy Inspector로 존재 여부 확인(비 SQLite 호환).
    - SQLite면 기존 PRAGMA 경로로 폴백.
    """
    try:
        if engine.dialect.name != "sqlite":  # [ADDED]
            insp = inspect(engine)
            cols = {c["name"] for c in insp.get_columns("user_settings")}
        else:
            with engine.connect() as conn:
                cols = {
                    row[1]
                    for row in conn.exec_driver_sql(
                        "PRAGMA table_info(user_settings)"
                    ).fetchall()
                }

        with engine.begin() as conn:
            if "project_id" not in cols:
                conn.exec_driver_sql(
                    "ALTER TABLE user_settings ADD COLUMN project_id VARCHAR(36)"
                )
            if "user_id" not in cols:
                conn.exec_driver_sql(
                    "ALTER TABLE user_settings ADD COLUMN user_id VARCHAR(64)"
                )
            # 유니크 인덱스(있으면 무시)
            conn.exec_driver_sql(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_user_settings_scope ON user_settings(project_id, user_id)"
            )
    except Exception:
        # 스키마 변경 실패해도 애플리케이션 동작은 지속
        pass


def _get_scoped(
    db: Session, project_id: Optional[str], user_id: Optional[str]
) -> UserSettings:
    _ensure_table()
    _migrate_columns()
    q = db.query(UserSettings).filter(
        (
            (UserSettings.project_id == project_id)
            if project_id
            else (UserSettings.project_id.is_(None))
        ),
        (
            (UserSettings.user_id == user_id)
            if user_id
            else (UserSettings.user_id.is_(None))
        ),
    )
    row = q.first()
    if not row:
        row = UserSettings(project_id=project_id, user_id=user_id)
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


def _iso(v):
    return v.isoformat() if isinstance(v, datetime) else None


# [ADDED] 현재 row + 기본값으로 안전한 단위 튜플 반환
def _units_with_defaults(row: UserSettings) -> Tuple[str, str, str, str]:
    flow = row.units_flow or DEFAULT_UNITS["flow"]
    pressure = row.units_pressure or DEFAULT_UNITS["pressure"]
    temperature = row.units_temperature or DEFAULT_UNITS["temperature"]
    flux = row.units_flux or DEFAULT_UNITS["flux"]
    return flow, pressure, temperature, flux


# [ADDED] 페이로드 병합(부분 업데이트)
def _merge_payload(
    row: UserSettings, payload: UnitsSettingsIn
) -> Tuple[str, str, str, str]:
    cur_flow, cur_pressure, cur_temp, cur_flux = _units_with_defaults(row)
    new_flow = payload.flow if payload.flow is not None else cur_flow
    new_pressure = payload.pressure if payload.pressure is not None else cur_pressure
    new_temp = payload.temperature if payload.temperature is not None else cur_temp
    new_flux = payload.flux if payload.flux is not None else cur_flux
    return new_flow, new_pressure, new_temp, new_flux


@router.get("/units", response_model=UnitsSettingsOut)
def get_units(
    project_id: str | None = Query(default=None),
    user_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    try:
        row = _get_scoped(db, project_id, user_id)
        flow, pressure, temperature, flux = _units_with_defaults(row)  # [CHANGED]
        try:
            u = Units(flow, pressure, temperature, flux)  # 유효성 검증
        except Exception as e:
            # 저장값이 이상하면 기본값으로 복구된 보기(conversions 계산용)만 제공
            u = Units(**DEFAULT_UNITS)
        return UnitsSettingsOut(
            id=row.id,
            flow=flow,
            pressure=pressure,
            temperature=temperature,
            flux=flux,
            created_at=_iso(getattr(row, "created_at", None)),
            updated_at=_iso(getattr(row, "updated_at", None)),
            conversions=compute_conversions(u),
        )
    except SQLAlchemyError as e:
        raise HTTPException(500, f"db_error: {type(e).__name__}: {e}")


@router.put("/units", response_model=UnitsSettingsOut)
def put_units(
    payload: UnitsSettingsIn,
    project_id: str | None = Query(default=None),
    user_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    try:
        row = _get_scoped(db, project_id, user_id)
        # [CHANGED] 부분 업데이트: None 필드는 유지
        flow, pressure, temperature, flux = _merge_payload(row, payload)

        # [ADDED] 사전 검증(잘못된 단위면 422)
        try:
            u = Units(flow, pressure, temperature, flux)
        except Exception as e:
            raise HTTPException(status_code=422, detail=f"invalid units: {e}")

        # 저장
        row.units_flow = flow
        row.units_pressure = pressure
        row.units_temperature = temperature
        row.units_flux = flux
        db.add(row)
        db.commit()
        db.refresh(row)

        return UnitsSettingsOut(
            id=row.id,
            flow=flow,
            pressure=pressure,
            temperature=temperature,
            flux=flux,
            created_at=_iso(getattr(row, "created_at", None)),
            updated_at=_iso(getattr(row, "updated_at", None)),
            conversions=compute_conversions(u),
        )
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        raise HTTPException(500, f"db_error: {type(e).__name__}: {e}")
