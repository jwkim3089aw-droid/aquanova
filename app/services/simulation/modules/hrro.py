# app/services/simulation/modules/hrro.py
# HRRO (Excel-baseline + optional physics) + Guide Line auto validation
#
# Goals
# - Reproduce the Excel "CCRO표지" sheet baseline exactly for Qp/Qc/Flux
# - Optionally compute pressure/CP/ΔP/SEC by matching a target flux (excel_physics)
# - Run automatic guideline checks (from Excel "Guide Line") and return violations
#
# Engine modes (StageConfig.hrro_engine)
#   - "excel_only": Excel flow/flux only (+ optional Cp/Cc estimator)
#   - "excel_physics": Use target flux (default: Excel flux) and solve inlet pressure with CP + ΔP + SEC
#
# excel_only permeate/concentrate salinity model (StageConfig.hrro_excel_only_cp_mode)
#   - "min_model": simple fixed-rejection model (overrideable)
#   - "fixed_rejection": apply a fixed rejection (%)
#   - "none": Cp/Cc = None (skip salt model)
#
# Notes
# - Defaults are chosen to be conservative and stable; any knob can be overridden from StageConfig.

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

from app.services.simulation.modules.base import SimulationModule

if TYPE_CHECKING:
    from app.schemas.simulation import (
        StageConfig,
        FeedInput,
        StageMetric,
        TimeSeriesPoint,
    )

LMH_TO_MPS = 1e-3 / 3600.0  # LMH -> m/s
PA_TO_BAR = 1.0 / 1e5


# =============================================================================
# small utils
# =============================================================================
def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(float(x), hi))


def _f(v: Any, default: float) -> float:
    try:
        if v is None:
            return float(default)
        return float(v)
    except Exception:
        return float(default)


def _i(v: Any, default: int) -> int:
    try:
        if v is None:
            return int(default)
        return int(v)
    except Exception:
        return int(default)


def _norm(s: Optional[str]) -> str:
    return (s or "").strip().lower()


# =============================================================================
# 0) Excel(CCRO표지) baseline formulas (1:1)
# =============================================================================
@dataclass(frozen=True)
class ExcelInputs:
    """
    These inputs map to Excel sheet "CCRO표지" cells:

    - q_raw_m3h            -> C7
    - ccro_recovery_pct    -> G7  (percent)
    - pf_feed_ratio_pct    -> K5  (percent)
    - pf_recovery_pct      -> K6  (percent)
    - cc_recycle_m3h_per_pv-> O5  (m3/h per PV)
    - vessel_count         -> H18
    - elements_per_vessel  -> H19
    - area_m2_per_element  -> C22 (m2 per element)
    """

    q_raw_m3h: float
    ccro_recovery_pct: float
    pf_feed_ratio_pct: float
    pf_recovery_pct: float
    cc_recycle_m3h_per_pv: float
    vessel_count: int
    elements_per_vessel: int
    area_m2_per_element: float


@dataclass(frozen=True)
class ExcelResults:
    total_elements: int
    total_area_m2: float

    ccro_qp_m3h: float
    ccro_qc_m3h: float
    ccro_flux_lmh: float

    pf_feed_m3h: float
    pf_qp_m3h: float
    pf_qc_m3h: float
    pf_flux_lmh: float
    cc_feed_m3h: float  # V10

    cc_blend_feed_m3h_per_pv: float
    cc_qp_m3h_per_pv: float
    cc_qc_m3h_per_pv: float
    cc_recovery_pct: float
    cc_flux_lmh: float


def compute_excel(inp: ExcelInputs) -> ExcelResults:
    vessel_count = max(1, int(inp.vessel_count))
    pv_elems = max(1, int(inp.elements_per_vessel))
    area_per_el = max(1e-9, float(inp.area_m2_per_element))

    total_elements = vessel_count * pv_elems
    total_area_m2 = total_elements * area_per_el

    q = max(1e-9, float(inp.q_raw_m3h))
    rec = _clamp(float(inp.ccro_recovery_pct), 0.0, 100.0)

    # CCRO (G8/G9/G10)
    ccro_qp = q * rec / 100.0
    ccro_qc = q - ccro_qp
    ccro_flux = (ccro_qp * 1000.0) / total_area_m2

    # PF helper (T7/V7/V8/V9/V10)
    K5 = float(inp.pf_feed_ratio_pct)
    if K5 >= 101.0:
        T7 = (q * (rec / 100.0)) / 10.0
    else:
        T7 = 0.0
    V7 = (K5 - 100.0) / 10.0
    V8 = T7 * V7
    V9 = q + V8
    V10 = V9 / (K5 / 100.0) if K5 > 0 else 0.0

    # PF (K7/K8/K9/K10)
    pf_feed = V9
    pf_rec = _clamp(float(inp.pf_recovery_pct), 0.0, 100.0)
    pf_qp = pf_feed * pf_rec / 100.0
    pf_qc = pf_feed - pf_qp
    pf_flux = (pf_qp * 1000.0) / total_area_m2

    # CC (O5/O6/O7/O8/O9/O10/O11) per PV
    O5 = max(0.0, float(inp.cc_recycle_m3h_per_pv))
    O7 = V10
    O8 = O5 + O7
    O9 = O7
    O10 = O5
    O6 = (O9 / O8) * 100.0 if O8 > 0 else 0.0
    O11 = (O9 * 1000.0) / total_area_m2

    return ExcelResults(
        total_elements=total_elements,
        total_area_m2=total_area_m2,
        ccro_qp_m3h=ccro_qp,
        ccro_qc_m3h=ccro_qc,
        ccro_flux_lmh=ccro_flux,
        pf_feed_m3h=pf_feed,
        pf_qp_m3h=pf_qp,
        pf_qc_m3h=pf_qc,
        pf_flux_lmh=pf_flux,
        cc_feed_m3h=V10,
        cc_blend_feed_m3h_per_pv=O8,
        cc_qp_m3h_per_pv=O9,
        cc_qc_m3h_per_pv=O10,
        cc_recovery_pct=O6,
        cc_flux_lmh=O11,
    )


