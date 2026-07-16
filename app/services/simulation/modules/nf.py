# app/services/simulation/modules/nf.py
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, Tuple, Optional, List

from app.services.simulation.modules.base import SimulationModule
from app.schemas.simulation import (
    StageConfig,
    FeedInput,
    StageMetric,
    ModuleType,
    SimulationWarning,
)
from app.services.chemistry import (
    ChemistryProfile,
    calculate_osmotic_pressure_bar,
    scale_profile_for_tds,
    calc_scaling_indices,
)
from app.services.transport import mass_transfer_k_m_s, cp_factor, lmh_to_m_per_s
from app.services.simulation.modules.wave_alignment import build_pressure_membrane_alignment

P_PERM_BAR = 0.0
TEMP_REF_C = 25.0
MOLAR_RATIO_NA = 22.99 / 58.44
MOLAR_RATIO_CL = 35.45 / 58.44
SOLVER_MAX_ITER = 30
SOLVER_TOLERANCE_MG_L = 1e-3

# Correlation fitted to the WAVE stage rows in the schema-v3 dataset.
# It estimates pressure drop per element from feed flow per pressure vessel,
# temperature and salinity.  The fitted multiplier remains calibratable.
DP_REF_BAR_PER_ELEMENT = 0.139
DP_REF_FLOW_M3H_PER_PV = 10.0
DP_FLOW_EXPONENT = 1.78
DP_TEMP_COEFF_PER_C = 0.0321
DP_TDS_EXPONENT = 0.65


def _safe_get(config: Any, key: str, default: Any = None) -> Any:
    if isinstance(config, dict):
        return config.get(key, default)
    if (
        hasattr(config, "model_extra")
        and isinstance(config.model_extra, dict)
        and key in config.model_extra
    ):
        return config.model_extra[key]
    val = getattr(config, key, None)
    return val if val is not None else default


def _f(v: Any, default: float) -> float:
    try:
        return float(v) if v is not None else float(default)
    except (ValueError, TypeError):
        return float(default)


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(float(x), hi))


def _estimate_dp_per_element_bar(
    feed_flow_m3h: float,
    vessel_count: int,
    temperature_C: float,
    feed_tds_mgL: float,
    multiplier: float,
) -> float:
    flow_per_pv = max(float(feed_flow_m3h) / max(int(vessel_count), 1), 1e-6)
    flow_term = (flow_per_pv / DP_REF_FLOW_M3H_PER_PV) ** DP_FLOW_EXPONENT
    temp_term = math.exp(DP_TEMP_COEFF_PER_C * (25.0 - float(temperature_C)))
    salinity_term = (1.0 + max(float(feed_tds_mgL), 0.0) / 35000.0) ** DP_TDS_EXPONENT
    value = DP_REF_BAR_PER_ELEMENT * flow_term * temp_term * salinity_term
    return _clamp(value * float(multiplier), 0.002, 5.0)


