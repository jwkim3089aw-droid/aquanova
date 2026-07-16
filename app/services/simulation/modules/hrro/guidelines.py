# app/services/simulation/modules/hrro/guidelines.py
from typing import Any, Dict, Optional, Tuple

GUIDELINES: Dict[str, Dict[int, Dict[str, Any]]] = {
    "시수 (Municipal Supply)": {
        8: {
            "sdi": "<5",
            "avg_flux_range_lmh": (20.0, 26.0),
            "conc_flow_min_m3h_per_vessel": 3.6,
            "feed_flow_max_m3h_per_vessel": 15.0,
            "dp_max_bar": 2.0,
            "element_recovery_max_pct": 15.0,
            "beta_max": 1.2,
            "flux_decline_ratio_max_pct": 13.0,
        },
        4: {
            "sdi": "<5",
            "avg_flux_range_lmh": None,
            "conc_flow_min_m3h_per_vessel": 0.7,
            "feed_flow_max_m3h_per_vessel": 2.8,
            "dp_max_bar": None,
            "element_recovery_max_pct": None,
            "beta_max": None,
            "flux_decline_ratio_max_pct": None,
        },
    },
    "기수 및 지하수 (Brackish Wells)": {
        8: {
            "sdi": "<3",
            "avg_flux_range_lmh": (23.0, 29.0),
            "conc_flow_min_m3h_per_vessel": 3.0,
            "feed_flow_max_m3h_per_vessel": 16.0,
            "dp_max_bar": 3.0,
            "element_recovery_max_pct": 20.0,
            "beta_max": 1.2,
            "flux_decline_ratio_max_pct": 10.0,
        },
        4: {
            "sdi": "<3",
            "avg_flux_range_lmh": None,
            "conc_flow_min_m3h_per_vessel": 0.6,
            "feed_flow_max_m3h_per_vessel": 3.2,
            "dp_max_bar": None,
            "element_recovery_max_pct": None,
            "beta_max": None,
            "flux_decline_ratio_max_pct": None,
        },
    },
    "지표수 - 매체 여과 (Surface Water Media Filtration)": {
        8: {
            "sdi": "<5",
            "avg_flux_range_lmh": (20.0, 26.0),
            "conc_flow_min_m3h_per_vessel": 3.6,
            "feed_flow_max_m3h_per_vessel": 15.0,
            "dp_max_bar": 2.0,
            "element_recovery_max_pct": 15.0,
            "beta_max": 1.2,
            "flux_decline_ratio_max_pct": 13.0,
        },
        4: {
            "sdi": "<5",
            "avg_flux_range_lmh": None,
            "conc_flow_min_m3h_per_vessel": 0.7,
            "feed_flow_max_m3h_per_vessel": 2.6,
            "dp_max_bar": None,
            "element_recovery_max_pct": None,
            "beta_max": None,
            "flux_decline_ratio_max_pct": None,
        },
    },
    "지표수 - 정밀/한외 여과 (Surface Water MF/UF Filtration)": {
        8: {
            "sdi": "<3",
            "avg_flux_range_lmh": (23.0, 29.0),
            "conc_flow_min_m3h_per_vessel": 3.0,
            "feed_flow_max_m3h_per_vessel": 16.0,
            "dp_max_bar": 3.0,
            "element_recovery_max_pct": 20.0,
            "beta_max": 1.2,
            "flux_decline_ratio_max_pct": 10.0,
        },
        4: {
            "sdi": "<3",
            "avg_flux_range_lmh": None,
            "conc_flow_min_m3h_per_vessel": 0.6,
            "feed_flow_max_m3h_per_vessel": 3.2,
            "dp_max_bar": None,
            "element_recovery_max_pct": None,
            "beta_max": None,
            "flux_decline_ratio_max_pct": None,
        },
    },
    "2차 하수 - 매체 여과 (Secondary Waste Media Filtration)": {
        8: {
            "sdi": "<5",
            "avg_flux_range_lmh": (14.0, 20.0),
            "conc_flow_min_m3h_per_vessel": 4.1,
            "feed_flow_max_m3h_per_vessel": 14.0,
            "dp_max_bar": 2.0,
            "element_recovery_max_pct": 12.0,
            "beta_max": 1.2,
            "flux_decline_ratio_max_pct": 18.0,
        },
        4: {
            "sdi": "<5",
            "avg_flux_range_lmh": None,
            "conc_flow_min_m3h_per_vessel": 0.8,
            "feed_flow_max_m3h_per_vessel": 2.6,
            "dp_max_bar": None,
            "element_recovery_max_pct": None,
            "beta_max": None,
            "flux_decline_ratio_max_pct": None,
        },
    },
    "2차 하수 - 정밀/한외 여과 (Secondary Waste MF/UF Filtration)": {
        8: {
            "sdi": "<3",
            "avg_flux_range_lmh": (17.0, 23.0),
            "conc_flow_min_m3h_per_vessel": 3.6,
            "feed_flow_max_m3h_per_vessel": 14.0,
            "dp_max_bar": 2.0,
            "element_recovery_max_pct": 17.0,
            "beta_max": 1.2,
            "flux_decline_ratio_max_pct": 15.0,
        },
        4: {
            "sdi": "<3",
            "avg_flux_range_lmh": None,
            "conc_flow_min_m3h_per_vessel": 0.7,
            "feed_flow_max_m3h_per_vessel": 2.8,
            "dp_max_bar": None,
            "element_recovery_max_pct": None,
            "beta_max": None,
            "flux_decline_ratio_max_pct": None,
        },
    },
    "해수 취수 - 매체 여과 (Seawater Intake Media Filtration)": {
        8: {
            "sdi": "<5",
            "avg_flux_range_lmh": (11.0, 17.0),
            "conc_flow_min_m3h_per_vessel": 3.6,
            "feed_flow_max_m3h_per_vessel": 14.0,
            "dp_max_bar": 2.0,
            "element_recovery_max_pct": 13.0,
            "beta_max": 1.2,
            "flux_decline_ratio_max_pct": 8.0,
        },
        4: {
            "sdi": "<5",
            "avg_flux_range_lmh": None,
            "conc_flow_min_m3h_per_vessel": 0.7,
            "feed_flow_max_m3h_per_vessel": 2.8,
            "dp_max_bar": None,
            "element_recovery_max_pct": None,
            "beta_max": None,
            "flux_decline_ratio_max_pct": None,
        },
    },
    "해수 취수 - 정밀/한외 여과 (Seawater Intake MF/UF Filtration)": {
        8: {
            "sdi": "<3",
            "avg_flux_range_lmh": (14.0, 20.0),
            "conc_flow_min_m3h_per_vessel": 3.4,
            "feed_flow_max_m3h_per_vessel": 16.0,
            "dp_max_bar": 3.0,
            "element_recovery_max_pct": 15.0,
            "beta_max": 1.2,
            "flux_decline_ratio_max_pct": 6.0,
        },
        4: {
            "sdi": "<3",
            "avg_flux_range_lmh": None,
            "conc_flow_min_m3h_per_vessel": 0.7,
            "feed_flow_max_m3h_per_vessel": 3.0,
            "dp_max_bar": None,
            "element_recovery_max_pct": None,
            "beta_max": None,
            "flux_decline_ratio_max_pct": None,
        },
    },
    "해수 비치 웰 (Seawater Beach Wells)": {
        8: {
            "sdi": "<3",
            "avg_flux_range_lmh": (14.0, 20.0),
            "conc_flow_min_m3h_per_vessel": 3.4,
            "feed_flow_max_m3h_per_vessel": 16.0,
            "dp_max_bar": 3.0,
            "element_recovery_max_pct": 15.0,
            "beta_max": 1.2,
            "flux_decline_ratio_max_pct": 6.0,
        },
        4: {
            "sdi": "<3",
            "avg_flux_range_lmh": None,
            "conc_flow_min_m3h_per_vessel": None,
            "feed_flow_max_m3h_per_vessel": 3.0,
            "dp_max_bar": None,
            "element_recovery_max_pct": None,
            "beta_max": None,
            "flux_decline_ratio_max_pct": None,
        },
    },
    "RO 생산수 (RO Permeate)": {
        8: {
            "sdi": "<1",
            "avg_flux_range_lmh": (32.0, 42.0),
            "conc_flow_min_m3h_per_vessel": 2.4,
            "feed_flow_max_m3h_per_vessel": 17.0,
            "dp_max_bar": 3.0,
            "element_recovery_max_pct": 30.0,
            "beta_max": 1.3,
            "flux_decline_ratio_max_pct": 6.0,
        },
        4: {
            "sdi": "<1",
            "avg_flux_range_lmh": None,
            "conc_flow_min_m3h_per_vessel": 0.5,
            "feed_flow_max_m3h_per_vessel": 3.6,
            "dp_max_bar": None,
            "element_recovery_max_pct": None,
            "beta_max": None,
            "flux_decline_ratio_max_pct": None,
        },
    },
}