# =============================================================================
# 0.5) Guide Line table (from Excel sheet "Guide Line")
# =============================================================================
GUIDELINES: Dict[str, Dict[int, Dict[str, Any]]] = {
    "municipal Supply": {
        8: {
            "sdi": "<5",
            "avg_flux_range_lmh": (20.0, 26.0),
            "lead_flux_max_lmh": 31.0,
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
            "lead_flux_max_lmh": None,
            "conc_flow_min_m3h_per_vessel": 0.7,
            "feed_flow_max_m3h_per_vessel": 2.8,
            "dp_max_bar": None,
            "element_recovery_max_pct": None,
            "beta_max": None,
            "flux_decline_ratio_max_pct": None,
        },
    },
    "Brackish Wells": {
        8: {
            "sdi": "<3",
            "avg_flux_range_lmh": (23.0, 29.0),
            "lead_flux_max_lmh": 34.0,
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
            "lead_flux_max_lmh": None,
            "conc_flow_min_m3h_per_vessel": 0.6,
            "feed_flow_max_m3h_per_vessel": 3.2,
            "dp_max_bar": None,
            "element_recovery_max_pct": None,
            "beta_max": None,
            "flux_decline_ratio_max_pct": None,
        },
    },
    "Surface Water media fillteration": {
        8: {
            "sdi": "<5",
            "avg_flux_range_lmh": (20.0, 26.0),
            "lead_flux_max_lmh": 31.0,
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
            "lead_flux_max_lmh": None,
            "conc_flow_min_m3h_per_vessel": 0.7,
            "feed_flow_max_m3h_per_vessel": 2.6,
            "dp_max_bar": None,
            "element_recovery_max_pct": None,
            "beta_max": None,
            "flux_decline_ratio_max_pct": None,
        },
    },
    "Surface Water MF/UF Filteration": {
        8: {
            "sdi": "<3",
            "avg_flux_range_lmh": (23.0, 29.0),
            "lead_flux_max_lmh": 34.0,
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
            "lead_flux_max_lmh": None,
            "conc_flow_min_m3h_per_vessel": 0.6,
            "feed_flow_max_m3h_per_vessel": 3.2,
            "dp_max_bar": None,
            "element_recovery_max_pct": None,
            "beta_max": None,
            "flux_decline_ratio_max_pct": None,
        },
    },
    "Secondary Waste media Filteration": {
        8: {
            "sdi": "<5",
            "avg_flux_range_lmh": (14.0, 20.0),
            "lead_flux_max_lmh": 24.0,
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
            "lead_flux_max_lmh": None,
            "conc_flow_min_m3h_per_vessel": 0.8,
            "feed_flow_max_m3h_per_vessel": 2.6,
            "dp_max_bar": None,
            "element_recovery_max_pct": None,
            "beta_max": None,
            "flux_decline_ratio_max_pct": None,
        },
    },
    "Secondary Waste MF/UF Filteration": {
        8: {
            "sdi": "<3",
            "avg_flux_range_lmh": (17.0, 23.0),
            "lead_flux_max_lmh": 28.0,
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
            "lead_flux_max_lmh": None,
            "conc_flow_min_m3h_per_vessel": 0.7,
            "feed_flow_max_m3h_per_vessel": 2.8,
            "dp_max_bar": None,
            "element_recovery_max_pct": None,
            "beta_max": None,
            "flux_decline_ratio_max_pct": None,
        },
    },
    "Seawater Intake media Filteration": {
        8: {
            "sdi": "<5",
            "avg_flux_range_lmh": (11.0, 17.0),
            "lead_flux_max_lmh": 30.0,
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
            "lead_flux_max_lmh": None,
            "conc_flow_min_m3h_per_vessel": 0.7,
            "feed_flow_max_m3h_per_vessel": 2.8,
            "dp_max_bar": None,
            "element_recovery_max_pct": None,
            "beta_max": None,
            "flux_decline_ratio_max_pct": None,
        },
    },
    "SeaWater Intake MF/UF filtertation": {
        8: {
            "sdi": "<3",
            "avg_flux_range_lmh": (14.0, 20.0),
            "lead_flux_max_lmh": 35.0,
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
            "lead_flux_max_lmh": None,
            "conc_flow_min_m3h_per_vessel": 0.7,
            "feed_flow_max_m3h_per_vessel": 3.0,
            "dp_max_bar": None,
            "element_recovery_max_pct": None,
            "beta_max": None,
            "flux_decline_ratio_max_pct": None,
        },
    },
    "Seawater Beach Wells": {
        8: {
            "sdi": "<3",
            "avg_flux_range_lmh": (14.0, 20.0),
            "lead_flux_max_lmh": 35.0,
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
            "lead_flux_max_lmh": None,
            "conc_flow_min_m3h_per_vessel": None,
            "feed_flow_max_m3h_per_vessel": 3.0,
            "dp_max_bar": None,
            "element_recovery_max_pct": None,
            "beta_max": None,
            "flux_decline_ratio_max_pct": None,
        },
    },
    "RO Pemeate": {
        8: {
            "sdi": "<1",
            "avg_flux_range_lmh": (32.0, 42.0),
            "lead_flux_max_lmh": 48.0,
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
            "lead_flux_max_lmh": None,
            "conc_flow_min_m3h_per_vessel": 0.5,
            "feed_flow_max_m3h_per_vessel": 3.6,
            "dp_max_bar": None,
            "element_recovery_max_pct": None,
            "beta_max": None,
            "flux_decline_ratio_max_pct": None,
        },
    },
}


def infer_element_inch(area_m2_per_element: float) -> int:
    return 8 if float(area_m2_per_element) >= 20.0 else 4


def choose_guideline_profile(
    *,
    water_type: Any,
    water_subtype: Optional[str],
    sdi15: Optional[float],
    tds_mgL: float,
) -> Tuple[str, str]:
    """
    Choose a guideline profile heuristically.
    Returns (profile_name, reason)
    """
    wt = str(water_type).strip() if water_type is not None else ""
    wt_l = wt.lower()
    sub = _norm(water_subtype)

    sdi = None
    try:
        sdi = float(sdi15) if sdi15 is not None else None
    except Exception:
        sdi = None

    if tds_mgL <= 200.0 and sdi is not None and sdi <= 1.0:
        return "RO Pemeate", "tds<=200 & sdi<=1 -> RO permeate"

    if "seawater" in wt_l:
        if "beach" in sub:
            return (
                "Seawater Beach Wells",
                "water_type=seawater & subtype contains beach",
            )
        if "mf" in sub or "uf" in sub or (sdi is not None and sdi <= 3.0):
            return "SeaWater Intake MF/UF filtertation", "seawater + (mf/uf or sdi<=3)"
        return "Seawater Intake media Filteration", "seawater default(media filtration)"

    if "surface" in wt_l:
        if "mf" in sub or "uf" in sub or (sdi is not None and sdi <= 3.0):
            return "Surface Water MF/UF Filteration", "surface + (mf/uf or sdi<=3)"
        return "Surface Water media fillteration", "surface default(media filtration)"

    if "wastewater" in wt_l:
        if "mf" in sub or "uf" in sub or (sdi is not None and sdi <= 3.0):
            return "Secondary Waste MF/UF Filteration", "wastewater + (mf/uf or sdi<=3)"
        return (
            "Secondary Waste media Filteration",
            "wastewater default(media filtration)",
        )

    if "brackish" in wt_l or "groundwater" in wt_l:
        return "Brackish Wells", "brackish/groundwater -> brackish wells"

    return "municipal Supply", "default fallback(municipal)"


