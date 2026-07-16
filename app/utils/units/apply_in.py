# app/utils/units/apply_in.py

from __future__ import annotations
import copy
from typing import Any, Dict, Optional


def _to_engine(val: Any, cv: Dict[str, Any]) -> Any:
    """
    화면 표시 단위(Display Unit)의 값을 엔진(SI) 표준 단위로 변환합니다.
    (예: gpm -> m3/h)
    """
    if val is None:
        return None

    try:
        scale = float(cv["from_display"]["scale"])
        offset = float(cv["from_display"]["offset"])
        return float(val) * scale + offset
    except (TypeError, ValueError, KeyError):
        # 변환 계수가 없거나 숫자 변환이 불가능한 경우 원본 반환 (Pydantic이 나중에 검증함)
        return val


def _promote_key(data: Dict[str, Any], legacy_key: str, standard_key: str) -> None:
    """구형 필드명(Legacy Key)을 새 표준 필드명으로 마이그레이션합니다."""
    if legacy_key in data:
        if standard_key not in data:
            data[standard_key] = data[legacy_key]
        data.pop(legacy_key, None)


def _convert_inplace(
    data: Dict[str, Any], key: str, cv: Optional[Dict[str, Any]]
) -> None:
    """딕셔너리 내의 특정 키 값을 변환 맵(cv)을 참조하여 제자리에서(in-place) 변환합니다."""
    if key in data and cv:
        data[key] = _to_engine(data[key], cv)


def apply_display_to_engine(
    payload: Dict[str, Any], conversions: Dict[str, Any]
) -> Dict[str, Any]:
    """
    사용자 입력 Payload(Display Unit)를 시뮬레이션 엔진이 사용하는 SI 단위로 변환합니다.

    [주의] 이 함수는 Pydantic 스키마 검증 '이전(Before)'에 실행되어야 합니다.
    """
    # 원본 Payload 오염을 막기 위한 깊은 복사
    d = copy.deepcopy(payload or {})
    conversions = conversions or {}

    cv_flow = conversions.get("flow")
    cv_pressure = conversions.get("pressure")
    cv_temp = conversions.get("temperature")
    cv_flux = conversions.get("flux")

    # ==========================================
    # 1. Feed (유입수) 단위 변환
    # ==========================================
    feed = d.get("feed")
    if isinstance(feed, dict):
        # 구버전 호환성 패치
        _promote_key(feed, "flow", "flow_m3h")
        _promote_key(feed, "temp_C", "temperature_C")
        _promote_key(feed, "temperature_c", "temperature_C")

        # 실제 변환 적용
        _convert_inplace(feed, "flow_m3h", cv_flow)
        _convert_inplace(feed, "temperature_C", cv_temp)

    # ==========================================
    # 2. Stages (공정 모듈) 단위 변환
    # ==========================================
    stages = d.get("stages")
    if isinstance(stages, list):
        for s in stages:
            if not isinstance(s, dict):
                continue

            # 구버전 호환성 패치
            _promote_key(s, "pressure", "pressure_bar")
            _promote_key(s, "set_pressure", "set_pressure_bar")

            # 압력 (RO/NF/HRRO) 및 플럭스 (UF/MF) 단위 변환
            _convert_inplace(s, "pressure_bar", cv_pressure)
            _convert_inplace(s, "set_pressure_bar", cv_pressure)
            _convert_inplace(s, "flux_lmh", cv_flux)
            _convert_inplace(s, "backwash_flux_lmh", cv_flux)

    return d
