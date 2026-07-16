# app/services/simulation/modules/mf.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from app.schemas.common import ModuleType
from app.schemas.simulation import (
    FeedInput,
    StageConfig,
    StageMetric,
    SimulationWarning,
)
from app.services.simulation.modules.base import SimulationModule
from app.services.chemistry import get_water_viscosity_pa_s


def _f(v: Any, default: float) -> float:
    try:
        if v is None:
            return float(default)
        return float(v)
    except Exception:
        return float(default)


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(float(x), hi))


@dataclass
class MFSolveState:
    Qf_m3h: float = 0.0
    Cf_mgL: float = 0.0
    T_C: float = 25.0

    elements: int = 1
    area_per_element: float = 60.0
    total_area: float = 60.0

    target_recovery_pct: Optional[float] = None
    max_tmp_bar: Optional[float] = None

    flux_lmh: float = 80.0
    bw_flux_lmh: float = 160.0
    filt_min: float = 20.0
    bw_min: float = 1.0

    filt_frac: float = 0.0
    bw_frac: float = 0.0
    cip_loss_factor: float = 0.98

    net_prod_m3h: float = 0.0
    qc_m3h: float = 0.0
    recovery_pct: float = 0.0

    permeability_25c: float = 500.0
    temp_corr: float = 1.0
    permeability: float = 500.0

    tmp_bar: float = 0.0
    p_in_bar: float = 0.0
    p_out_bar: float = 0.0

    sec_kwhm3: float = 0.0
    warnings: list[SimulationWarning] = field(default_factory=list)


