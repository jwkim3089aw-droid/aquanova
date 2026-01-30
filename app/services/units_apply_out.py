# app\services\units_apply_out.py
from __future__ import annotations

from copy import deepcopy


def _to_display(val, cv: dict):
    if val is None:
        return None
    try:
        return float(val) * float(cv["to_display"]["scale"]) + float(
            cv["to_display"]["offset"]
        )
    except Exception:
        return val


def _promote_key(d: dict, legacy: str, standard: str) -> None:
    """legacy 키가 있으면 standard로 승격하고 legacy는 제거(출력 표준화)."""
    if legacy in d and standard not in d:
        d[standard] = d[legacy]
    if legacy in d:
        d.pop(legacy, None)


def to_display_streams(streams: list[dict], conv: dict) -> list[dict]:
    out = []
    for s in streams or []:
        sd = deepcopy(s)
        if "flow_m3h" in sd and "flow" in conv:
            sd["flow_m3h"] = _to_display(sd["flow_m3h"], conv["flow"])
        if "pressure_bar" in sd and "pressure" in conv:
            sd["pressure_bar"] = _to_display(sd["pressure_bar"], conv["pressure"])
        out.append(sd)
    return out


def to_display_kpi(kpi: dict, conv: dict) -> dict:
    kd = deepcopy(kpi or {})

    # ✅ 출력 표준화: 레거시 키 흡수 후 제거
    _promote_key(kd, "sec_kwh_m3", "sec_kwhm3")

    # flux_lmh -> flux display
    if "flux_lmh" in kd and "flux" in conv:
        kd["flux_lmh"] = _to_display(kd["flux_lmh"], conv["flux"])

    # ndp_bar -> pressure display
    if "ndp_bar" in kd and "pressure" in conv:
        kd["ndp_bar"] = _to_display(kd["ndp_bar"], conv["pressure"])

    return kd


def to_display_stage_metrics(rows: list[dict] | None, conv: dict) -> list[dict] | None:
    if not rows:
        return rows

    out: list[dict] = []
    for r in rows:
        rd = deepcopy(r)

        # ✅ 출력 표준화: 레거시 키 흡수 후 제거
        _promote_key(rd, "pin_bar", "p_in_bar")
        _promote_key(rd, "pout_bar", "p_out_bar")
        _promote_key(rd, "sec_kwh_m3", "sec_kwhm3")

        # pressure display
        if "p_in_bar" in rd and "pressure" in conv:
            rd["p_in_bar"] = _to_display(rd["p_in_bar"], conv["pressure"])
        if "p_out_bar" in rd and "pressure" in conv:
            rd["p_out_bar"] = _to_display(rd["p_out_bar"], conv["pressure"])

        # flux display
        if "jw_avg_lmh" in rd and "flux" in conv:
            rd["jw_avg_lmh"] = _to_display(rd["jw_avg_lmh"], conv["flux"])

        out.append(rd)

    return out


def unit_labels(conv: dict) -> dict:
    """PDF/응답에 덧붙일 단위 라벨들"""
    return {
        "flow": conv.get("flow", {}).get("display", "m3/h"),
        "pressure": conv.get("pressure", {}).get("display", "bar"),
        "temperature": conv.get("temperature", {}).get("display", "C"),
        "flux": conv.get("flux", {}).get("display", "LMH"),
    }
