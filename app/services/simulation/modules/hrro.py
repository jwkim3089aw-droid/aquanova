# app/services/simulation/modules/hrro.py

from __future__ import annotations
import math
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

from app.services.simulation.modules.base import SimulationModule
from app.services.membranes import get_params_from_options
from app.services.water_chemistry import (
    ChemistryProfile,
    scale_profile_for_tds,
    calculate_osmotic_pressure_bar,
    calc_scaling_indices,
)

from app.data.membranes import MEMBRANES

if TYPE_CHECKING:
    from app.schemas.simulation import (
        StageConfig,
        FeedInput,
        StageMetric,
        TimeSeriesPoint,
    )

LMH_TO_MPS = 1e-3 / 3600.0
PA_TO_BAR = 1.0 / 1e5


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
    wt_l = str(water_type).strip().lower() if water_type is not None else ""
    sub = _norm(water_subtype)
    sdi = float(sdi15) if sdi15 is not None else None

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
    *, profile: str, inch: int, checks: Dict[str, Optional[float]]
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    g = (GUIDELINES.get(profile, {}) or {}).get(inch)
    if g is None:
        profile = "municipal Supply"
        g = (GUIDELINES.get(profile, {}) or {}).get(inch) or {}

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

    qc = checks.get("conc_flow_m3h_per_vessel")
    qc_min = g.get("conc_flow_min_m3h_per_vessel")
    if qc is not None and qc_min is not None and float(qc) + 1e-12 < float(qc_min):
        v_fail(
            "conc_flow_min",
            f"Concentrate flow/vessel {qc:.6f} m3/h is below guideline min {qc_min}",
            float(qc),
            float(qc_min),
            "m3/h",
        )

    qf = checks.get("feed_flow_m3h_per_vessel")
    qf_max = g.get("feed_flow_max_m3h_per_vessel")
    if qf is not None and qf_max is not None and float(qf) > float(qf_max) + 1e-9:
        v_fail(
            "feed_flow_max",
            f"Feed flow/vessel {qf:.6f} m3/h exceeds max {qf_max}",
            float(qf),
            float(qf_max),
            "m3/h",
        )

    return {"profile": profile, "element_inch": inch, "limits": g}, violations


def extract_chemistry_profile(feed: Any) -> ChemistryProfile:
    chem_data = getattr(feed, "chemistry", {}) or {}
    if not isinstance(chem_data, dict):
        if hasattr(chem_data, "model_dump"):
            chem_data = chem_data.model_dump()
        elif hasattr(chem_data, "dict"):
            chem_data = chem_data.dict()
        else:
            chem_data = {}

    def _g(key: str) -> float:
        val = chem_data.get(key)
        try:
            return float(val) if val is not None else 0.0
        except:
            return 0.0

    return ChemistryProfile(
        tds_mgL=_f(getattr(feed, "tds_mgL", None), 0.0),
        temperature_C=_f(getattr(feed, "temperature_C", None), 25.0),
        ph=_f(getattr(feed, "ph", None), 7.0),
        na_mgL=_g("na"),
        k_mgL=_g("k"),
        ca_mgL=_g("ca"),
        mg_mgL=_g("mg"),
        nh4_mgL=_g("nh4"),
        sr_mgL=_g("sr"),
        ba_mgL=_g("ba"),
        fe_mgL=_g("fe"),
        mn_mgL=_g("mn"),
        al_mgL=_g("al"),
        cl_mgL=_g("cl"),
        so4_mgL=_g("so4"),
        hco3_mgL=_g("hco3"),
        no3_mgL=_g("no3"),
        f_mgL=_g("f"),
        br_mgL=_g("br"),
        po4_mgL=_g("po4"),
        co3_mgL=_g("co3"),
        sio2_mgL=_g("sio2"),
        b_mgL=_g("b"),
        co2_mgL=_g("co2"),
        alkalinity_mgL_as_CaCO3=_g("alkalinity_mgL_as_CaCO3"),
        calcium_hardness_mgL_as_CaCO3=_g("calcium_hardness_mgL_as_CaCO3"),
    )