def _norm(s: Optional[str]) -> str:
    return (s or "").strip().lower()


def choose_guideline_profile(
    *,
    water_type: Any,
    water_subtype: Optional[str],
    sdi15: Optional[float],
    tds_mgL: float,
) -> Tuple[str, str]:
    wt_l = str(water_type).strip().lower() if water_type is not None else ""
    sub = _norm(water_subtype)
    sdi = float(sdi15) if sdi15 is not None else None

    if tds_mgL <= 200.0 and sdi is not None and sdi <= 1.0:
        return ("RO 생산수 (RO Permeate)", "TDS <= 200 & SDI <= 1 조건 부합")
    if "seawater" in wt_l:
        if "beach" in sub:
            return (
                "해수 비치 웰 (Seawater Beach Wells)",
                "해수 및 Beach Well 조건 부합",
            )
        if "mf" in sub or "uf" in sub or (sdi is not None and sdi <= 3.0):
            return (
                "해수 취수 - 정밀/한외 여과 (Seawater Intake MF/UF Filtration)",
                "해수 및 MF/UF 조건 부합",
            )
        return (
            "해수 취수 - 매체 여과 (Seawater Intake Media Filtration)",
            "해수 기본값 적용",
        )
    if "surface" in wt_l:
        if "mf" in sub or "uf" in sub or (sdi is not None and sdi <= 3.0):
            return (
                "지표수 - 정밀/한외 여과 (Surface Water MF/UF Filtration)",
                "지표수 및 MF/UF 조건 부합",
            )
        return (
            "지표수 - 매체 여과 (Surface Water Media Filtration)",
            "지표수 기본값 적용",
        )
    if "wastewater" in wt_l:
        if "mf" in sub or "uf" in sub or (sdi is not None and sdi <= 3.0):
            return (
                "2차 하수 - 정밀/한외 여과 (Secondary Waste MF/UF Filtration)",
                "하수 및 MF/UF 조건 부합",
            )
        return (
            "2차 하수 - 매체 여과 (Secondary Waste Media Filtration)",
            "하수 기본값 적용",
        )
    if "brackish" in wt_l or "groundwater" in wt_l:
        return ("기수 및 지하수 (Brackish Wells)", "기수/지하수 기준 적용")

    return "시수 (Municipal Supply)", "분류 불가 - 기본값 일괄 적용"