def _as_dict(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        return value.model_dump(exclude_none=True)
    if hasattr(value, "dict"):
        return value.dict(exclude_none=True)
    return {}


def _extract_chemistry_profile(feed: FeedInput) -> ChemistryProfile:
    # FeedInput used by the tuner stores ions in ``feed.ions``. The old code
    # only inspected ``feed.chemistry``, silently discarding Ca/Mg/SO4/HCO3.
    ion_data = _as_dict(getattr(feed, "ions", None))
    chemistry_data = _as_dict(getattr(feed, "chemistry", None))
    chem_data = {**chemistry_data, **ion_data}

    tds = _f(getattr(feed, "tds_mgL", None), 0.0)
    temp = _f(getattr(feed, "temperature_C", None), TEMP_REF_C)
    ph = _f(getattr(feed, "ph", None), 7.0)

    def ion_value(key: str) -> float:
        return _f(chem_data.get(key, chem_data.get(f"{key}_mgL")), 0.0)

    ion_keys = ("na", "cl", "k", "ca", "mg", "so4", "hco3", "sr", "ba", "f", "sio2")
    has_explicit_ions = any(ion_value(key) > 0.0 for key in ion_keys)
    na_val = ion_value("na")
    cl_val = ion_value("cl")
    if not has_explicit_ions:
        na_val = tds * MOLAR_RATIO_NA
        cl_val = tds * MOLAR_RATIO_CL

    return ChemistryProfile(
        tds_mgL=tds,
        temperature_C=temp,
        ph=ph,
        na_mgL=na_val,
        cl_mgL=cl_val,
        k_mgL=ion_value("k"),
        ca_mgL=ion_value("ca"),
        mg_mgL=ion_value("mg"),
        so4_mgL=ion_value("so4"),
        hco3_mgL=ion_value("hco3"),
        sr_mgL=ion_value("sr"),
        ba_mgL=ion_value("ba"),
        f_mgL=ion_value("f"),
        sio2_mgL=ion_value("sio2"),
    )


def _profile_to_dict(prof: ChemistryProfile) -> Dict[str, float]:
    return {
        k.replace("_mgL", ""): float(v)
        for k, v in vars(prof).items()
        if k.endswith("_mgL") and k != "tds_mgL" and v is not None
    }


def _get_wave_calibration(
    mod_type: str, A_init: float, B_init: float, pi_bar: float
) -> Tuple[float, float]:
    if mod_type == "NF":
        return A_init * 1.45, B_init * 0.25
    return A_init, B_init


@dataclass
class NFSolveState:
    Qf_m3h: float = 0.0
    Cf_mgL: float = 0.0
    T_C: float = TEMP_REF_C
    base_profile: Optional[ChemistryProfile] = None
    vessels: int = 1
    elements_per_vessel: int = 6
    area_per_element: float = 37.0
    total_area: float = 37.0
    A_lmh_bar: float = 0.0
    B_mono_lmh: float = 0.0
    B_di_lmh: float = 0.0
    B_corr: float = 1.0
    b_salinity_slope: float = 0.0
    dp_total_bar: float = 0.15
    dp_per_element_bar: float = 0.025
    dp_correlation_enabled: bool = False
    dp_correlation_multiplier: float = 1.0
    cp_tuning_factor: float = 1.0
    permeate_bp_bar: float = 0.0
    target_qp_m3h: Optional[float] = None
    qp_m3h: float = 0.0
    qc_m3h: float = 0.0
    flux_lmh: float = 0.0
    cp_factor_val: float = 1.0
    ndp_bar: float = 0.0
    pi_cm_bar: float = 0.0
    avg_pressure_bar: float = 0.0
    p_in_bar: float = 0.0
    p_out_bar: float = 0.0
    permeate_profile: Optional[ChemistryProfile] = None
    concentrate_profile: Optional[ChemistryProfile] = None
    recovery_pct: float = 0.0
    sec_kwhm3: float = 0.0
    element_profiles: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[SimulationWarning] = field(default_factory=list)


class NFModule(SimulationModule):
    def compute(self, config: StageConfig, feed: FeedInput) -> StageMetric:
        state = self._initialize_state(config, feed)
        if state.Qf_m3h <= 1e-12 or state.total_area <= 1e-12 or state.A_lmh_bar <= 0.0:
            return self._create_empty_metric(state)
        self._solve_transport(state)
        self._calculate_energy_and_warnings(config, state)
        return self._build_result(config, state)

    def _initialize_state(self, config: StageConfig, feed: FeedInput) -> NFSolveState:
        state = NFSolveState()
        state.Qf_m3h = _f(getattr(feed, "flow_m3h", None), 0.0)
        state.Cf_mgL = _f(getattr(feed, "tds_mgL", None), 0.0)
        state.T_C = _f(getattr(feed, "temperature_C", None), TEMP_REF_C)
        state.base_profile = _extract_chemistry_profile(feed)

        state.vessels = max(1, int(_f(_safe_get(config, "vessel_count", 10), 10)))
        state.elements_per_vessel = int(
            _f(_safe_get(config, "elements_per_vessel", 6), 6)
        )
        state.area_per_element = _f(_safe_get(config, "membrane_area_m2", 37.0), 37.0)
        state.total_area = max(
            1e-9, state.vessels * state.elements_per_vessel * state.area_per_element
        )

        # 🚀 하드코딩 제거: 외부 튜닝값 동적 수용
        A_base = max(0.0, _f(_safe_get(config, "membrane_A_lmh_bar", 12.5), 12.5))
        B_in = _f(_safe_get(config, "membrane_B_lmh", 0.1), 0.1)
        if B_in < 1.0:
            B_base_mono, B_base_divalent = 25.0, 0.2
        else:
            B_base_mono, B_base_divalent = B_in, B_in * 0.05

        A_corr = _f(_safe_get(config, "A_correction_factor", 1.0), 1.0)
        state.B_corr = _f(_safe_get(config, "B_correction_factor", 1.0), 1.0)
        fouling_factor = _clamp(
            _f(_safe_get(config, "fouling_factor", 1.0), 1.0), 0.05, 1.20
        )
        b_fouling_factor = _clamp(
            _f(_safe_get(config, "B_fouling_factor", 1.0), 1.0), 0.05, 20.0
        )

        state.dp_correlation_enabled = bool(
            _safe_get(config, "dp_correlation_enabled", False)
        )
        state.dp_correlation_multiplier = _clamp(
            _f(_safe_get(config, "dp_correlation_multiplier", 1.0), 1.0),
            0.05,
            20.0,
        )
        if state.dp_correlation_enabled:
            state.dp_per_element_bar = _estimate_dp_per_element_bar(
                state.Qf_m3h,
                state.vessels,
                state.T_C,
                state.Cf_mgL,
                state.dp_correlation_multiplier,
            )
        else:
            dp_in = _safe_get(
                config, "dp_module_bar", _safe_get(config, "dp_per_elem_bar", 0.15)
            )
            state.dp_per_element_bar = max(0.0, _f(dp_in, 0.15))
        state.dp_total_bar = float(
            state.elements_per_vessel * state.dp_per_element_bar
        )
        state.b_salinity_slope = _clamp(
            _f(_safe_get(config, "b_salinity_slope", 0.0), 0.0),
            0.0,
            20.0,
        )

        cp_in = _safe_get(
            config, "cp_tuning_factor", _safe_get(config, "cp_adjustment_factor", 1.0)
        )
        state.cp_tuning_factor = _clamp(_f(cp_in, 1.0), 0.05, 20.0)

        temp_corr_A = _f(_safe_get(config, "temp_corr_factor_A", 2640.0), 2640.0)
        temp_corr_B = _f(_safe_get(config, "temp_corr_factor_B", 3500.0), 3500.0)
        T_K = state.T_C + 273.15
        tcf_A = math.exp(temp_corr_A * (1.0 / 298.15 - 1.0 / T_K))
        tcf_B = math.exp(temp_corr_B * (1.0 / 298.15 - 1.0 / T_K))

        A_init = (
            A_base
            * _f(_safe_get(config, "flow_factor", 0.85), 0.85)
            * tcf_A
            * A_corr
            * fouling_factor
        )
        B_mono_init = B_base_mono * tcf_B * b_fouling_factor
        B_di_init = B_base_divalent * tcf_B * b_fouling_factor
        state.A_lmh_bar, state.B_mono_lmh = _get_wave_calibration(
            "NF", A_init, B_mono_init, 0.0
        )
        _, state.B_di_lmh = _get_wave_calibration("NF", A_init, B_di_init, 0.0)

        state.permeate_bp_bar = max(
            0.0, _f(_safe_get(config, "permeate_back_pressure_bar", 0.0), 0.0)
        )
        target_recovery = _safe_get(config, "recovery_target_pct")
        if target_recovery is not None:
            state.target_qp_m3h = state.Qf_m3h * (
                _clamp(target_recovery, 0.0, 99.5) / 100.0
            )
        return state

    def _solve_transport(self, state: NFSolveState) -> None:
        state.permeate_profile = ChemistryProfile(
            tds_mgL=0.0, temperature_C=state.T_C, ph=7.0
        )
        state.concentrate_profile = scale_profile_for_tds(
            state.base_profile, state.Cf_mgL
        )

        if state.target_qp_m3h is not None:
            state.qp_m3h = min(state.target_qp_m3h, state.Qf_m3h * 0.99)
            state.qc_m3h = max(1e-12, state.Qf_m3h - state.qp_m3h)
            state.flux_lmh = (state.qp_m3h * 1000.0) / state.total_area

            prev_perm_tds = -1.0
            for _ in range(SOLVER_MAX_ITER):
                avg_flow_m3h_per_vessel = (
                    (state.Qf_m3h + state.qc_m3h) / 2.0
                ) / state.vessels
                velocity_m_s = (avg_flow_m3h_per_vessel / 3600.0) / 0.015
                k_mt_ms = mass_transfer_k_m_s(velocity_m_s, 0.001, state.T_C)
                # Match RO semantics: larger CP tuning means stronger mass
                # transfer (larger effective k) and therefore a lower CP factor.
                effective_k = max(k_mt_ms * state.cp_tuning_factor, 1e-8)
                state.cp_factor_val = max(
                    1.0,
                    math.exp(
                        min(lmh_to_m_per_s(state.flux_lmh) / effective_k, 3.0)
                    ),
                )
                self._calc_all_ions_passage(state)
                if (
                    abs(state.permeate_profile.tds_mgL - prev_perm_tds)
                    < SOLVER_TOLERANCE_MG_L
                ):
                    break
                prev_perm_tds = state.permeate_profile.tds_mgL

            effective_wall_tds = max(
                1.0,
                (state.concentrate_profile.tds_mgL * state.cp_factor_val)
                - state.permeate_profile.tds_mgL,
            )
            state.pi_cm_bar = (
                calculate_osmotic_pressure_bar(
                    scale_profile_for_tds(state.base_profile, effective_wall_tds)
                )
                * 0.5
            )
            state.ndp_bar = (
                state.flux_lmh / state.A_lmh_bar if state.A_lmh_bar > 0 else 0.0
            )
            state.avg_pressure_bar = (
                state.ndp_bar + state.pi_cm_bar + state.permeate_bp_bar
            )
            state.p_in_bar = state.avg_pressure_bar + state.dp_total_bar / 2.0
            state.p_out_bar = max(0.0, state.p_in_bar - state.dp_total_bar)

        state.recovery_pct = (
            (state.qp_m3h / state.Qf_m3h * 100.0) if state.Qf_m3h > 1e-12 else 0.0
        )

    def _calc_all_ions_passage(self, state: NFSolveState) -> None:
        def calc_ion(
            feed_c: float, curr_conc_c: float, base_b_val: float, scale_factor: float
        ) -> Tuple[float, float]:
            avg_c = (feed_c + curr_conc_c) / 2.0
            wall_c = min(avg_c * state.cp_factor_val, max(feed_c * 10.0, avg_c))
            salinity_ratio = min(
                max(state.concentrate_profile.tds_mgL * state.cp_factor_val, 0.0)
                / 35000.0,
                12.0,
            )
            b_val = (
                base_b_val
                * scale_factor
                * state.B_corr
                * (1.0 + state.b_salinity_slope * salinity_ratio)
            )
            perm_c = (
                (b_val * wall_c) / (state.flux_lmh + b_val)
                if (state.flux_lmh + b_val) > 0
                else 0.0
            )
            perm_c = max(0.0, min(perm_c, feed_c))
            target_conc_c = max(
                0.0, (state.Qf_m3h * feed_c - state.qp_m3h * perm_c) / state.qc_m3h
            )
            return perm_c, (curr_conc_c * 0.5 + target_conc_c * 0.5)

        bp, cp, pp = (
            state.base_profile,
            state.concentrate_profile,
            state.permeate_profile,
        )
        b_mono, b_di = state.B_mono_lmh, state.B_di_lmh

        pp.na_mgL, cp.na_mgL = calc_ion(bp.na_mgL, cp.na_mgL, b_mono, 5.5)
        pp.cl_mgL, cp.cl_mgL = calc_ion(bp.cl_mgL, cp.cl_mgL, b_mono, 6.0)
        pp.k_mgL, cp.k_mgL = calc_ion(bp.k_mgL, cp.k_mgL, b_mono, 5.0)
        pp.hco3_mgL, cp.hco3_mgL = calc_ion(bp.hco3_mgL, cp.hco3_mgL, b_mono, 0.8)
        pp.f_mgL, cp.f_mgL = calc_ion(bp.f_mgL, cp.f_mgL, b_mono, 1.0)
        pp.sio2_mgL, cp.sio2_mgL = calc_ion(bp.sio2_mgL, cp.sio2_mgL, b_mono, 1.0)
        pp.ca_mgL, cp.ca_mgL = calc_ion(bp.ca_mgL, cp.ca_mgL, b_di, 0.15)
        pp.mg_mgL, cp.mg_mgL = calc_ion(bp.mg_mgL, cp.mg_mgL, b_di, 0.08)
        pp.so4_mgL, cp.so4_mgL = calc_ion(bp.so4_mgL, cp.so4_mgL, b_di, 0.02)
        pp.sr_mgL, cp.sr_mgL = calc_ion(bp.sr_mgL, cp.sr_mgL, b_di, 0.1)
        pp.ba_mgL, cp.ba_mgL = calc_ion(bp.ba_mgL, cp.ba_mgL, b_di, 0.1)

        def sum_ions(p: ChemistryProfile) -> float:
            return sum(
                filter(
                    None,
                    [
                        p.na_mgL,
                        p.cl_mgL,
                        p.k_mgL,
                        p.ca_mgL,
                        p.mg_mgL,
                        p.so4_mgL,
                        p.hco3_mgL,
                        p.sr_mgL,
                        p.ba_mgL,
                        p.f_mgL,
                        p.sio2_mgL,
                    ],
                )
            )

        pp.tds_mgL, cp.tds_mgL = sum_ions(pp), sum_ions(cp)

    def _calculate_energy_and_warnings(
        self, config: StageConfig, state: NFSolveState
    ) -> None:
        state.sec_kwhm3 = max(
            0.01,
            (
                (
                    (
                        (state.Qf_m3h * state.p_in_bar)
                        / (
                            36.0
                            * _clamp(
                                _f(_safe_get(config, "pump_eff", 0.80), 0.80), 0.2, 0.95
                            )
                        )
                    )
                    / state.qp_m3h
                )
                * 0.86
                if state.qp_m3h > 1e-12
                else 0.0
            ),
        )

    def _build_result(self, config: StageConfig, state: NFSolveState) -> StageMetric:
        final_permeate_tds = state.permeate_profile.tds_mgL
        final_concentrate_tds = max(
            0.0,
            (
                (
                    state.Qf_m3h * state.base_profile.tds_mgL
                    - state.qp_m3h * final_permeate_tds
                )
                / state.qc_m3h
                if state.qc_m3h > 1e-12
                else state.concentrate_profile.tds_mgL
            ),
        )
        scaling_indices = calc_scaling_indices(
            scale_profile_for_tds(state.base_profile, final_concentrate_tds)
        )
        wave_alignment = build_pressure_membrane_alignment(
            config=config,
            module_type=ModuleType.NF,
            qf_m3h=state.Qf_m3h,
            qp_m3h=state.qp_m3h,
            qc_m3h=state.qc_m3h,
            feed_tds_mgL=state.base_profile.tds_mgL,
            permeate_tds_mgL=final_permeate_tds,
            concentrate_tds_mgL=final_concentrate_tds,
            flux_lmh=state.flux_lmh,
            ndp_bar=state.ndp_bar,
            p_in_bar=state.p_in_bar,
            p_out_bar=state.p_out_bar,
            dp_total_bar=state.dp_total_bar,
            total_area_m2=state.total_area,
            vessels=state.vessels,
            elements_per_vessel=state.elements_per_vessel,
            area_per_element_m2=state.area_per_element,
            temperature_C=state.T_C,
            stage_label=_safe_get(config, "stage_label", None),
        )

        return StageMetric(
            stage=0,
            module_type=ModuleType.NF,
            recovery_pct=round(state.recovery_pct, 2),
            flux_lmh=round(state.flux_lmh, 2),
            sec_kwhm3=round(state.sec_kwhm3, 4),
            ndp_bar=round(state.ndp_bar, 3),
            p_in_bar=round(state.p_in_bar, 3),
            p_out_bar=round(state.p_out_bar, 3),
            Qf=round(state.Qf_m3h, 6),
            Qp=round(state.qp_m3h, 6),
            Qc=round(state.qc_m3h, 6),
            Cf=round(state.base_profile.tds_mgL, 6),
            Cp=round(final_permeate_tds, 6),
            Cc=round(final_concentrate_tds, 6),
            chemistry={
                "streams": {
                    "feed": {
                        "flow_m3h": float(state.Qf_m3h),
                        "tds_mgL": float(state.base_profile.tds_mgL),
                        "ions": _profile_to_dict(state.base_profile),
                    },
                    "permeate": {
                        "flow_m3h": float(state.qp_m3h),
                        "tds_mgL": float(final_permeate_tds),
                        "ions": _profile_to_dict(state.permeate_profile),
                    },
                    "concentrate": {
                        "flow_m3h": float(state.qc_m3h),
                        "tds_mgL": float(final_concentrate_tds),
                        "ions": _profile_to_dict(state.concentrate_profile),
                    },
                },
                "model": {
                    "dp_total_bar": float(state.dp_total_bar),
                    "dp_per_element_bar": float(state.dp_per_element_bar),
                    "dp_correlation_enabled": bool(state.dp_correlation_enabled),
                    "dp_correlation_multiplier": float(state.dp_correlation_multiplier),
                    "b_salinity_slope": float(state.b_salinity_slope),
                    "avg_pressure_bar": float(state.avg_pressure_bar),
                    "pi_cm_bar": float(state.pi_cm_bar),
                    "cp_factor_last": float(state.cp_factor_val),
                },
                "elements": state.element_profiles,
                "scaling": {"final_brine": scaling_indices},
                "final_brine": scaling_indices,
                "wave_alignment": wave_alignment,
            },
            warnings=state.warnings if state.warnings else None,
        )

    def _create_empty_metric(self, state: NFSolveState) -> StageMetric:
        return StageMetric(
            stage=0,
            module_type=ModuleType.NF,
            recovery_pct=0.0,
            flux_lmh=0.0,
            sec_kwhm3=0.0,
            ndp_bar=0.0,
            p_in_bar=0.0,
            p_out_bar=0.0,
            Qf=round(state.Qf_m3h, 6),
            Qp=0.0,
            Qc=round(state.Qf_m3h, 6),
            Cf=0.0,
            Cp=0.0,
            Cc=0.0,
            chemistry={},
        )