def calc_water_properties_from_chemistry(
    profile: ChemistryProfile,
) -> Tuple[float, float, float]:
    t = _clamp(float(profile.temperature_C), 5.0, 45.0)
    tds = max(0.0, float(profile.tds_mgL))

    rho = 1000.0 + (tds / 1000.0) * 0.75
    mu_pure = 2.414e-5 * 10 ** (247.8 / (t + 133.15))
    mu = mu_pure * (1.0 + 0.0015 * (tds / 1000.0))

    base_pi = calculate_osmotic_pressure_bar(profile)

    thermo_phi = 1.0 + (0.15 * (tds / 100000.0))

    final_pi = max(0.0, base_pi * thermo_phi)
    return rho, mu, final_pi


def correct_membrane_params(
    A0_lmh_bar: float, B0_lmh: float, temp_c: float
) -> Tuple[float, float]:
    dt = float(temp_c) - 25.0
    return float(A0_lmh_bar) * math.exp(0.027 * dt), float(B0_lmh) * math.exp(
        0.050 * dt
    )


def hydraulic_diameter(spacer_thickness_m: float, voidage: float) -> float:
    h = max(1e-6, float(spacer_thickness_m))
    eps = _clamp(float(voidage), 0.30, 0.95)
    return max(2.0 * h * eps / (2.0 - eps), 1e-6)


def friction_factor_schock_miquel(Re: float) -> float:
    """
    Schock & Miquel (1987) 상관식
    RO 멤브레인 스페이서 채널의 마찰 계수(Darcy Friction Factor) 산출
    """
    Re = max(float(Re), 1.0)
    return 6.23 * (Re**-0.3)


def pressure_drop_spacer_bar(
    *,
    rho_kg_m3: float,
    mu_pa_s: float,
    velocity_m_s: float,
    dh_m: float,
    length_m: float,
) -> float:
    """
    Darcy-Weisbach 방정식과 Schock & Miquel 모델을 이용한 채널 내 압력 강하 계산
    """
    Re = (rho_kg_m3 * velocity_m_s * dh_m) / mu_pa_s
    f_sp = friction_factor_schock_miquel(Re)
    dp_pa = f_sp * (length_m / dh_m) * (rho_kg_m3 * (velocity_m_s**2) / 2.0)
    return min(max(0.0, dp_pa * PA_TO_BAR), 3.0)


def mass_transfer_coeff_m_s(
    *,
    rho_kg_m3: float,
    mu_pa_s: float,
    velocity_m_s: float,
    dh_m: float,
    diffusivity_m2_s: float,
) -> float:
    Re = max((rho_kg_m3 * velocity_m_s * dh_m) / mu_pa_s, 1.0)
    Sc = max(mu_pa_s / (rho_kg_m3 * diffusivity_m2_s), 1.0)
    Sh = 0.065 * (Re**0.875) * (Sc**0.25)
    return max((Sh * diffusivity_m2_s) / dh_m, 1e-8)


