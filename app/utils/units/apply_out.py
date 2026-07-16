# app/utils/units/apply_out.py

from __future__ import annotations
import copy
from typing import Any, Dict, List, Optional


def _to_display(val: Any, cv: Dict[str, Any]) -> Any:
    """엔진 표준 단위(SI)의 값을 화면 표시 단위(Display Unit)로 변환합니다."""
    if val is None:
        return None
    try:
        scale = float(cv["to_display"]["scale"])
        offset = float(cv["to_display"]["offset"])
        return float(val) * scale + offset
    except (TypeError, ValueError, KeyError):
        return val


def _promote_key(data: Dict[str, Any], legacy_key: str, standard_key: str) -> None:
    """출력 표준화를 위해 구형 필드명을 새 표준 필드명으로 승격시키고 기존 키는 제거합니다."""
    if legacy_key in data:
        if standard_key not in data:
            data[standard_key] = data[legacy_key]
        data.pop(legacy_key, None)


def _convert_inplace(
    data: Dict[str, Any], key: str, cv: Optional[Dict[str, Any]]
) -> None:
    """딕셔너리 내의 특정 키 값을 제자리에서(in-place) 표시 단위로 변환합니다."""
    if key in data and cv:
        data[key] = _to_display(data[key], cv)


def to_display_streams(
    streams: Optional[List[Dict[str, Any]]], conv: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """스트림(Streams) 결과값의 단위를 변환합니다."""
    out = []
    for s in streams or []:
        sd = copy.deepcopy(s)
        _convert_inplace(sd, "flow_m3h", conv.get("flow"))
        _convert_inplace(sd, "pressure_bar", conv.get("pressure"))
        out.append(sd)
    return out


def to_display_kpi(
    kpi: Optional[Dict[str, Any]], conv: Dict[str, Any]
) -> Dict[str, Any]:
    """KPI 결과값의 단위를 변환합니다."""
    kd = copy.deepcopy(kpi or {})

    # 출력 표준화
    _promote_key(kd, "sec_kwh_m3", "sec_kwhm3")

    # 단위 변환
    _convert_inplace(kd, "flux_lmh", conv.get("flux"))
    _convert_inplace(kd, "ndp_bar", conv.get("pressure"))
    return kd


def to_display_stage_metrics(
    rows: Optional[List[Dict[str, Any]]], conv: Dict[str, Any]
) -> Optional[List[Dict[str, Any]]]:
    """스테이지별 메트릭스(Stage Metrics) 결과값의 단위를 변환합니다."""
    if not rows:
        return rows

    out = []
    for r in rows:
        rd = copy.deepcopy(r)

        # 출력 표준화
        _promote_key(rd, "pin_bar", "p_in_bar")
        _promote_key(rd, "pout_bar", "p_out_bar")
        _promote_key(rd, "sec_kwh_m3", "sec_kwhm3")

        # 단위 변환
        _convert_inplace(rd, "p_in_bar", conv.get("pressure"))
        _convert_inplace(rd, "p_out_bar", conv.get("pressure"))
        _convert_inplace(rd, "jw_avg_lmh", conv.get("flux"))
        out.append(rd)
    return out


def unit_labels(conv: Dict[str, Any]) -> Dict[str, str]:
    """PDF 생성 및 UI 응답에 덧붙일 단위 라벨(Label) 문자열 맵을 반환합니다."""
    return {
        "flow": conv.get("flow", {}).get("display", "m3/h"),
        "pressure": conv.get("pressure", {}).get("display", "bar"),
        "temperature": conv.get("temperature", {}).get("display", "C"),
        "flux": conv.get("flux", {}).get("display", "LMH"),
    }