def build_guideline_violations(
    *,
    profile: str,
    inch: int,
    checks: Dict[str, Optional[float]],
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """
    Build guideline "used" object and list of violations based on computed checks.
    """
    g = (GUIDELINES.get(profile, {}) or {}).get(inch)
    if g is None:
        profile = "municipal Supply"
        g = (GUIDELINES.get(profile, {}) or {}).get(inch)
    g = g or {}

    violations: List[Dict[str, Any]] = []

    def v_fail(
        key: str, msg: str, value: Optional[float], limit: Any, unit: str = ""
    ) -> None:
        violations.append(
            {"key": key, "message": msg, "value": value, "limit": limit, "unit": unit}
        )

    avg_flux = checks.get("avg_flux_lmh")
    r = g.get("avg_flux_range_lmh")
    if avg_flux is not None and isinstance(r, tuple) and len(r) == 2:
        lo, hi = float(r[0]), float(r[1])
        if not (lo <= float(avg_flux) <= hi):
            v_fail(
                "avg_flux_range",
                f"Average flux {avg_flux:.3f} LMH is out of guideline range [{lo}..{hi}]",
                float(avg_flux),
                {"min": lo, "max": hi},
                "LMH",
            )

    lead_flux = checks.get("lead_flux_lmh")
    lead_max = g.get("lead_flux_max_lmh")
    if lead_flux is not None and lead_max is not None:
        if float(lead_flux) > float(lead_max) + 1e-9:
            v_fail(
                "lead_flux_max",
                f"Lead flux {lead_flux:.3f} LMH exceeds guideline max {lead_max}",
                float(lead_flux),
                float(lead_max),
                "LMH",
            )

    qc = checks.get("conc_flow_m3h_per_vessel")
    qc_min = g.get("conc_flow_min_m3h_per_vessel")
    if qc is not None and qc_min is not None:
        if float(qc) + 1e-12 < float(qc_min):
            v_fail(
                "conc_flow_min",
                f"Concentrate flow/vessel {qc:.6f} m3/h is below guideline min {qc_min}",
                float(qc),
                float(qc_min),
                "m3/h",
            )

    qf = checks.get("feed_flow_m3h_per_vessel")
    qf_max = g.get("feed_flow_max_m3h_per_vessel")
    if qf is not None and qf_max is not None:
        if float(qf) > float(qf_max) + 1e-9:
            v_fail(
                "feed_flow_max",
                f"Feed flow/vessel {qf:.6f} m3/h exceeds guideline max {qf_max}",
                float(qf),
                float(qf_max),
                "m3/h",
            )

    dp = checks.get("dp_bar_per_vessel")
    dp_max = g.get("dp_max_bar")
    if dp is not None and dp_max is not None:
        if float(dp) > float(dp_max) + 1e-9:
            v_fail(
                "dp_max",
                f"Pressure drop/vessel {dp:.3f} bar exceeds guideline max {dp_max}",
                float(dp),
                float(dp_max),
                "bar",
            )

    er = checks.get("element_recovery_pct")
    er_max = g.get("element_recovery_max_pct")
    if er is not None and er_max is not None:
        if float(er) > float(er_max) + 1e-9:
            v_fail(
                "element_recovery_max",
                f"Element recovery(avg) {er:.3f}% exceeds guideline max {er_max}%",
                float(er),
                float(er_max),
                "%",
            )

    beta = checks.get("beta_max")
    beta_max = g.get("beta_max")
    if beta is not None and beta_max is not None:
        if float(beta) > float(beta_max) + 1e-9:
            v_fail(
                "beta_max",
                f"Beta(max) {beta:.4f} exceeds guideline max {beta_max}",
                float(beta),
                float(beta_max),
                "-",
            )

    fdr = checks.get("flux_decline_ratio_pct")
    fdr_max = g.get("flux_decline_ratio_max_pct")
    if fdr is not None and fdr_max is not None:
        if float(fdr) > float(fdr_max) + 1e-9:
            v_fail(
                "flux_decline_ratio_max",
                f"Flux decline ratio {fdr:.3f}% exceeds guideline max {fdr_max}%",
                float(fdr),
                float(fdr_max),
                "%",
            )

    guideline_used = {"profile": profile, "element_inch": inch, "limits": g}
    return guideline_used, violations


# =============================================================================
# excel_only Cp 옵션 로직
# =============================================================================
def excel_only_compute_cp_cc(
    *,
    cf_mgL: float,
    qf_m3h: float,
    qp_m3h: float,
    qc_m3h: float,
    cp_mode: str,
    fixed_rejection_pct: float,
    min_model_rejection_pct: Optional[float],
    fallback_rejection_pct: float,
) -> Tuple[Optional[float], Optional[float], Dict[str, Any]]:
    """
    returns: (Cp, Cc, debug)
    """
    cf = max(0.0, float(cf_mgL))
    qf = max(0.0, float(qf_m3h))
    qp = max(0.0, float(qp_m3h))
    qc = max(0.0, float(qc_m3h))

    mode = (cp_mode or "min_model").strip().lower()
    dbg: Dict[str, Any] = {"cp_mode": mode}

    if mode == "none":
        return None, None, dbg

    if mode == "fixed_rejection":
        rej = _clamp(float(fixed_rejection_pct), 0.0, 100.0)
        dbg["rejection_pct"] = rej
        dbg["rejection_source"] = "hrro_excel_only_fixed_rejection_pct"
    else:
        # min_model
        if min_model_rejection_pct is not None:
            rej = _clamp(float(min_model_rejection_pct), 0.0, 100.0)
            dbg["rejection_pct"] = rej
            dbg["rejection_source"] = "hrro_excel_only_min_model_rejection_pct"
        else:
            rej = _clamp(float(fallback_rejection_pct), 0.0, 100.0)
            dbg["rejection_pct"] = rej
            dbg["rejection_source"] = "membrane_salt_rejection_pct_or_default"

    cp = cf * (1.0 - rej / 100.0)

    # salt balance -> Cc
    if qc > 1e-12:
        salt_in = qf * cf
        salt_perm = qp * cp
        salt_out = max(0.0, salt_in - salt_perm)
        cc = salt_out / qc
    else:
        cc = None

    return cp, cc, dbg


# =============================================================================
# 1) Water properties (robust, clamped)
# =============================================================================
def calc_water_properties(temp_c: float, tds_mgL: float) -> Tuple[float, float, float]:
    """
    Returns: (rho_kg_m3, mu_Pa_s, pi_bar)
    """
    t = _clamp(float(temp_c), 5.0, 45.0)
    tds = max(0.0, float(tds_mgL))
    s_frac = _clamp(tds / 1_000_000.0, 0.0, 0.10)

    rho_w = 999.9 + 2.034e-2 * t - 6.162e-3 * (t**2) + 2.261e-5 * (t**3)
    rho = rho_w + s_frac * (802.0 - 2.0 * t)
    rho = _clamp(rho, 950.0, 1050.0)

    mu_w = 2.414e-5 * 10 ** (247.8 / (t + 133.15))
    mu_rel = 1.0 + 1.5 * s_frac + (s_frac**2)
    mu = mu_w * mu_rel
    mu = _clamp(mu, 0.0004, 0.0020)

    # osmotic pressure (bar), rough van't Hoff-like
    temp_k = t + 273.15
    c_mol = tds / 58440.0  # approx NaCl eq
    phi = 0.95 if tds <= 30000 else 1.05
    pi = phi * 2.0 * c_mol * 0.08314 * temp_k
    pi = max(0.0, pi)

    return rho, mu, pi


# =============================================================================
# 2) Membrane base temperature correction (TCF)
# =============================================================================
def correct_membrane_params(
    A0_lmh_bar: float, B0_lmh: float, temp_c: float
) -> Tuple[float, float]:
    dt = float(temp_c) - 25.0
    tcf_a = math.exp(0.027 * dt)
    tcf_b = math.exp(0.050 * dt)
    return float(A0_lmh_bar) * tcf_a, float(B0_lmh) * tcf_b


# =============================================================================
# 3) Hydraulics / Mass-transfer helpers
# =============================================================================
def hydraulic_diameter(spacer_thickness_m: float, voidage: float) -> float:
    h = max(1e-6, float(spacer_thickness_m))
    eps = _clamp(float(voidage), 0.30, 0.95)
    dh = 2.0 * h * eps / (2.0 - eps)
    return max(dh, 1e-6)


def friction_factor_smooth(Re: float) -> float:
    Re = max(float(Re), 1.0)
    if Re < 2100.0:
        return 64.0 / Re
    return 0.3164 / (Re**0.25)


def pressure_drop_spacer_bar(
    *,
    rho_kg_m3: float,
    mu_pa_s: float,
    velocity_m_s: float,
    dh_m: float,
    length_m: float,
    spacer_friction_multiplier: float = 5.0,
) -> float:
    rho = max(1.0, float(rho_kg_m3))
    mu = max(1e-6, float(mu_pa_s))
    v = max(1e-6, float(velocity_m_s))
    dh = max(1e-6, float(dh_m))
    L = max(1e-3, float(length_m))

    Re = (rho * v * dh) / mu
    f = friction_factor_smooth(Re)

    K = max(1.0, float(spacer_friction_multiplier))
    dp_pa = (f * (L / dh) * (rho * v * v / 2.0)) * K
    dp_bar = dp_pa * PA_TO_BAR
    return max(0.0, dp_bar)


def mass_transfer_coeff_m_s(
    *,
    rho_kg_m3: float,
    mu_pa_s: float,
    velocity_m_s: float,
    dh_m: float,
    diffusivity_m2_s: float,
) -> float:
    rho = max(1.0, float(rho_kg_m3))
    mu = max(1e-6, float(mu_pa_s))
    v = max(1e-6, float(velocity_m_s))
    dh = max(1e-6, float(dh_m))
    D = max(1e-12, float(diffusivity_m2_s))

    Re = max((rho * v * dh) / mu, 1.0)
    Sc = max(mu / (rho * D), 1.0)

    Sh = 0.065 * (Re**0.875) * (Sc**0.25)
    k = (Sh * D) / dh
    return max(k, 1e-8)


# =============================================================================
# 4) Transport param modifiers (empirical)
# =============================================================================
def effective_transport_params(
    *,
    A_lmh_bar_base: float,
    B_lmh_base: float,
    mu_pa_s: float,
    tds_mgL: float,
    p_bar: float,
    mu_ref_pa_s: float = 0.001,
    a_mu_exp: float = 0.70,
    b_mu_exp: float = 0.30,
    b_sal_slope: float = 0.25,
    compaction_k_per_bar: float = 0.003,
) -> Tuple[float, float, float]:
    mu = max(1e-6, float(mu_pa_s))
    mu_ref = max(1e-6, float(mu_ref_pa_s))
    c = max(0.0, float(tds_mgL))
    p = max(0.0, float(p_bar))

    visc_ratio = mu_ref / mu
    A_eff = max(0.0, float(A_lmh_bar_base)) * (visc_ratio ** max(0.0, float(a_mu_exp)))
    B_eff = max(0.0, float(B_lmh_base)) * (visc_ratio ** max(0.0, float(b_mu_exp)))

    # salt effect on B
    B_eff *= 1.0 + max(0.0, float(b_sal_slope)) * min(c / 35000.0, 10.0)

    # compaction at high pressure
    if p > 25.0 and compaction_k_per_bar > 0.0:
        A_eff *= math.exp(-float(compaction_k_per_bar) * (p - 25.0))

    # diffusivity scaling
    D_scale = _clamp((visc_ratio**0.8), 0.2, 5.0)
    return A_eff, B_eff, D_scale


# =============================================================================
# 5) Segment local solver (fixed-point with CP)
# =============================================================================
def solve_local_flux_constant_pressure(
    *,
    A_lmh_bar: float,
    p_seg_bar: float,
    pi_bulk_bar: float,
    k_mt_m_s: float,
    cp_exp_max: float,
    cp_max_iter: int,
    cp_rel_tol: float,
    cp_abs_tol_lmh: float,
    cp_relax: float,
    flux_init_lmh: float,
) -> Tuple[float, float, float, float]:
    """
    Return: (flux_lmh, ndp_bar, beta(CP factor), pi_wall_bar)
    """
    A = max(0.0, float(A_lmh_bar))
    if A <= 0.0:
        return 0.0, 0.0, 1.0, float(pi_bulk_bar)

    p = max(0.0, float(p_seg_bar))
    pi_bulk = max(0.0, float(pi_bulk_bar))
    k = max(1e-12, float(k_mt_m_s))

    exp_max = max(0.0, float(cp_exp_max))
    iters = max(1, int(cp_max_iter))
    rel_tol = max(0.0, float(cp_rel_tol))
    abs_tol = max(0.0, float(cp_abs_tol_lmh))
    relax = _clamp(float(cp_relax), 0.05, 0.95)

    flux = max(0.0, float(flux_init_lmh))

    for _ in range(iters):
        J_mps = flux * LMH_TO_MPS
        beta = math.exp(min(J_mps / k, exp_max))
        pi_wall = pi_bulk * beta

        ndp = p - pi_wall
        new_flux = max(0.0, A * ndp)

        diff = abs(new_flux - flux)
        if diff <= abs_tol:
            return new_flux, ndp, beta, pi_wall
        if flux > 1e-9 and (diff / max(flux, 1e-9)) <= rel_tol:
            return new_flux, ndp, beta, pi_wall

        flux = (1.0 - relax) * flux + relax * new_flux

    J_mps = flux * LMH_TO_MPS
    beta = math.exp(min(J_mps / max(1e-12, k), exp_max))
    pi_wall = pi_bulk * beta
    ndp = p - pi_wall
    return flux, ndp, beta, pi_wall


# =============================================================================
# 6) Axial stage (single pass) + debug for guideline checks
# =============================================================================
def run_axial_stage(
    *,
    temp_c: float,
    A_lmh_bar_base: float,
    B_lmh_base: float,
    area_total_m2: float,
    nseg: int,
    p_in_bar: float,
    dp_total_bar: float,
    q_in_m3h: float,
    c_in_mgL: float,
    channel_area_m2: float,
    spacer_voidage: float,
    dh_m: float,
    diffusivity_m2_s: float,
    cp_exp_max: float,
    cp_max_iter: int,
    cp_rel_tol: float,
    cp_abs_tol_lmh: float,
    cp_relax: float,
    flux_init_lmh: float,
    a_mu_exp: float,
    b_mu_exp: float,
    b_sal_slope: float,
    compaction_k_per_bar: float,
    # patch knobs
    k_mt_multiplier: float = 1.0,
    k_mt_min_m_s: float = 0.0,
) -> Tuple[float, float, float, float, float, float, float, Dict[str, Any]]:
    """
    Returns:
      (q_perm_m3h, avg_flux_lmh, avg_perm_tds_mgL, c_out_mgL, q_out_m3h,
       avg_ndp_bar, pi_wall_out_bar, debug)
    """
    nseg = max(1, int(nseg))
    area_total = max(1e-9, float(area_total_m2))
    area_seg = area_total / nseg

    p = max(0.0, float(p_in_bar))
    dp_total = max(0.0, float(dp_total_bar))
    dp_seg = dp_total / nseg

    q = max(1e-9, float(q_in_m3h))
    c = max(0.0, float(c_in_mgL))

    ch_area = max(1e-9, float(channel_area_m2))
    eps = _clamp(float(spacer_voidage), 0.30, 0.95)
    dh = max(1e-6, float(dh_m))
    D_base = max(1e-12, float(diffusivity_m2_s))

    k_mult = max(0.05, float(k_mt_multiplier))
    k_min = max(0.0, float(k_mt_min_m_s))

    sum_perm = 0.0
    sum_perm_salt = 0.0
    sum_flux_area = 0.0
    sum_ndp_area = 0.0

    flux_guess = max(0.0, float(flux_init_lmh))
    pi_wall_out = 0.0

    lead_flux: Optional[float] = None
    tail_flux: Optional[float] = None
    beta_max = 1.0
    lead_beta: Optional[float] = None
    tail_beta: Optional[float] = None

    for idx in range(nseg):
        rho, mu, pi_bulk = calc_water_properties(temp_c, c)

        # superficial velocity in feed channel
        v = (q / 3600.0) / (ch_area * eps)
        v = max(v, 0.10)

        p_mid = max(0.0, p - 0.5 * dp_seg)

        A_eff, B_eff, D_scale = effective_transport_params(
            A_lmh_bar_base=A_lmh_bar_base,
            B_lmh_base=B_lmh_base,
            mu_pa_s=mu,
            tds_mgL=c,
            p_bar=p_mid,
            a_mu_exp=a_mu_exp,
            b_mu_exp=b_mu_exp,
            b_sal_slope=b_sal_slope,
            compaction_k_per_bar=compaction_k_per_bar,
        )
        D_eff = D_base * D_scale

        k_mt = mass_transfer_coeff_m_s(
            rho_kg_m3=rho,
            mu_pa_s=mu,
            velocity_m_s=v,
            dh_m=dh,
            diffusivity_m2_s=D_eff,
        )
        k_mt *= k_mult
        if k_min > 0.0:
            k_mt = max(k_mt, k_min)

        flux_lmh, ndp_bar, beta, pi_wall = solve_local_flux_constant_pressure(
            A_lmh_bar=A_eff,
            p_seg_bar=p_mid,
            pi_bulk_bar=pi_bulk,
            k_mt_m_s=k_mt,
            cp_exp_max=cp_exp_max,
            cp_max_iter=cp_max_iter,
            cp_rel_tol=cp_rel_tol,
            cp_abs_tol_lmh=cp_abs_tol_lmh,
            cp_relax=cp_relax,
            flux_init_lmh=flux_guess,
        )
        flux_guess = max(0.0, float(flux_lmh))

        if idx == 0:
            lead_flux = float(flux_lmh)
            lead_beta = float(beta)
        tail_flux = float(flux_lmh)
        tail_beta = float(beta)
        beta_max = max(beta_max, float(beta))

        q_perm_seg = (flux_lmh * area_seg) / 1000.0
        if q_perm_seg > 0.95 * q:
            q_perm_seg = 0.95 * q

        # permeate concentration by solution-diffusion (using wall concentration)
        c_wall = c * beta
        eff_flux = max(float(flux_lmh), 1e-9)
        c_perm = (B_eff * c_wall) / (eff_flux + B_eff) if B_eff > 0.0 else 0.0
        c_perm = _clamp(c_perm, 0.0, c_wall)

        q_out = max(1e-9, q - q_perm_seg)
        salt_in = q * c
        salt_perm = q_perm_seg * c_perm
        salt_out = max(0.0, salt_in - salt_perm)
        c_out = salt_out / q_out

        sum_perm += q_perm_seg
        sum_perm_salt += q_perm_seg * c_perm
        sum_flux_area += flux_lmh * area_seg
        sum_ndp_area += ndp_bar * area_seg

        q = q_out
        c = max(0.0, c_out)
        p = max(0.0, p - dp_seg)

        pi_wall_out = float(pi_wall)

    q_perm = max(0.0, sum_perm)
    avg_flux = (sum_flux_area / area_total) if area_total > 0 else 0.0
    avg_perm_tds = (sum_perm_salt / q_perm) if q_perm > 1e-12 else 0.0
    avg_ndp = (sum_ndp_area / area_total) if area_total > 0 else 0.0

    debug = {
        "lead_flux_lmh": lead_flux,
        "tail_flux_lmh": tail_flux,
        "beta_max": beta_max,
        "lead_beta": lead_beta,
        "tail_beta": tail_beta,
        "k_mt_multiplier": k_mult,
        "k_mt_min_m_s": (k_min if k_min > 0.0 else None),
        "nseg": int(nseg),
    }

    return q_perm, avg_flux, avg_perm_tds, c, q, avg_ndp, pi_wall_out, debug


def solve_inlet_pressure_for_target_avg_flux(
    *,
    target_flux_lmh: float,
    p_limit_bar: float,
    axial_kwargs: dict,
    tol_lmh: float = 0.03,
    max_iter: int = 30,
) -> Tuple[
    float, Tuple[float, float, float, float, float, float, float, Dict[str, Any]]
]:
    """
    Bisection on p_in to match avg flux.
    Returns: (p_in_used, axial_result_tuple)
    """
    target = max(0.0, float(target_flux_lmh))
    p_low = 0.0
    p_high = max(0.0, float(p_limit_bar))

    ax_low = run_axial_stage(p_in_bar=p_low, **axial_kwargs)
    ax_high = run_axial_stage(p_in_bar=p_high, **axial_kwargs)

    f_low = ax_low[1] - target
    f_high = ax_high[1] - target

    if f_high < 0.0:
        return p_high, ax_high
    if f_low >= 0.0:
        return p_low, ax_low

    best_p = p_high
    best_ax = ax_high
    best_err = abs(f_high)

    for _ in range(max(1, int(max_iter))):
        p_mid = 0.5 * (p_low + p_high)
        ax_mid = run_axial_stage(p_in_bar=p_mid, **axial_kwargs)
        f_mid = ax_mid[1] - target
        err = abs(f_mid)

        if err < best_err:
            best_p, best_ax, best_err = p_mid, ax_mid, err

        if err <= tol_lmh:
            return p_mid, ax_mid

        if f_mid < 0.0:
            p_low = p_mid
        else:
            p_high = p_mid

    return best_p, best_ax


# =============================================================================
# 7) Scaling indices (LSI/RSI) - optional
# =============================================================================
def _to_float(v: Any) -> Optional[float]:
    try:
        if v is None:
            return None
        return float(v)
    except Exception:
        return None


def calc_lsi_rsi(
    *,
    ph: Optional[float],
    temp_c: Optional[float],
    tds_mgL: Optional[float],
    calcium_hardness_mgL_as_CaCO3: Optional[float],
    alkalinity_mgL_as_CaCO3: Optional[float],
) -> Tuple[Optional[float], Optional[float]]:
    ph = _to_float(ph)
    T = _to_float(temp_c)
    tds = _to_float(tds_mgL)
    Ca = _to_float(calcium_hardness_mgL_as_CaCO3)
    Alk = _to_float(alkalinity_mgL_as_CaCO3)

    if ph is None or T is None or tds is None or Ca is None or Alk is None:
        return None, None

    tds = max(tds, 1.0)
    Ca = max(Ca, 1.0)
    Alk = max(Alk, 1.0)

    A = (math.log10(tds) - 1.0) / 10.0
    B = -13.12 * math.log10(T + 273.15) + 34.55
    C = math.log10(Ca) - 0.4
    D = math.log10(Alk)
    pHs = (9.3 + A + B) - (C + D)

    lsi = ph - pHs
    rsi = 2.0 * pHs - ph
    return lsi, rsi


def extract_chemistry_obj(config: Any, feed: Any) -> Optional[Any]:
    return getattr(config, "chemistry", None) or getattr(feed, "chemistry", None)


def read_chem_field(chem: Any, key: str) -> Optional[float]:
    if chem is None:
        return None
    if isinstance(chem, dict):
        return _to_float(chem.get(key))
    return _to_float(getattr(chem, key, None))


# =============================================================================
# 8) HRRO Module
# =============================================================================
def build_hrro_batch_cycle_history(
    *,
    TimeSeriesPoint,
    config: Any,
    qf_total: float,
    rec_pct_final: float,
    p_bar: float,
    cf0_mgL: float,
    total_area_m2: float,
    cp_mgL: Optional[float],
    ndp_bar: Optional[float],
    npts_fallback: int = 25,
) -> List["TimeSeriesPoint"]:
    """
    HRRO batch-cycle chart용 time_history 생성(최소 2포인트 보장).
    - config.max_minutes / config.timestep_s 사용(없으면 fallback)
    - recovery 0 -> 최종 recovery로 선형 증가
    - TDS는 단순 농축 모델(Cf/(1-R))로 증가
    """
    rec_final = max(0.0, float(rec_pct_final))
    qf = max(0.0, float(qf_total))
    cf0 = max(0.0, float(cf0_mgL))
    area = max(1e-9, float(total_area_m2))

    max_minutes = _f(getattr(config, "max_minutes", None), 60.0)
    max_minutes = max(1.0, float(max_minutes))

    timestep_s = _f(getattr(config, "timestep_s", None), 60.0)
    dt_min = max(0.1, float(timestep_s) / 60.0)

    # 포인트 수 결정
    n = int(round(max_minutes / dt_min)) + 1
    if n < 2:
        n = 2
    if n > 400:
        n = 400

    # max/timestep이 의미 없으면 fallback으로 보정
    if not (2 <= n <= 400):
        n = max(2, int(npts_fallback))

    pts: List["TimeSeriesPoint"] = []
    for i in range(n):
        frac = i / (n - 1) if n > 1 else 1.0
        t = max_minutes * frac
        r = rec_final * frac

        # 농축(폭주 방지)
        denom = max(1e-6, 1.0 - (r / 100.0))
        cf_bulk = min(cf0 / denom, 2_000_000.0)

        # pseudo permeate flow (차트용; 선형 증가)
        qp = qf * (r / 100.0)

        flux = (qp * 1000.0) / area if area > 0 else 0.0

        pts.append(
            TimeSeriesPoint(
                time_min=round(t, 3),
                recovery_pct=round(r, 3),
                pressure_bar=round(float(p_bar), 3),
                tds_mgL=round(float(cf_bulk), 3),
                flux_lmh=round(float(flux), 3),
                ndp_bar=(round(float(ndp_bar), 3) if ndp_bar is not None else None),
                permeate_flow_m3h=round(float(qp), 6),
                permeate_tds_mgL=(
                    round(float(cp_mgL), 3) if cp_mgL is not None else None
                ),
            )
        )
    return pts


class HRROModule(SimulationModule):
    def compute(self, config: "StageConfig", feed: "FeedInput") -> "StageMetric":
        from app.schemas.simulation import StageMetric, TimeSeriesPoint
        from app.schemas.common import ModuleType
        from app.schemas.simulation import HRROMassTransferIn, HRROSpacerIn

        # ------------------------------------------------------------
        # A) Resolve Excel inputs from StageConfig / FeedInput
        # ------------------------------------------------------------
        hrro_engine = (
            (getattr(config, "hrro_engine", None) or "excel_only").strip().lower()
        )
        hrro_engine = (
            "excel_physics" if hrro_engine == "excel_physics" else "excel_only"
        )

        vessel_count = max(1, _i(getattr(config, "vessel_count", None), 1))

        elements_per_vessel = getattr(config, "elements_per_vessel", None)
        if elements_per_vessel is None:
            # fall back to legacy total elements
            elements_per_vessel = _i(getattr(config, "elements", None), 6)
        elements_per_vessel = max(1, int(elements_per_vessel))

        area_m2_per_element = getattr(config, "membrane_area_m2_per_element", None)
        if area_m2_per_element is None:
            area_m2_per_element = getattr(config, "membrane_area_m2", None)
        area_m2_per_element = max(1e-9, _f(area_m2_per_element, 37.0))

        q_raw_m3h = getattr(config, "feed_flow_m3h", None)
        if q_raw_m3h is None:
            q_raw_m3h = getattr(feed, "flow_m3h", None)
        q_raw_m3h = max(1e-9, _f(q_raw_m3h, 0.0))

        ccro_rec = getattr(config, "ccro_recovery_pct", None)
        if ccro_rec is None:
            ccro_rec = (
                getattr(config, "stop_recovery_pct", None)
                or getattr(config, "recovery_target_pct", None)
                or 85.0
            )
        ccro_rec = _clamp(_f(ccro_rec, 85.0), 0.0, 100.0)

        pf_feed_ratio = _f(getattr(config, "pf_feed_ratio_pct", None), 110.0)

        pf_recovery = _clamp(
            _f(getattr(config, "pf_recovery_pct", None), 10.0), 0.0, 100.0
        )

        cc_recycle_m3h_per_pv = getattr(config, "cc_recycle_m3h_per_pv", None)
        if cc_recycle_m3h_per_pv is None:
            recirc_total = _f(getattr(config, "recirc_flow_m3h", None), 0.0)
            cc_recycle_m3h_per_pv = (
                (recirc_total / vessel_count) if vessel_count > 0 else recirc_total
            )
        cc_recycle_m3h_per_pv = max(0.0, _f(cc_recycle_m3h_per_pv, 0.0))

        excel_in = ExcelInputs(
            q_raw_m3h=q_raw_m3h,
            ccro_recovery_pct=ccro_rec,
            pf_feed_ratio_pct=pf_feed_ratio,
            pf_recovery_pct=pf_recovery,
            cc_recycle_m3h_per_pv=cc_recycle_m3h_per_pv,
            vessel_count=vessel_count,
            elements_per_vessel=elements_per_vessel,
            area_m2_per_element=area_m2_per_element,
        )
        excel = compute_excel(excel_in)

        qf_total = q_raw_m3h
        qp_excel = excel.ccro_qp_m3h
        qc_excel = excel.ccro_qc_m3h
        flux_excel = excel.ccro_flux_lmh

        temp_c = _f(getattr(feed, "temperature_C", None), 25.0)
        cf = max(0.0, _f(getattr(feed, "tds_mgL", None), 0.0))

        p_in_bar = _f(
            getattr(config, "pressure_bar", None),
            _f(getattr(feed, "pressure_bar", None), 0.0),
        )
        p_in_bar = max(0.0, float(p_in_bar))

        element_inch = getattr(config, "element_inch", None)
        if element_inch is None:
            element_inch = infer_element_inch(area_m2_per_element)
        element_inch = int(element_inch)

        stage_no = _i(
            (
                getattr(config, "stage", None)
                or getattr(config, "stage_no", None)
                or getattr(config, "stage_index", None)
            ),
            1,
        )

        # ------------------------------------------------------------
        # B) Excel-only mode
        # ------------------------------------------------------------
        if hrro_engine == "excel_only":
            rec_pct = (qp_excel / qf_total) * 100.0 if qf_total > 0 else 0.0

            # hydraulics (for guideline dp check)
            mt: HRROMassTransferIn = (
                getattr(config, "mass_transfer", None) or HRROMassTransferIn()
            )
            channel_area_m2 = max(
                1e-9, _f(getattr(mt, "feed_channel_area_m2", None), 0.015)
            )

            sp: HRROSpacerIn = getattr(config, "spacer", None) or HRROSpacerIn()
            sp_h_m = _f(getattr(sp, "thickness_mm", None), 0.76) / 1000.0
            sp_eps = getattr(sp, "voidage", None)
            sp_eps = _f(sp_eps, _f(getattr(sp, "voidage_fallback", None), 0.85))
            sp_eps = _clamp(sp_eps, 0.30, 0.95)
            dh_m = getattr(sp, "hydraulic_diameter_m", None)
            dh_m = (
                float(dh_m) if dh_m is not None else hydraulic_diameter(sp_h_m, sp_eps)
            )

            elem_length_m = max(
                0.2, _f(getattr(config, "hrro_elem_length_m", None), 1.0)
            )
            spacer_fric_mult = max(
                1.0, _f(getattr(config, "hrro_spacer_friction_multiplier", None), 5.0)
            )

            q_feed_per_pv = qf_total / vessel_count
            q_in_per_pv = cc_recycle_m3h_per_pv + q_feed_per_pv

            rho0, mu0, _pi0 = calc_water_properties(temp_c, cf)
            v0 = (q_in_per_pv / 3600.0) / (channel_area_m2 * sp_eps)
            v0 = max(v0, 0.10)
            L_total = elements_per_vessel * elem_length_m

            dp_total = pressure_drop_spacer_bar(
                rho_kg_m3=rho0,
                mu_pa_s=mu0,
                velocity_m_s=v0,
                dh_m=dh_m,
                length_m=L_total,
                spacer_friction_multiplier=spacer_fric_mult,
            )

            # Cp 옵션화
            cp_mode = getattr(config, "hrro_excel_only_cp_mode", None) or "min_model"
            fixed_rej = _f(
                getattr(config, "hrro_excel_only_fixed_rejection_pct", None), 99.5
            )
            min_rej = getattr(config, "hrro_excel_only_min_model_rejection_pct", None)

            # fallback rejection: membrane_salt_rejection_pct -> default 99.63 (to reproduce old min_model baseline)
            fallback_rej = _f(
                getattr(config, "membrane_salt_rejection_pct", None), 99.63
            )

            cp_out, cc_out, cp_dbg = excel_only_compute_cp_cc(
                cf_mgL=cf,
                qf_m3h=qf_total,
                qp_m3h=qp_excel,
                qc_m3h=qc_excel,
                cp_mode=str(cp_mode),
                fixed_rejection_pct=fixed_rej,
                min_model_rejection_pct=min_rej,
                fallback_rejection_pct=fallback_rej,
            )

            # guideline selection
            profile, reason = choose_guideline_profile(
                water_type=getattr(feed, "water_type", None),
                water_subtype=getattr(feed, "water_subtype", None),
                sdi15=getattr(feed, "sdi15", None),
                tds_mgL=cf,
            )

            checks = {
                "avg_flux_lmh": flux_excel,
                "lead_flux_lmh": None,
                "conc_flow_m3h_per_vessel": (
                    (qc_excel / vessel_count) if vessel_count > 0 else None
                ),
                "feed_flow_m3h_per_vessel": (
                    (qf_total / vessel_count) if vessel_count > 0 else None
                ),
                "dp_bar_per_vessel": dp_total,
                "element_recovery_pct": (
                    (rec_pct / elements_per_vessel) if elements_per_vessel > 0 else None
                ),
                "beta_max": None,
                "flux_decline_ratio_pct": None,
            }
            guideline_used, violations = build_guideline_violations(
                profile=profile, inch=element_inch, checks=checks
            )

            history = build_hrro_batch_cycle_history(
                TimeSeriesPoint=TimeSeriesPoint,
                config=config,
                qf_total=qf_total,
                rec_pct_final=rec_pct,
                p_bar=p_in_bar,
                cf0_mgL=cf,
                total_area_m2=excel.total_area_m2,
                cp_mgL=(float(cp_out) if cp_out is not None else None),
                ndp_bar=None,
            )

            chem_out: Dict[str, Any] = {
                "design_excel": {
                    "inputs": {
                        "q_raw_m3h": q_raw_m3h,
                        "ccro_recovery_pct": ccro_rec,
                        "pf_feed_ratio_pct": pf_feed_ratio,
                        "pf_recovery_pct": pf_recovery,
                        "cc_recycle_m3h_per_pv": cc_recycle_m3h_per_pv,
                        "vessel_count": vessel_count,
                        "elements_per_vessel": elements_per_vessel,
                        "area_m2_per_element": area_m2_per_element,
                    },
                    "ccro": {
                        "q_feed_m3h": qf_total,
                        "q_perm_m3h": qp_excel,
                        "q_conc_m3h": qc_excel,
                        "flux_lmh": flux_excel,
                    },
                    "pf": {
                        "q_feed_m3h": excel.pf_feed_m3h,
                        "q_perm_m3h": excel.pf_qp_m3h,
                        "q_conc_m3h": excel.pf_qc_m3h,
                        "flux_lmh": excel.pf_flux_lmh,
                        "cc_feed_m3h": excel.cc_feed_m3h,
                    },
                    "cc": {
                        "blend_feed_m3h_per_pv": excel.cc_blend_feed_m3h_per_pv,
                        "q_perm_m3h_per_pv": excel.cc_qp_m3h_per_pv,
                        "q_conc_m3h_per_pv": excel.cc_qc_m3h_per_pv,
                        "recovery_pct": excel.cc_recovery_pct,
                        "flux_lmh": excel.cc_flux_lmh,
                    },
                    "membrane": {
                        "total_elements": excel.total_elements,
                        "total_area_m2": excel.total_area_m2,
                    },
                    "excel_only_cp": cp_dbg,
                    "hydraulics": {
                        "channel_area_m2": channel_area_m2,
                        "spacer_voidage": sp_eps,
                        "hydraulic_diameter_m": dh_m,
                        "elem_length_m": elem_length_m,
                        "spacer_friction_multiplier": spacer_fric_mult,
                        "q_in_m3h_per_pv": q_in_per_pv,
                        "velocity_m_s": v0,
                        "dp_bar_per_vessel": dp_total,
                    },
                },
                "guideline": {**guideline_used, "profile_reason": reason},
                "guideline_checks": checks,
                "violations": violations,
            }

            return StageMetric(
                stage=stage_no,
                module_type=ModuleType.HRRO,
                recovery_pct=round(rec_pct, 2),
                net_recovery_pct=round(
                    (qp_excel / max(qp_excel + qc_excel, 1e-12)) * 100.0, 2
                ),
                flux_lmh=round(flux_excel, 3),
                sec_kwhm3=0.0,
                ndp_bar=None,
                p_in_bar=round(p_in_bar, 3),
                p_out_bar=round(max(0.0, p_in_bar - dp_total), 3),
                delta_pi_bar=None,
                Qf=round(qf_total, 6),
                Qp=round(qp_excel, 6),
                Qc=round(qc_excel, 6),
                Cf=round(cf, 3),
                Cp=(round(float(cp_out), 3) if cp_out is not None else None),
                Cc=(round(float(cc_out), 3) if cc_out is not None else None),
                time_history=history,
                chemistry=chem_out,
            )

        # ------------------------------------------------------------
        # C) excel_physics: target flux -> solve inlet pressure with CP/ΔP/SEC
        # ------------------------------------------------------------
        A0 = _f(getattr(config, "membrane_A_lmh_bar", None), 1.2)
        B0 = _f(getattr(config, "membrane_B_lmh", None), 0.1)
        A_base, B_base = correct_membrane_params(A0, B0, temp_c)
        A_base = max(0.0, A_base)
        B_base = max(0.0, B_base)

        mt: HRROMassTransferIn = (
            getattr(config, "mass_transfer", None) or HRROMassTransferIn()
        )
        cp_exp_max = _f(getattr(mt, "cp_exp_max", None), 5.0)
        cp_rel_tol = _f(getattr(mt, "cp_rel_tol", None), 1e-4)
        cp_abs_tol_lmh = _f(getattr(mt, "cp_abs_tol_lmh", None), 1e-3)
        cp_relax = _f(getattr(mt, "cp_relax", None), 0.5)
        cp_max_iter = _i(getattr(mt, "cp_max_iter", None), 30)
        diffusivity = _f(getattr(mt, "diffusivity_m2_s", None), 1.5e-9)

        channel_area_m2 = max(
            1e-9, _f(getattr(mt, "feed_channel_area_m2", None), 0.015)
        )

        sp: HRROSpacerIn = getattr(config, "spacer", None) or HRROSpacerIn()
        sp_h_m = _f(getattr(sp, "thickness_mm", None), 0.76) / 1000.0
        sp_eps = getattr(sp, "voidage", None)
        sp_eps = _f(sp_eps, _f(getattr(sp, "voidage_fallback", None), 0.85))
        sp_eps = _clamp(sp_eps, 0.30, 0.95)
        dh_m = getattr(sp, "hydraulic_diameter_m", None)
        dh_m = float(dh_m) if dh_m is not None else hydraulic_diameter(sp_h_m, sp_eps)

        elem_length_m = max(0.2, _f(getattr(config, "hrro_elem_length_m", None), 1.0))
        spacer_fric_mult = max(
            1.0, _f(getattr(config, "hrro_spacer_friction_multiplier", None), 5.0)
        )

        a_mu_exp = _f(getattr(config, "hrro_A_mu_exp", None), 0.70)
        b_mu_exp = _f(getattr(config, "hrro_B_mu_exp", None), 0.30)
        b_sal_slope = _f(getattr(config, "hrro_B_sal_slope", None), 0.25)
        comp_k = _f(getattr(config, "hrro_A_compaction_k", None), 0.003)

        # num segments (default 1)
        nseg = getattr(config, "hrro_num_segments", None)
        if nseg is None:
            nseg = getattr(mt, "segments_total", None)
        if nseg is None:
            nseg = 1
        nseg = max(1, int(nseg))

        # pressure limit (upper bound for bisection)
        p_limit_bar = getattr(config, "hrro_pressure_limit_bar", None)
        if p_limit_bar is None:
            p_limit_bar = getattr(config, "pressure_bar", None)
        p_limit_bar = max(1.0, _f(p_limit_bar, 60.0))

        pump_eff = _clamp(_f(getattr(config, "pump_eff", None), 0.80), 0.20, 0.95)

        target_flux = getattr(config, "flux_lmh", None)
        if target_flux is None:
            target_flux = flux_excel
        target_flux = max(0.0, float(target_flux))

        k_mt_multiplier = getattr(config, "hrro_k_mt_multiplier", None)
        if k_mt_multiplier is None:
            k_mt_multiplier = getattr(mt, "k_mt_multiplier", None)
        k_mt_multiplier = _f(k_mt_multiplier, 0.5)

        k_mt_min_m_s = getattr(config, "hrro_k_mt_min_m_s", None)
        if k_mt_min_m_s is None:
            k_mt_min_m_s = getattr(mt, "k_mt_min_m_s", None)
        k_mt_min_m_s = _f(k_mt_min_m_s, 0.0)

        area_per_pv = area_m2_per_element * elements_per_vessel
        q_feed_per_pv = qf_total / vessel_count
        q_in_per_pv = max(1e-9, cc_recycle_m3h_per_pv + q_feed_per_pv)

        rho0, mu0, _pi0 = calc_water_properties(temp_c, cf)
        v0 = (q_in_per_pv / 3600.0) / (channel_area_m2 * sp_eps)
        v0 = max(v0, 0.10)
        L_total = elements_per_vessel * elem_length_m

        dp_total = pressure_drop_spacer_bar(
            rho_kg_m3=rho0,
            mu_pa_s=mu0,
            velocity_m_s=v0,
            dh_m=dh_m,
            length_m=L_total,
            spacer_friction_multiplier=spacer_fric_mult,
        )

        axial_kwargs = dict(
            temp_c=temp_c,
            A_lmh_bar_base=A_base,
            B_lmh_base=B_base,
            area_total_m2=area_per_pv,
            nseg=nseg,
            dp_total_bar=dp_total,
            q_in_m3h=q_in_per_pv,
            c_in_mgL=cf,
            channel_area_m2=channel_area_m2,
            spacer_voidage=sp_eps,
            dh_m=dh_m,
            diffusivity_m2_s=diffusivity,
            cp_exp_max=cp_exp_max,
            cp_max_iter=cp_max_iter,
            cp_rel_tol=cp_rel_tol,
            cp_abs_tol_lmh=cp_abs_tol_lmh,
            cp_relax=cp_relax,
            flux_init_lmh=target_flux,
            a_mu_exp=a_mu_exp,
            b_mu_exp=b_mu_exp,
            b_sal_slope=b_sal_slope,
            compaction_k_per_bar=comp_k,
            k_mt_multiplier=k_mt_multiplier,
            k_mt_min_m_s=k_mt_min_m_s,
        )

        p_in_used, axial_res = solve_inlet_pressure_for_target_avg_flux(
            target_flux_lmh=target_flux,
            p_limit_bar=p_limit_bar,
            axial_kwargs=axial_kwargs,
            tol_lmh=0.03,
            max_iter=28,
        )

        (
            q_perm_per_pv,
            flux_avg_pv,
            perm_tds_avg,
            c_out_mgL,
            _q_out_m3h,
            ndp_avg_bar,
            pi_wall_out,
            debug,
        ) = axial_res

        # ------------------------------------------------------------
        # IMPORTANT:
        # - Default: keep Excel baseline Qp/Qc/Flux for system mass balance
        # - If user explicitly provided config.flux_lmh: allow flux override
        #   => Qp = flux * total_area (with clamp Qp <= 0.999*Qf)
        # ------------------------------------------------------------
        user_flux_lmh = getattr(config, "flux_lmh", None)
        flow_mode = "excel_baseline" if user_flux_lmh is None else "flux_override"

        qp_total_clamped = False
        qp_total_from_flux = None

        if user_flux_lmh is None:
            # Excel baseline outputs (net product/brine)
            qp_total = max(0.0, float(qp_excel))
            qc_total = max(0.0, float(qc_excel))
        else:
            # Flux override: Qp derived from installed area
            qp_total_from_flux = max(
                0.0, (float(target_flux) * max(excel.total_area_m2, 1e-9)) / 1000.0
            )
            qp_total = float(qp_total_from_flux)
            # enforce mass balance (avoid negative brine)
            qp_limit = 0.999 * max(qf_total, 0.0)
            if qp_total > qp_limit:
                qp_total = qp_limit
                qp_total_clamped = True
            qc_total = max(0.0, float(qf_total) - float(qp_total))

        # achieved flux on total installed area (consistent with reported Qp)
        flux_ach = (float(qp_total) * 1000.0) / max(excel.total_area_m2, 1e-9)

        p_out = max(0.0, p_in_used - dp_total)

        q_hp_total = q_in_per_pv * vessel_count
        sec = ((q_hp_total * p_in_used) / 36.0 / pump_eff) / max(qp_total, 1e-12)

        rec_pct = (qp_total / qf_total) * 100.0 if qf_total > 0 else 0.0

        profile, reason = choose_guideline_profile(
            water_type=getattr(feed, "water_type", None),
            water_subtype=getattr(feed, "water_subtype", None),
            sdi15=getattr(feed, "sdi15", None),
            tds_mgL=cf,
        )

        lead_flux = debug.get("lead_flux_lmh")
        tail_flux = debug.get("tail_flux_lmh")
        fdr = None
        if lead_flux is not None and tail_flux is not None and float(lead_flux) > 1e-9:
            fdr = (1.0 - (float(tail_flux) / float(lead_flux))) * 100.0

        checks = {
            "avg_flux_lmh": flux_ach,
            "lead_flux_lmh": lead_flux,
            "conc_flow_m3h_per_vessel": (
                (qc_total / vessel_count) if vessel_count > 0 else None
            ),
            "feed_flow_m3h_per_vessel": (
                (qf_total / vessel_count) if vessel_count > 0 else None
            ),
            "dp_bar_per_vessel": dp_total,
            "element_recovery_pct": (
                (rec_pct / elements_per_vessel) if elements_per_vessel > 0 else None
            ),
            "beta_max": debug.get("beta_max"),
            "flux_decline_ratio_pct": fdr,
        }
        guideline_used, violations = build_guideline_violations(
            profile=profile, inch=element_inch, checks=checks
        )

        chem = extract_chemistry_obj(config, feed)
        chem_out: Dict[str, Any] = {
            "design_excel": {
                "inputs": {
                    "q_raw_m3h": q_raw_m3h,
                    "ccro_recovery_pct": ccro_rec,
                    "pf_feed_ratio_pct": pf_feed_ratio,
                    "pf_recovery_pct": pf_recovery,
                    "cc_recycle_m3h_per_pv": cc_recycle_m3h_per_pv,
                    "vessel_count": vessel_count,
                    "elements_per_vessel": elements_per_vessel,
                    "area_m2_per_element": area_m2_per_element,
                },
                "ccro": {
                    "q_feed_m3h": qf_total,
                    "q_perm_m3h": qp_excel,
                    "q_conc_m3h": qc_excel,
                    "flux_lmh": flux_excel,
                },
                "pf": {
                    "q_feed_m3h": excel.pf_feed_m3h,
                    "q_perm_m3h": excel.pf_qp_m3h,
                    "q_conc_m3h": excel.pf_qc_m3h,
                    "flux_lmh": excel.pf_flux_lmh,
                    "cc_feed_m3h": excel.cc_feed_m3h,
                },
                "cc": {
                    "blend_feed_m3h_per_pv": excel.cc_blend_feed_m3h_per_pv,
                    "q_perm_m3h_per_pv": excel.cc_qp_m3h_per_pv,
                    "q_conc_m3h_per_pv": excel.cc_qc_m3h_per_pv,
                    "recovery_pct": excel.cc_recovery_pct,
                    "flux_lmh": excel.cc_flux_lmh,
                },
                "membrane": {
                    "total_elements": excel.total_elements,
                    "total_area_m2": excel.total_area_m2,
                },
                "physics": {
                    "target_flux_lmh": target_flux,
                    "achieved_flux_lmh": flux_ach,
                    "p_in_bar": p_in_used,
                    "p_out_bar": p_out,
                    "dp_bar": dp_total,
                    "ndp_bar": ndp_avg_bar,
                    "sec_kwhm3": sec,
                    "pump_eff": pump_eff,
                    "flow_mode": flow_mode,
                    "qp_total_m3h": float(qp_total),
                    "qc_total_m3h": float(qc_total),
                    "qp_total_from_flux_m3h": (
                        float(qp_total_from_flux)
                        if qp_total_from_flux is not None
                        else None
                    ),
                    "qp_total_clamped": qp_total_clamped,
                    "q_perm_model_m3h_per_pv": float(q_perm_per_pv),
                    "k_mt_multiplier": k_mt_multiplier,
                    "k_mt_min_m_s": (k_mt_min_m_s if k_mt_min_m_s > 0 else None),
                    "nseg": nseg,
                    "pressure_limit_bar": p_limit_bar,
                    "hydraulics": {
                        "channel_area_m2": channel_area_m2,
                        "spacer_voidage": sp_eps,
                        "hydraulic_diameter_m": dh_m,
                        "elem_length_m": elem_length_m,
                        "spacer_friction_multiplier": spacer_fric_mult,
                        "q_in_m3h_per_pv": q_in_per_pv,
                        "velocity_m_s": v0,
                    },
                    "debug": debug,
                },
            },
            "guideline": {**guideline_used, "profile_reason": reason},
            "guideline_checks": checks,
            "violations": violations,
        }

        if chem is not None:
            alk = read_chem_field(chem, "alkalinity_mgL_as_CaCO3")
            ca = read_chem_field(chem, "calcium_hardness_mgL_as_CaCO3")
            lsi_f, rsi_f = calc_lsi_rsi(
                ph=getattr(feed, "ph", None),
                temp_c=temp_c,
                tds_mgL=cf,
                calcium_hardness_mgL_as_CaCO3=ca,
                alkalinity_mgL_as_CaCO3=alk,
            )
            lsi_b, rsi_b = calc_lsi_rsi(
                ph=getattr(feed, "ph", None),
                temp_c=temp_c,
                tds_mgL=c_out_mgL,
                calcium_hardness_mgL_as_CaCO3=ca,
                alkalinity_mgL_as_CaCO3=alk,
            )
            chem_out["scaling"] = {
                "feed": {"lsi": lsi_f, "rsi": rsi_f},
                "final_brine": {"lsi": lsi_b, "rsi": rsi_b},
            }

        history = build_hrro_batch_cycle_history(
            TimeSeriesPoint=TimeSeriesPoint,
            config=config,
            qf_total=qf_total,
            rec_pct_final=rec_pct,
            p_bar=p_in_used,
            cf0_mgL=cf,
            total_area_m2=excel.total_area_m2,
            cp_mgL=float(perm_tds_avg),
            ndp_bar=float(ndp_avg_bar),
        )

        return StageMetric(
            stage=stage_no,
            module_type=ModuleType.HRRO,
            recovery_pct=round(rec_pct, 2),
            net_recovery_pct=round(
                (qp_total / max(qp_total + qc_total, 1e-12)) * 100.0, 2
            ),
            flux_lmh=round(flux_ach, 3),
            sec_kwhm3=round(sec, 3),
            ndp_bar=round(float(ndp_avg_bar), 3),
            p_in_bar=round(float(p_in_used), 3),
            p_out_bar=round(float(p_out), 3),
            delta_pi_bar=round(float(pi_wall_out), 3),
            Qf=round(qf_total, 6),
            Qp=round(qp_total, 6),
            Qc=round(qc_total, 6),
            Cf=round(cf, 3),
            Cp=round(float(perm_tds_avg), 3),
            Cc=round(float(c_out_mgL), 3),
            time_history=history,
            chemistry=chem_out,
        )