def build_hrro_batch_cycle_history(
    *,
    TimeSeriesPoint,
    max_minutes: float,
    dt_min: float,
    qf_total: float,
    rec_pct_final: float,
    base_chem_profile: ChemistryProfile,
    total_area_m2: float,
    A_lmh_bar_base: float,
    B_lmh_base: float,
    pump_eff: float,
    q_circulation_m3h: float,
    channel_area_m2: float,
    spacer_voidage: float,
    hydraulic_diameter_m: float,
    diffusivity_m2_s: float,
    elements_per_vessel: int,
    b_sal_slope: float = 0.45,
    compaction_k: float = 0.003,
    back_pressure_bar: float = 0.0,
    spacer_thickness_m: float = 0.00076,
    loop_volume_m3: float = 1.36,  # [정석 반영] 하드웨어 배관 체적
) -> List["TimeSeriesPoint"]:
    rec_final = _clamp(float(rec_pct_final), 0.0, 99.5)
    area = max(1e-9, float(total_area_m2))

    # [제1원리] 시스템 체적(Volume) 동기화 (WAVE 스펙 1.36 ㎥ 우선)
    v_element_m3 = area * spacer_thickness_m
    v_sys_m3 = float(loop_volume_m3) if loop_volume_m3 > 0.1 else (v_element_m3 * 1.30)

    Q_p_m3h = qf_total * (rec_final / 100.0)
    CF_max = 1.0 / max(1e-6, 1.0 - (rec_final / 100.0))

    t_cc_min = ((CF_max - 1.0) * v_sys_m3 / max(Q_p_m3h, 1e-6)) * 60.0
    t_pf_min = (v_sys_m3 / max(qf_total, 1e-6)) * 60.0
    t_cycle_min = t_cc_min + t_pf_min

    n = max(5, min(int(round(max_minutes / dt_min)) + 1, 1000))
    pts: List["TimeSeriesPoint"] = []
    cf0_mgL = base_chem_profile.tds_mgL

    for i in range(n):
        t_min = i * dt_min

        # 반연속식(Semi-batch) 톱니바퀴 사이클 로직
        t_local = t_min % t_cycle_min

        if t_local <= t_cc_min:
            frac = t_local / t_cc_min if t_cc_min > 0 else 1.0
            cf_bulk_tds = cf0_mgL * (1.0 + (CF_max - 1.0) * frac)
            r_inst = rec_final * frac
        else:
            frac = (t_local - t_cc_min) / t_pf_min if t_pf_min > 0 else 1.0
            cf_bulk_tds = cf0_mgL * (CF_max - (CF_max - 1.0) * frac)
            r_inst = 0.0

        # [Thermodynamics] Bulk Profile
        bulk_profile = scale_profile_for_tds(base_chem_profile, cf_bulk_tds)
        rho, mu, pi_bulk = calc_water_properties_from_chemistry(bulk_profile)

        v_cross = max(
            (q_circulation_m3h / 3600.0) / (channel_area_m2 * spacer_voidage), 0.05
        )
        visc_ratio = 0.00089 / mu
        D_eff = diffusivity_m2_s * _clamp((visc_ratio**0.8), 0.2, 5.0)

        k_mt = mass_transfer_coeff_m_s(
            rho_kg_m3=rho,
            mu_pa_s=mu,
            velocity_m_s=v_cross,
            dh_m=hydraulic_diameter_m,
            diffusivity_m2_s=D_eff,
        )

        target_flux_lmh = (
            (qf_total * (rec_final / 100.0) * 1000.0) / area if area > 0 else 1.0
        )
        J_mps = target_flux_lmh * LMH_TO_MPS

        # High crossflow turbulence limits concentration polarization
        beta = _clamp(math.exp(J_mps / max(k_mt, 1e-9)), 1.0, 1.20)

        # [Thermodynamics] Wall Profile
        wall_tds = cf_bulk_tds * beta
        wall_profile = scale_profile_for_tds(base_chem_profile, wall_tds)
        _, _, pi_wall = calc_water_properties_from_chemistry(wall_profile)

        A_eff = A_lmh_bar_base * (visc_ratio**0.7)
        if pi_wall > 25.0:
            A_eff *= math.exp(-compaction_k * (pi_wall - 25.0))

        B_eff = (
            B_lmh_base
            * (visc_ratio**0.3)
            * (1.0 + b_sal_slope * min(wall_tds / 35000.0, 15.0))
        )

        cp_inst = (B_eff * wall_tds) / (target_flux_lmh + B_eff) if B_eff > 0 else 0.0
        ndp_req = target_flux_lmh / max(A_eff, 0.1)

        # [제1원리 3] 40인치 표준 엘리먼트 길이(1.016m) 적용 및 스페이서 압력 강하 산출
        dp_module = pressure_drop_spacer_bar(
            rho_kg_m3=rho,
            mu_pa_s=mu,
            velocity_m_s=v_cross,
            dh_m=hydraulic_diameter_m,
            length_m=1.016,
        ) * float(elements_per_vessel)

        p_req = pi_wall + ndp_req + (dp_module * 0.5) + back_pressure_bar
        power_kw = (qf_total * (p_req + 3.0)) / 36.0 / max(0.1, pump_eff)
        qp_inst_m3h = (target_flux_lmh * area) / 1000.0
        sec_inst = power_kw / qp_inst_m3h if qp_inst_m3h > 0 else 0.0

        pts.append(
            TimeSeriesPoint(
                time_min=round(t_min, 3),
                recovery_pct=round(r_inst, 2),
                pressure_bar=round(float(p_req), 2),
                tds_mgL=round(float(cf_bulk_tds), 0),
                flux_lmh=round(float(target_flux_lmh), 2),
                ndp_bar=round(float(ndp_req), 2),
                permeate_flow_m3h=round(float(qp_inst_m3h), 4),
                permeate_tds_mgL=round(float(cp_inst), 2),
                specific_energy_kwh_m3=round(float(sec_inst), 2),
            )
        )
    return pts


