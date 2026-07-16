# app/services/simulation/modules/uf.py
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from app.schemas.common import ModuleType
from app.schemas.simulation import (
    FeedInput,
    SimulationWarning,
    StageConfig,
    StageMetric,
)
from app.services.simulation.modules.base import SimulationModule
from app.services.chemistry import get_water_viscosity_pa_s
from app.services.simulation.modules.wave_alignment import build_uf_alignment

# ==========================================
# 1. 상수 정의 (Magic Numbers 제거)
# ==========================================
P_ATM_PA = 101325.0  # 1 atm in Pascals
BLOWER_ADD_PA = 75000.0  # 0.75 bar in Pascals
GAMMA_AIR = 1.4  # 비열비 (Air)
GAMMA_RATIO = GAMMA_AIR / (GAMMA_AIR - 1.0)  # 1.4 / 0.4 = 3.5
GAMMA_PWR = (GAMMA_AIR - 1.0) / GAMMA_AIR  # 0.4 / 1.4 = ~0.2857
BLOWER_EFFICIENCY = 0.60

NAOCL_CONC_RATIO = 0.35  # NaOCl 약품 농도 비율 (350 mg/L 기준)


def _f(v: Any, default: float) -> float:
    try:
        if v is None:
            return float(default)
        return float(v)
    except (ValueError, TypeError):
        return float(default)


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(float(x), hi))


def _get_m(obj: Any, key: str, default: float) -> float:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default) if hasattr(obj, key) else default


@dataclass
class UFSolveState:
    Qf_raw_m3h: float = 0.0  # 스트레이너 통과 전 진짜 원수
    Qf_m3h: float = 0.0  # 스트레이너 통과 후 UF 유입수
    Cf_mgL: float = 0.0
    tss_mgL: float = 0.0
    T_C: float = 25.0

    elements: int = 1
    area_per_element: float = 77.0
    total_area: float = 77.0

    target_recovery_pct: Optional[float] = None
    max_tmp_bar: Optional[float] = None

    flux_lmh: float = 0.0
    filt_min: float = 60.0
    bw_min: float = 1.0
    bw_flux_lmh: float = 100.0

    net_prod_m3h: float = 0.0
    qc_m3h: float = 0.0
    uf_recovery_pct: float = 0.0
    system_recovery_pct: float = 0.0

    viscosity_ratio: float = 1.0
    R_m_eff: float = 0.0
    R_f_eff: float = 0.0
    tmp_initial_bar: float = 0.0
    tmp_end_bar: float = 0.0
    p_in_bar: float = 0.0
    p_out_bar: float = 0.0

    strainer_waste_m3h: float = 0.0
    air_flow_nm3h: float = 0.0
    air_power_kw: float = 0.0
    ceb_naocl_kg_day: float = 0.0
    ceb_hcl_kg_day: float = 0.0

    sec_kwhm3: float = 0.0
    warnings: list[SimulationWarning] = field(default_factory=list)