class MFModule(SimulationModule):
    """
    [MF (Microfiltration) Module - Physics-Informed & Reverse Solved]
    - UF와 완벽히 동일한 역산(Reverse Calculation) 엔진 적용.
    - CIP 및 역세척 손실분을 고려하여 타겟 회수율 달성에 필요한 Gross Flux를 동적 산출합니다.
    """

    def compute(self, config: StageConfig, feed: FeedInput) -> StageMetric:
        state = self._initialize_state(config, feed)

        if state.Qf_m3h <= 1e-12 or state.total_area <= 1e-12:
            return self._create_empty_metric(state)

        self._solve_flow_balance(config, state)
        self._solve_hydraulics_and_energy(config, state)

        return self._build_result(config, state)

    def _initialize_state(self, config: StageConfig, feed: FeedInput) -> MFSolveState:
        state = MFSolveState()
        state.Qf_m3h = _f(getattr(feed, "flow_m3h", None), 0.0)
        state.Cf_mgL = _f(getattr(feed, "tds_mgL", None), 0.0)
        state.T_C = _f(getattr(feed, "temperature_C", None), 25.0)

        state.elements = max(1, int(_f(getattr(config, "elements", None), 1)))
        state.area_per_element = _f(getattr(config, "membrane_area_m2", None), 60.0)
        state.total_area = max(1e-9, state.elements * max(1e-9, state.area_per_element))

        state.target_recovery_pct = getattr(config, "recovery_target_pct", None)
        state.max_tmp_bar = getattr(config, "max_tmp_bar", None)

        return state

    def _solve_flow_balance(self, config: StageConfig, state: MFSolveState) -> None:
        """여과 및 역세척, CIP 주기를 분석하여 순 생산량(Net Production)과 요구 Flux 산출"""

        # 유지보수 주기 및 CIP 인자 파싱
        state.filt_min = max(
            0.1, _f(getattr(config, "filtration_cycle_min", None), 20.0)
        )
        bw_sec = max(0.0, _f(getattr(config, "backwash_duration_sec", None), 60.0))
        state.bw_min = bw_sec / 60.0
        state.cip_loss_factor = _clamp(
            _f(getattr(config, "mf_cip_loss_factor", None), 0.98), 0.7, 1.0
        )

        cycle_time_min = max(1e-6, state.filt_min + state.bw_min)
        state.filt_frac = state.filt_min / cycle_time_min
        state.bw_frac = state.bw_min / cycle_time_min

        # 역세척 플럭스 기준 설정 (입력값 없으면 기본 설계 플럭스의 2배 적용)
        input_flux = _f(getattr(config, "flux_lmh", None), 80.0)
        state.bw_flux_lmh = _f(
            getattr(config, "backwash_flux_lmh", None), input_flux * 2.0
        )
        bw_rate_m3h = (state.bw_flux_lmh * state.total_area) / 1000.0

        # 🟢 [핵심 역산 엔진 (Reverse Solver)]
        if state.target_recovery_pct is not None:
            state.recovery_pct = _clamp(state.target_recovery_pct, 0.0, 100.0)
            state.net_prod_m3h = state.Qf_m3h * (state.recovery_pct / 100.0)

            # 수학적 역산: Net = (Gross * filt_frac - BW * bw_frac) * cip_loss
            req_gross_rate_m3h = (
                (state.net_prod_m3h / state.cip_loss_factor)
                + (bw_rate_m3h * state.bw_frac)
            ) / max(1e-9, state.filt_frac)

            # 역산된 실제 멤브레인 구동 Flux
            state.flux_lmh = (req_gross_rate_m3h * 1000.0) / state.total_area
        else:
            state.flux_lmh = input_flux
            gross_prod_rate_m3h = (state.flux_lmh * state.total_area) / 1000.0

            calc_net_prod_m3h = (
                gross_prod_rate_m3h * state.filt_frac - bw_rate_m3h * state.bw_frac
            ) * state.cip_loss_factor
            state.net_prod_m3h = max(0.0, min(calc_net_prod_m3h, state.Qf_m3h))
            state.recovery_pct = (
                (state.net_prod_m3h / state.Qf_m3h * 100.0)
                if state.Qf_m3h > 1e-12
                else 0.0
            )

        state.qc_m3h = max(0.0, state.Qf_m3h - state.net_prod_m3h)

    def _solve_hydraulics_and_energy(
        self, config: StageConfig, state: MFSolveState
    ) -> None:
        """물 점도 기반의 온도 보정 계수 산출, 역산된 Flux를 기반으로 TMP 산출"""
        state.permeability_25c = _f(
            getattr(config, "mf_permeability_25c_lmh_bar", None), 500.0
        )

        mu_25_ref = get_water_viscosity_pa_s(25.0, state.Cf_mgL)
        mu_t_actual = get_water_viscosity_pa_s(state.T_C, state.Cf_mgL)
        state.temp_corr = _clamp(mu_25_ref / max(1e-9, float(mu_t_actual)), 0.25, 4.0)

        state.permeability = max(1e-9, state.permeability_25c * state.temp_corr)

        # 동적/역산된 Flux를 반영하여 정확한 막간차압(TMP) 획득
        state.tmp_bar = max(0.0, state.flux_lmh / state.permeability)

        state.p_out_bar = _f(getattr(config, "mf_p_out_bar", None), 0.5)
        header_loss = _f(getattr(config, "mf_header_loss_bar", None), 0.0)
        state.p_in_bar = state.p_out_bar + state.tmp_bar + header_loss

        pump_eff = _clamp(_f(getattr(config, "pump_eff", None), 0.75), 0.2, 0.95)
        power_kw = (
            ((state.Qf_m3h * state.p_in_bar) / 36.0 / pump_eff)
            if state.Qf_m3h > 0 and state.p_in_bar > 0
            else 0.0
        )
        state.sec_kwhm3 = (
            power_kw / state.net_prod_m3h if state.net_prod_m3h > 1e-12 else 0.0
        )

        if state.max_tmp_bar is not None and state.tmp_bar > state.max_tmp_bar:
            state.warnings.append(
                SimulationWarning(
                    stage=str(getattr(config, "stage_idx", 1)),
                    module_type=ModuleType.MF.value,
                    key="HIGH_TMP_WARN",
                    message=f"Calculated TMP ({state.tmp_bar:.2f} bar) exceeds the design limit ({state.max_tmp_bar:.2f} bar). Consider lowering target recovery or adding modules.",
                    value=state.tmp_bar,
                    limit=state.max_tmp_bar,
                    unit="bar",
                    level="WARN",
                )
            )

    def _build_result(self, config: StageConfig, state: MFSolveState) -> StageMetric:
        chem_payload: Dict[str, Any] = {
            "streams": {
                "feed": {
                    "flow_m3h": float(state.Qf_m3h),
                    "tds_mgL": float(state.Cf_mgL),
                },
                "permeate": {
                    "flow_m3h": float(state.net_prod_m3h),
                    "tds_mgL": float(state.Cf_mgL),
                    "definition": "MF permeate (TDS unchanged)",
                },
                "concentrate": {
                    "flow_m3h": float(state.qc_m3h),
                    "tds_mgL": float(state.Cf_mgL),
                    "definition": "MF waste/backwash",
                },
            },
            "model": {
                "temp_C": float(state.T_C),
                "permeability_25c_lmh_bar": float(state.permeability_25c),
                "temp_corr": float(state.temp_corr),
                "permeability_lmh_bar": float(state.permeability),
                "tmp_bar": float(state.tmp_bar),
                "filtration_min": float(state.filt_min),
                "backwash_min": float(state.bw_min),
                "filt_frac": float(state.filt_frac),
                "bw_frac": float(state.bw_frac),
                "cip_loss_factor": float(state.cip_loss_factor),
                "net_prod_m3h": float(state.net_prod_m3h),
                "gross_flux_lmh": float(state.flux_lmh),  # 역산된 Flux
            },
        }

        return StageMetric(
            stage=0,
            module_type=ModuleType.MF,
            recovery_pct=round(state.recovery_pct, 2),
            flux_lmh=round(state.flux_lmh, 1),
            ndp_bar=round(state.tmp_bar, 3),
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

    def _create_empty_metric(self, state: MFSolveState) -> StageMetric:
        chem_empty: Dict[str, Any] = {
            "streams": {
                "feed": {
                    "flow_m3h": float(state.Qf_m3h),
                    "tds_mgL": float(state.Cf_mgL),
                },
                "permeate": {
                    "flow_m3h": 0.0,
                    "tds_mgL": float(state.Cf_mgL),
                    "definition": "MF permeate",
                },
                "concentrate": {
                    "flow_m3h": float(state.Qf_m3h),
                    "tds_mgL": float(state.Cf_mgL),
                    "definition": "MF waste/backwash",
                },
            },
            "model": {
                "temp_C": float(state.T_C),
                "temp_corr": 1.0,
                "tmp_bar": 0.0,
                "net_prod_m3h": 0.0,
            },
        }
        return StageMetric(
            stage=0,
            module_type=ModuleType.MF,
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
            chemistry=chem_empty,
        )