class HRROModule(SimulationModule):
    def compute(self, config: "StageConfig", feed: "FeedInput") -> "StageMetric":
        from app.schemas.simulation import StageMetric, TimeSeriesPoint
        from app.schemas.common import ModuleType
        from app.schemas.simulation import HRROMassTransferIn, HRROSpacerIn

        q_raw = _f(
            getattr(config, "feed_flow_m3h", None) or getattr(feed, "flow_m3h", None),
            100.0,
        )
        rec_pct = _clamp(
            _f(
                getattr(config, "recovery_target_pct", None)
                or getattr(config, "stop_recovery_pct", None)
                or getattr(config, "ccro_recovery_pct", None),
                90.0,
            ),
            0.0,
            99.5,
        )

        vessel_count = max(1, _i(getattr(config, "vessel_count", None), 1))
        elements_per_vessel = _i(
            getattr(config, "elements_per_vessel", None)
            or getattr(config, "elements", None),
            0,
        )

        if elements_per_vessel > 50:
            elements_per_vessel //= vessel_count
        if elements_per_vessel <= 0:
            elements_per_vessel = 6
        total_elements = vessel_count * elements_per_vessel

        base_chem_profile = extract_chemistry_profile(feed)

        # ------------------------------------------------------------------
        # [정석 아키텍처] Config 입력값 최우선 -> DB 조회 -> 기본값 폴백
        # ------------------------------------------------------------------
        A0 = _f(getattr(config, "membrane_A_lmh_bar", None), 0.0)
        B0 = _f(getattr(config, "membrane_B_lmh", None), 0.0)
        area_per_elem = _f(getattr(config, "membrane_area_m2", None), 0.0)

        if A0 <= 0.0 or B0 <= 0.0 or area_per_elem <= 0.0:
            mem_id_raw = (
                getattr(config, "membrane_model", "")
                or getattr(config, "membrane_id", "")
                or "filmtec-soar-6000i"
            )
            mem_id_slug = str(mem_id_raw).strip().lower().replace(" ", "-")

            db_membrane = next(
                (m for m in MEMBRANES if m.get("id") == mem_id_slug), None
            )

            if db_membrane:
                A0 = A0 if A0 > 0.0 else float(db_membrane.get("A_lmh_bar", 6.35))
                B0 = (
                    B0
                    if B0 > 0.0
                    else float(
                        db_membrane.get("B_lmh", db_membrane.get("B_mps", 0.058))
                    )
                )
                area_per_elem = (
                    area_per_elem
                    if area_per_elem > 0.0
                    else float(db_membrane.get("area_m2", 40.9))
                )
            else:
                A0 = A0 if A0 > 0.0 else 6.35
                B0 = B0 if B0 > 0.0 else 0.058
                area_per_elem = area_per_elem if area_per_elem > 0.0 else 40.9

        total_area_m2 = total_elements * area_per_elem
        # ------------------------------------------------------------------

        flow_factor = _f(
            getattr(config, "flow_factor", None)
            or getattr(config, "hrro_flow_factor", None),
            0.85,
        )

        A_base, B_base = correct_membrane_params(
            A0, B0, base_chem_profile.temperature_C
        )
        A_base *= flow_factor

        Qp = q_raw * (rec_pct / 100.0)
        Qc = q_raw - Qp
        flux_lmh = (Qp * 1000.0) / total_area_m2 if total_area_m2 > 0 else 0.0

        sp = getattr(config, "spacer", None) or HRROSpacerIn()
        sp_h_m = _f(getattr(sp, "thickness_mm", None), 0.76) / 1000.0
        sp_eps = _f(getattr(sp, "voidage", None), 0.85)
        dh_m = float(
            getattr(sp, "hydraulic_diameter_m", None)
            or hydraulic_diameter(sp_h_m, sp_eps)
        )

        mt = getattr(config, "mass_transfer", None) or HRROMassTransferIn()
        diffusivity = _f(getattr(mt, "diffusivity_m2_s", None), 1.5e-9)
        channel_area_m2 = _f(getattr(mt, "feed_channel_area_m2", None), 0.015)

        qf_per_vessel = q_raw / vessel_count if vessel_count > 0 else 0.0
        cc_recycle = _f(getattr(config, "cc_recycle_m3h_per_pv", None), 0.0)
        if cc_recycle <= 0:
            cc_recycle = (
                _f(getattr(config, "recirc_flow_m3h", None), 0.0) / vessel_count
                if vessel_count > 0
                else 0.0
            )

        # [정석 반영] 과거에 삽입되었던 마찰 저항 강제 펌핑용 max(..., 15.0) 제거
        q_circ_est = cc_recycle + qf_per_vessel

        # WAVE 체적 스펙 가져오기 (기본값 1.36)
        loop_vol = _f(getattr(config, "loop_volume_m3", None), 1.36)

        history = build_hrro_batch_cycle_history(
            TimeSeriesPoint=TimeSeriesPoint,
            max_minutes=max(1.0, _f(getattr(config, "max_minutes", None), 30.0)),
            dt_min=max(0.05, _f(getattr(config, "timestep_s", None), 30.0) / 60.0),
            qf_total=q_raw,
            rec_pct_final=rec_pct,
            base_chem_profile=base_chem_profile,
            total_area_m2=total_area_m2,
            A_lmh_bar_base=A_base,
            B_lmh_base=B_base,
            pump_eff=_f(getattr(config, "pump_eff", None), 0.80),
            q_circulation_m3h=q_circ_est,
            channel_area_m2=channel_area_m2,
            spacer_voidage=sp_eps,
            hydraulic_diameter_m=dh_m,
            diffusivity_m2_s=diffusivity,
            elements_per_vessel=elements_per_vessel,
            b_sal_slope=_f(getattr(config, "hrro_B_sal_slope", None), 0.45),
            compaction_k=_f(getattr(config, "hrro_A_compaction_k", None), 0.003),
            back_pressure_bar=_f(
                getattr(config, "permeate_back_pressure_bar", None), 0.0
            ),
            spacer_thickness_m=sp_h_m,
            loop_volume_m3=loop_vol,  # [정석 반영] 체적 전달
        )

        avg_sec = (
            sum(
                pt.specific_energy_kwh_m3 for pt in history if pt.specific_energy_kwh_m3
            )
            / len(history)
            if history
            else 0.0
        )
        avg_cp = (
            sum(pt.permeate_tds_mgL for pt in history) / len(history)
            if history
            else 0.0
        )

        max_p_in = max((pt.pressure_bar for pt in history), default=0.0)
        max_cc = max((pt.tds_mgL for pt in history), default=0.0)

        profile_name, reason = choose_guideline_profile(
            water_type=getattr(feed, "water_type", None),
            water_subtype=getattr(feed, "water_subtype", None),
            sdi15=getattr(feed, "sdi15", None),
            tds_mgL=base_chem_profile.tds_mgL,
        )
        checks = {
            "avg_flux_lmh": flux_lmh,
            "feed_flow_m3h_per_vessel": qf_per_vessel,
            "dp_bar_per_vessel": 0.0,
            "element_recovery_pct": (
                (rec_pct / elements_per_vessel) if elements_per_vessel > 0 else 0.0
            ),
        }
        guideline_used, violations = build_guideline_violations(
            profile=profile_name, inch=infer_element_inch(area_per_elem), checks=checks
        )

        scaling_indices = calc_scaling_indices(base_chem_profile)

        chem_out = {
            "physics_parameters": {
                "total_area_m2": total_area_m2,
                "flux_lmh": flux_lmh,
                "A_base": A_base,
                "B_base": B_base,
            },
            "guideline": {**guideline_used, "profile_reason": reason},
            "violations": violations,
            "scaling": {"feed": scaling_indices},
        }

        stage_no = _i(
            (getattr(config, "stage", None) or getattr(config, "stage_no", None) or 1),
            1,
        )

        return StageMetric(
            stage=stage_no,
            module_type=ModuleType.HRRO,
            recovery_pct=round(rec_pct, 2),
            net_recovery_pct=round(rec_pct, 2),
            flux_lmh=round(flux_lmh, 3),
            sec_kwhm3=round(avg_sec, 2),
            ndp_bar=None,
            p_in_bar=round(max_p_in, 2),
            p_out_bar=None,
            Qf=q_raw,
            Qp=Qp,
            Qc=Qc,
            Cf=base_chem_profile.tds_mgL,
            Cp=round(avg_cp, 2),
            Cc=round(max_cc, 0),
            time_history=history,
            chemistry=chem_out,
        )