class UFModule(SimulationModule):
    def compute(self, config: StageConfig, feed: FeedInput) -> StageMetric:
        state = self._initialize_state(config, feed)

        if state.Qf_raw_m3h <= 1e-12 or state.total_area <= 1e-12:
            return self._create_empty_metric(state)

        self._solve_peripherals(config, state)
        self._solve_flow_balance(config, state)
        self._solve_hydraulics_and_energy(config, state)

        return self._build_result(config, state)

    def _initialize_state(self, config: StageConfig, feed: FeedInput) -> UFSolveState:
        state = UFSolveState()
        state.Qf_raw_m3h = _f(getattr(feed, "flow_m3h", None), 0.0)
        state.Cf_mgL = _f(getattr(feed, "tds_mgL", None), 0.0)
        state.tss_mgL = _f(getattr(feed, "tss_mgL", None), 0.0)
        state.T_C = _f(getattr(feed, "temperature_C", None), 25.0)

        state.elements = max(1, int(_f(getattr(config, "elements", None), 1)))
        state.area_per_element = _f(getattr(config, "membrane_area_m2", None), 77.0)
        state.total_area = max(1e-9, state.elements * max(1e-9, state.area_per_element))

        state.target_recovery_pct = getattr(config, "recovery_target_pct", None)
        state.max_tmp_bar = getattr(config, "max_tmp_bar", None)

        return state

    def _solve_peripherals(self, config: StageConfig, state: UFSolveState) -> None:
        strainer_rec = _clamp(
            _f(getattr(config, "strainer_recovery_pct", 99.5), 99.5), 0.0, 100.0
        )
        state.Qf_m3h = state.Qf_raw_m3h * (strainer_rec / 100.0)
        state.strainer_waste_m3h = state.Qf_raw_m3h - state.Qf_m3h

    def _solve_flow_balance(self, config: StageConfig, state: UFSolveState) -> None:
        maint = getattr(config, "uf_maintenance", None)
        state.filt_min = _f(_get_m(maint, "filtration_duration_min", 60.0), 60.0)
        bw_sec = _f(_get_m(maint, "backwash_duration_sec", 60.0), 60.0)
        state.bw_min = bw_sec / 60.0
        state.bw_flux_lmh = _f(_get_m(maint, "backwash_flux_lmh", 100.0), 100.0)

        cycle_time_min = max(1e-6, state.filt_min + state.bw_min)
        filt_frac = state.filt_min / cycle_time_min
        bw_frac = state.bw_min / cycle_time_min
        uptime_factor = 0.95

        bw_rate_m3h = (state.bw_flux_lmh * state.total_area) / 1000.0

        if state.target_recovery_pct is not None:
            state.uf_recovery_pct = _clamp(state.target_recovery_pct, 0.0, 100.0)
            state.net_prod_m3h = state.Qf_m3h * (state.uf_recovery_pct / 100.0)

            req_gross_rate_m3h = (
                (state.net_prod_m3h / uptime_factor) + (bw_rate_m3h * bw_frac)
            ) / max(1e-9, filt_frac)

            state.flux_lmh = (req_gross_rate_m3h * 1000.0) / state.total_area
        else:
            state.flux_lmh = _f(
                getattr(config, "flux_lmh", None),
                _f(getattr(config, "design_flux_lmh", None), 55.5),
            )
            gross_prod_rate_m3h = (state.flux_lmh * state.total_area) / 1000.0

            calc_net_prod_m3h = (
                gross_prod_rate_m3h * filt_frac - bw_rate_m3h * bw_frac
            ) * uptime_factor
            state.net_prod_m3h = max(0.0, min(calc_net_prod_m3h, state.Qf_m3h))
            state.uf_recovery_pct = (
                (state.net_prod_m3h / state.Qf_m3h * 100.0)
                if state.Qf_m3h > 1e-12
                else 0.0
            )

        state.qc_m3h = max(0.0, state.Qf_m3h - state.net_prod_m3h)
        state.system_recovery_pct = (
            (state.net_prod_m3h / state.Qf_raw_m3h * 100.0)
            if state.Qf_raw_m3h > 1e-12
            else 0.0
        )

    def _solve_hydraulics_and_energy(
        self, config: StageConfig, state: UFSolveState
    ) -> None:
        mu_25_ref = get_water_viscosity_pa_s(25.0, state.Cf_mgL)
        mu_t_actual = get_water_viscosity_pa_s(state.T_C, state.Cf_mgL)
        state.viscosity_ratio = float(mu_t_actual) / float(mu_25_ref)

        permeability_25c = _f(getattr(config, "membrane_A_lmh_bar", None), 140.0)
        flow_factor = _clamp(_f(getattr(config, "flow_factor", None), 1.0), 0.1, 2.0)

        state.R_m_eff = 1.0 / max(1e-9, permeability_25c * flow_factor)

        alpha_fouling = _f(getattr(config, "fouling_rate_constant", 1.5e-7), 1.5e-7)
        delta_R_f_per_cycle = (
            alpha_fouling * state.tss_mgL * state.flux_lmh * state.filt_min
        )

        bw_recovery_eff = 0.95
        residual_R_f_per_cycle = delta_R_f_per_cycle * (1.0 - bw_recovery_eff)

        maint = getattr(config, "uf_maintenance", None)
        ceb_interval_h = _f(_get_m(maint, "alkali_ceb_interval_h", 24.0), 24.0)
        if ceb_interval_h <= 0.0:
            ceb_interval_h = 24.0

        cycle_time_min = state.filt_min + state.bw_min
        cycles_per_ceb = (ceb_interval_h * 60.0) / max(1e-6, cycle_time_min)

        state.R_f_eff = delta_R_f_per_cycle + (residual_R_f_per_cycle * cycles_per_ceb)

        state.tmp_initial_bar = state.flux_lmh * state.viscosity_ratio * state.R_m_eff
        state.tmp_end_bar = (
            state.flux_lmh * state.viscosity_ratio * (state.R_m_eff + state.R_f_eff)
        )

        state.p_out_bar = _f(getattr(config, "uf_p_out_bar", None), 0.0)
        header_loss = _f(getattr(config, "uf_header_loss_bar", None), 0.0)
        state.p_in_bar = state.p_out_bar + state.tmp_end_bar + header_loss

        # 에어 스쿠어(Air Scour) 블로워 동력 연산 (단열 압축 공식 적용)
        air_flow_per_mod = _f(_get_m(maint, "air_flow_nm3h_per_mod", 12.0), 12.0)
        state.air_flow_nm3h = air_flow_per_mod * state.elements

        air_scour_sec = _f(_get_m(maint, "air_scour_duration_sec", 30.0), 30.0)
        air_duty_cycle = (air_scour_sec / 60.0) / max(1e-6, cycle_time_min)

        p_out = P_ATM_PA + BLOWER_ADD_PA
        Q_m3s = state.air_flow_nm3h / 3600.0

        peak_air_w = (
            (Q_m3s * P_ATM_PA / BLOWER_EFFICIENCY)
            * GAMMA_RATIO
            * ((p_out / P_ATM_PA) ** GAMMA_PWR - 1.0)
        )
        state.air_power_kw = (peak_air_w / 1000.0) * air_duty_cycle

        # UF Feed Pump 동력
        pump_eff = _clamp(_f(getattr(config, "pump_eff", None), 0.75), 0.2, 0.95)
        pump_power_kw = (
            ((state.Qf_m3h * state.p_in_bar) / 36.0 / pump_eff)
            if state.Qf_m3h > 0
            else 0.0
        )

        state.sec_kwhm3 = (
            (pump_power_kw + state.air_power_kw) / state.net_prod_m3h
            if state.net_prod_m3h > 1e-12
            else 0.0
        )

        # CEB 화학세정 약품 소모량 연산
        ceb_flux = _f(_get_m(maint, "ceb_flux_lmh", 80.0), 80.0)
        ceb_flow_m3h = (ceb_flux * state.total_area) / 1000.0
        ceb_duration_min = 10.0
        ceb_vol_m3_per_event = ceb_flow_m3h * (ceb_duration_min / 60.0)

        events_per_day = 24.0 / max(1e-6, ceb_interval_h)
        state.ceb_naocl_kg_day = (
            ceb_vol_m3_per_event * NAOCL_CONC_RATIO * events_per_day
        )

        if state.max_tmp_bar is not None and state.tmp_end_bar > state.max_tmp_bar:
            state.warnings.append(
                SimulationWarning(
                    stage=str(getattr(config, "stage_idx", 1)),
                    module_type=ModuleType.UF.value,
                    key="HIGH_TMP_WARN",
                    message=f"CEB End-of-Cycle TMP ({state.tmp_end_bar:.2f} bar) exceeds the design limit ({state.max_tmp_bar:.2f} bar).",
                    value=state.tmp_end_bar,
                    limit=state.max_tmp_bar,
                    unit="bar",
                    level="WARN",
                )
            )

    def _build_result(self, config: StageConfig, state: UFSolveState) -> StageMetric:
        wave_alignment = build_uf_alignment(
            config=config,
            qf_raw_m3h=state.Qf_raw_m3h,
            qf_after_strainer_m3h=state.Qf_m3h,
            net_prod_m3h=state.net_prod_m3h,
            concentrate_m3h=state.qc_m3h,
            total_area_m2=state.total_area,
            flux_lmh=state.flux_lmh,
            tmp_initial_bar=state.tmp_initial_bar,
            tmp_end_bar=state.tmp_end_bar,
            p_in_bar=state.p_in_bar,
            filtration_min=state.filt_min,
            backwash_min=state.bw_min,
            backwash_flux_lmh=state.bw_flux_lmh,
            strainer_waste_m3h=state.strainer_waste_m3h,
            air_flow_nm3h=state.air_flow_nm3h,
            air_power_kw=state.air_power_kw,
            ceb_naocl_kg_day=state.ceb_naocl_kg_day,
            ceb_hcl_kg_day=state.ceb_hcl_kg_day,
            module_count=state.elements,
        )
        chem_payload: Dict[str, Any] = {
            "streams": {
                "raw_feed": {
                    "flow_m3h": float(state.Qf_raw_m3h),
                    "definition": "Raw water before strainer",
                },
                "feed": {
                    "flow_m3h": float(state.Qf_m3h),
                    "tds_mgL": float(state.Cf_mgL),
                    "tss_mgL": float(state.tss_mgL),
                },
                "permeate": {
                    "flow_m3h": float(state.net_prod_m3h),
                    "tds_mgL": float(state.Cf_mgL),
                    "tss_mgL": 0.0,
                },
                "concentrate": {
                    "flow_m3h": float(state.qc_m3h),
                    "tds_mgL": float(state.Cf_mgL),
                    "tss_mgL": float(
                        (state.tss_mgL * state.Qf_m3h) / max(1e-9, state.qc_m3h)
                    ),
                },
                "strainer_waste": {"flow_m3h": float(state.strainer_waste_m3h)},
            },
            "model": {
                "tmp_initial_bar": float(state.tmp_initial_bar),
                "tmp_end_bar": float(state.tmp_end_bar),
                "filtration_min": float(state.filt_min),
                "net_prod_m3h": float(state.net_prod_m3h),
                "gross_flux_lmh": float(state.flux_lmh),
                "system_recovery_pct": float(state.system_recovery_pct),
            },
            "peripherals": {
                "air_scour_flow_nm3h": float(state.air_flow_nm3h),
                "air_blower_avg_kw": float(state.air_power_kw),
                "ceb_naocl_kg_day": float(state.ceb_naocl_kg_day),
                "ceb_hcl_kg_day": float(state.ceb_hcl_kg_day),
            },
            "wave_alignment": wave_alignment,
        }

        return StageMetric(
            stage=0,
            module_type=ModuleType.UF,
            recovery_pct=round(state.uf_recovery_pct, 2),
            flux_lmh=round(state.flux_lmh, 1),
            ndp_bar=round(state.tmp_end_bar, 3),
            sec_kwhm3=round(state.sec_kwhm3, 4),
            p_in_bar=round(state.p_in_bar, 3),
            p_out_bar=round(state.p_out_bar, 3),
            Qf=round(state.Qf_m3h, 6),
            Qp=round(state.net_prod_m3h, 6),
            Qc=round(state.qc_m3h, 6),
            Cf=round(state.Cf_mgL, 6),
            Cp=round(state.Cf_mgL, 6),
            Cc=round(state.Cf_mgL, 6),
            chemistry=chem_payload,
            warnings=state.warnings if state.warnings else None,
        )

    def _create_empty_metric(self, state: UFSolveState) -> StageMetric:
        return StageMetric(
            stage=0,
            module_type=ModuleType.UF,
            recovery_pct=0.0,
            flux_lmh=0.0,
            ndp_bar=0.0,
            sec_kwhm3=0.0,
            p_in_bar=0.0,
            p_out_bar=0.0,
            Qf=round(state.Qf_m3h, 6),
            Qp=0.0,
            Qc=round(state.Qf_m3h, 6),
            Cf=round(state.Cf_mgL, 6),
            Cp=round(state.Cf_mgL, 6),
            Cc=round(state.Cf_mgL, 6),
            chemistry={},
        )
