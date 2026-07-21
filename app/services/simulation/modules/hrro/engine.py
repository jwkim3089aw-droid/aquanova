# app/services/simulation/modules/hrro/engine.py
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from app.services.simulation.modules.base import SimulationModule
from app.schemas.common import ModuleType
from app.schemas.simulation import (
    StageConfig,
    FeedInput,
    StageMetric,
    TimeSeriesPoint,
    SimulationWarning,
    HRROMassTransferIn,
    HRROSpacerIn,
)
from app.services.chemistry import calc_scaling_indices

from .guidelines import GUIDELINES, choose_guideline_profile
from .ccro_cycle import build_ccro_cycle_spec, ccro_cycle_warnings, CCROCycleSpec
from .wave_quality import build_hrro_wave_quality_alignment, scale_ions_to_tds
from .helpers import (
    PA_TO_BAR,
    LMH_TO_MPS,
    _clamp,
    _f,
    _i,
    _get_membrane_rejections,
    _dict_to_profile,
    _apply_charge_balance,
    _extract_ions_from_feed,
    _calc_water_properties,
    _mass_transfer_coeff,
    _pressure_drop_spacer,
)

# ==========================================
# 1. 상수 정의
# ==========================================
CC_PHASE_RATIO = 0.893  # Closed-circuit 시간 대비 Flush 단계 진입 비율
VISC_REF_25C = 0.00089  # 25도 물의 동점성계수(Pa·s) 기준치
PI_COMPACTION_THRESHOLD = 25.0  # 막 압밀화(Compaction)가 시작되는 한계 삼투압 (bar)
HEADER_LOSS_BAR = 0.20  # 하우징 헤더 압력 손실 기본값


@dataclass
class HRROSolveState:
    Qf_m3h: float = 0.0
    Cf_mgL: float = 0.0
    T_C: float = 25.0
    ph: float = 7.0
    target_recovery_pct: float = 90.0

    feed_ions: Dict[str, float] = field(default_factory=dict)
    ion_rejections: Dict[str, float] = field(default_factory=dict)
    bulk_rejection_pct: float = 99.5
    tot_perm_mass_ions: Dict[str, float] = field(default_factory=dict)
    tot_perm_vol: float = 0.0

    vessel_count: int = 1
    elements_per_vessel: int = 6
    total_area_m2: float = 0.0
    A_base: float = 0.0
    B_base: float = 0.0
    pump_eff: float = 0.8
    stage_no: int = 1

    sp_h_m: float = 0.00076
    sp_eps: float = 0.85
    dh_m: float = 0.0
    diffusivity_m2_s: float = 1.5e-9
    channel_area_m2: float = 0.015
    q_circ_est_m3h: float = 0.0
    loop_volume_m3: float = 1.36
    dt_minutes: float = 0.5
    max_minutes: float = 30.0
    b_sal_slope: float = 0.45
    compaction_k: float = 0.003
    back_pressure_bar: float = 0.0
    max_tmp_bar: float = 120.0

    override_dp_elem: float = -1.0
    cp_tuning: float = 1.0
    fouling_factor: float = 1.0
    b_fouling_factor: float = 1.0
    pressure_limited: bool = False
    target_recovery_achieved: bool = True
    recovery_error_fraction: float = 0.0
    target_perm_volume_m3: float = 0.0

    history: List[TimeSeriesPoint] = field(default_factory=list)
    warnings: List[SimulationWarning] = field(default_factory=list)
    Qp_m3h: float = 0.0
    Qc_m3h: float = 0.0
    avg_flux_lmh: float = 0.0

    avg_cp_mgL: float = 0.0
    calc_cc_mgL: float = 0.0
    avg_cp_ions: Dict[str, float] = field(default_factory=dict)
    calc_cc_ions: Dict[str, float] = field(default_factory=dict)

    final_cc_tds: float = 0.0
    max_p_in_bar: float = 0.0
    avg_ndp_bar: float = 0.0
    avg_sec_kwhm3: float = 0.0
    actual_recovery_pct: float = 0.0

    # WAVE-style CCRO/PF operating diagnostics
    pf_feed_ratio_pct: float = 120.0
    pf_recovery_pct: float = 10.0
    cc_recycle_m3h_per_pv: float = 0.0
    pf_cp_assist_enabled: bool = False
    pf_cp_assist_flow_m3h_per_pv: float = 0.0
    pf_mode: str = "wave_true_plug_flow"
    min_concentrate_flow_m3h_per_pv: float = 0.0
    p3_recycle_capacity_m3h_per_pv: float = 0.0
    drain_low_threshold_m3h_per_pv: float = 0.0
    adaptive_recovery_enabled: bool = False
    requested_target_recovery_pct: float = 90.0
    brine_conductivity_limit_mgL: float = 0.0
    adaptive_min_recovery_pct: float = 50.0
    recovery_stop_reason: str = "target_recovery_reached"
    hpp_sizing_mode: str = "base"
    hpp_count: int = 1
    p3_generated_head_bar: float = 0.6
    p3_casing_pressure_rating_bar: float = 12.0
    rinse_volume_m3: float = 0.0
    rinse_interval_cycles: int = 1
    rinse_uses_permeate: bool = False
    cycle_spec: Optional[CCROCycleSpec] = None
    membrane_model_name: str = ""
    wave_quality_alignment_enabled: bool = True
    wave_quality_alignment: Dict[str, Any] = field(default_factory=dict)
    wave_quality_config: Dict[str, Any] = field(default_factory=dict)


class HRROModule(SimulationModule):
    def compute(self, config: StageConfig, feed: FeedInput) -> StageMetric:
        state = self._initialize_state(config, feed)
        if state.Qf_m3h <= 1e-12 or state.total_area_m2 <= 1e-12 or state.A_base <= 0.0:
            return self._build_empty_metric(state)

        self._simulate_batch_cycle(state)
        self._aggregate_results(state)
        guideline_used, violations = self._evaluate_guidelines(feed, config, state)

        return self._build_result(state, guideline_used, violations)

    def _initialize_state(self, config: StageConfig, feed: FeedInput) -> HRROSolveState:
        s = HRROSolveState()

        cfg_dict = {}
        if hasattr(config, "model_dump"):
            cfg_dict = config.model_dump()
        elif hasattr(config, "dict"):
            cfg_dict = config.dict()

        if hasattr(config, "model_extra") and config.model_extra:
            cfg_dict.update(config.model_extra)

        s.Qf_m3h = _f(
            cfg_dict.get("feed_flow_m3h")
            or getattr(config, "feed_flow_m3h", None)
            or getattr(feed, "flow_m3h", None),
            100.0,
        )
        s.target_recovery_pct = _clamp(
            _f(
                cfg_dict.get("recovery_target_pct")
                or getattr(config, "recovery_target_pct", None),
                90.0,
            ),
            0.0,
            99.5,
        )
        s.requested_target_recovery_pct = s.target_recovery_pct
        s.T_C = _f(getattr(feed, "temperature_C", None), 25.0)
        s.ph = _f(getattr(feed, "ph", None), 7.0)

        s.feed_ions = _extract_ions_from_feed(feed)
        s.Cf_mgL = (
            sum(s.feed_ions.values())
            if s.feed_ions
            else _f(getattr(feed, "tds_mgL", None), 0.0)
        )

        s.stage_no = _i(
            cfg_dict.get("stage")
            or getattr(config, "stage", None)
            or cfg_dict.get("stage_no")
            or getattr(config, "stage_no", None),
            1,
        )
        s.vessel_count = max(
            1,
            _i(
                cfg_dict.get("vessel_count") or getattr(config, "vessel_count", None),
                20,
            ),
        )
        s.elements_per_vessel = _i(
            cfg_dict.get("elements_per_vessel")
            or getattr(config, "elements_per_vessel", None)
            or cfg_dict.get("elements")
            or getattr(config, "elements", None),
            5,
        )

        if s.elements_per_vessel > 50:
            s.elements_per_vessel //= s.vessel_count
        if s.elements_per_vessel <= 0:
            s.elements_per_vessel = 5

        A0 = _f(
            cfg_dict.get("membrane_A_lmh_bar")
            or getattr(config, "membrane_A_lmh_bar", None),
            5.50,
        )
        B0 = _f(
            cfg_dict.get("membrane_B_lmh") or getattr(config, "membrane_B_lmh", None),
            0.060,
        )

        A_corr = _f(
            cfg_dict.get("A_correction_factor")
            or getattr(config, "A_correction_factor", 1.0),
            1.0,
        )
        B_corr = _f(
            cfg_dict.get("B_correction_factor")
            or getattr(config, "B_correction_factor", 1.0),
            1.0,
        )
        s.fouling_factor = _clamp(
            _f(
                (
                    cfg_dict.get("fouling_factor")
                    if cfg_dict.get("fouling_factor") is not None
                    else getattr(config, "fouling_factor", 1.0)
                ),
                1.0,
            ),
            0.05,
            1.20,
        )
        s.b_fouling_factor = _clamp(
            _f(
                (
                    cfg_dict.get("B_fouling_factor")
                    if cfg_dict.get("B_fouling_factor") is not None
                    else getattr(config, "B_fouling_factor", 1.0)
                ),
                1.0,
            ),
            0.05,
            20.0,
        )

        dp_in = cfg_dict.get("dp_per_elem_bar")
        if dp_in is None:
            dp_in = getattr(config, "dp_per_elem_bar", None)
        if dp_in is None:
            dp_in = cfg_dict.get("dp_module_bar") or getattr(
                config, "dp_module_bar", None
            )
        if dp_in is None:
            dp_in = cfg_dict.get("dp_per_elem_bar") or getattr(
                config, "dp_per_elem_bar", None
            )
        s.override_dp_elem = _f(dp_in, -1.0)

        cp_in = cfg_dict.get("cp_tuning_factor") or getattr(
            config, "cp_tuning_factor", None
        )
        if cp_in is None:
            cp_in = cfg_dict.get("cp_adjustment_factor") or getattr(
                config, "cp_adjustment_factor", 1.0
            )
        s.cp_tuning = _f(cp_in, 1.0)

        area_per_elem = _f(
            cfg_dict.get("membrane_area_m2")
            or getattr(config, "membrane_area_m2", None),
            37.16,
        )

        model_name = str(
            cfg_dict.get("membrane_model") or getattr(config, "membrane_model", "")
        ).lower()
        s.membrane_model_name = model_name
        s.wave_quality_alignment_enabled = bool(
            cfg_dict.get("wave_quality_alignment_enabled", True)
        )
        s.wave_quality_config = {
            "wave_effective_salt_passage_pct": cfg_dict.get("wave_effective_salt_passage_pct"),
            "wave_product_tds_target_mgL": cfg_dict.get("wave_product_tds_target_mgL"),
            "wave_final_concentrate_tds_target_mgL": cfg_dict.get("wave_final_concentrate_tds_target_mgL"),
            "wave_salt_passage_recovery_coeff": cfg_dict.get("wave_salt_passage_recovery_coeff"),
        }
        s.bulk_rejection_pct, s.ion_rejections = _get_membrane_rejections(model_name)

        s.total_area_m2 = (s.vessel_count * s.elements_per_vessel) * area_per_elem

        ff = _f(
            cfg_dict.get("flow_factor") or getattr(config, "flow_factor", None), 1.0
        )
        temp_corr_A = _f(
            cfg_dict.get("temp_corr_factor_A")
            or getattr(config, "temp_corr_factor_A", 2640.0),
            2640.0,
        )
        temp_corr_B = _f(
            cfg_dict.get("temp_corr_factor_B")
            or getattr(config, "temp_corr_factor_B", 3500.0),
            3500.0,
        )

        T_K = s.T_C + 273.15
        TEMP_REF_K = 298.15

        tcf_A = math.exp(temp_corr_A * (1.0 / TEMP_REF_K - 1.0 / T_K))
        tcf_B = math.exp(temp_corr_B * (1.0 / TEMP_REF_K - 1.0 / T_K))

        s.A_base = A0 * A_corr * ff * tcf_A * s.fouling_factor
        s.B_base = B0 * B_corr * tcf_B * s.b_fouling_factor
        s.pump_eff = _f(
            cfg_dict.get("pump_eff") or getattr(config, "pump_eff", None), 0.80
        )

        sp = getattr(config, "spacer", None) or HRROSpacerIn()
        s.sp_h_m = _f(getattr(sp, "thickness_mm", None), 0.76) / 1000.0
        s.sp_eps = _f(getattr(sp, "voidage", None), 0.85)
        s.dh_m = float(
            getattr(sp, "hydraulic_diameter_m", None)
            or max(2.0 * s.sp_h_m * s.sp_eps / (2.0 - s.sp_eps), 1e-6)
        )

        mt = getattr(config, "mass_transfer", None) or HRROMassTransferIn()
        s.diffusivity_m2_s = _f(getattr(mt, "diffusivity_m2_s", None), 1.5e-9)
        s.channel_area_m2 = _f(getattr(mt, "feed_channel_area_m2", None), 0.015)

        s.q_circ_est_m3h = _f(
            cfg_dict.get("recirc_flow_m3h") or getattr(config, "recirc_flow_m3h", None),
            120.0,
        ) / max(s.vessel_count, 1)
        s.loop_volume_m3 = _f(
            cfg_dict.get("loop_volume_m3") or getattr(config, "loop_volume_m3", None),
            1.36,
        )
        s.dt_minutes = max(
            0.05,
            _f(cfg_dict.get("timestep_s") or getattr(config, "timestep_s", None), 30.0)
            / 60.0,
        )
        s.max_minutes = max(
            1.0,
            _f(
                cfg_dict.get("max_minutes") or getattr(config, "max_minutes", None),
                30.0,
            ),
        )
        s.b_sal_slope = _clamp(
            _f(
                cfg_dict.get("b_salinity_slope")
                or getattr(config, "b_salinity_slope", None)
                or cfg_dict.get("hrro_B_sal_slope")
                or getattr(config, "hrro_B_sal_slope", None),
                0.45,
            ),
            0.0,
            20.0,
        )
        s.compaction_k = _f(
            cfg_dict.get("hrro_A_compaction_k")
            or getattr(config, "hrro_A_compaction_k", None),
            0.003,
        )
        s.back_pressure_bar = _f(
            cfg_dict.get("permeate_back_pressure_bar")
            or getattr(config, "permeate_back_pressure_bar", None),
            0.0,
        )
        s.max_tmp_bar = _f(
            cfg_dict.get("max_tmp_bar") or getattr(config, "max_tmp_bar", None), 120.0
        )

        s.pf_feed_ratio_pct = max(
            0.0,
            _f(
                cfg_dict.get("pf_feed_ratio_pct")
                or getattr(config, "pf_feed_ratio_pct", None),
                120.0,
            ),
        )
        s.pf_recovery_pct = _clamp(
            _f(
                cfg_dict.get("pf_recovery_pct")
                or getattr(config, "pf_recovery_pct", None),
                10.0,
            ),
            0.0,
            95.0,
        )
        s.cc_recycle_m3h_per_pv = _f(
            cfg_dict.get("cc_recycle_m3h_per_pv")
            or getattr(config, "cc_recycle_m3h_per_pv", None),
            0.0,
        )
        s.pf_cp_assist_enabled = bool(
            cfg_dict.get("pf_cp_assist_enabled")
            or getattr(config, "pf_cp_assist_enabled", False)
        )
        s.pf_cp_assist_flow_m3h_per_pv = _f(
            cfg_dict.get("pf_cp_assist_flow_m3h_per_pv")
            or getattr(config, "pf_cp_assist_flow_m3h_per_pv", None),
            0.0,
        )
        s.pf_mode = str(
            cfg_dict.get("pf_mode")
            or getattr(config, "pf_mode", None)
            or "wave_true_plug_flow"
        )
        s.min_concentrate_flow_m3h_per_pv = _f(
            cfg_dict.get("min_concentrate_flow_m3h_per_pv")
            or getattr(config, "min_concentrate_flow_m3h_per_pv", None),
            s.cc_recycle_m3h_per_pv,
        )
        s.p3_recycle_capacity_m3h_per_pv = _f(
            cfg_dict.get("p3_recycle_capacity_m3h_per_pv")
            or getattr(config, "p3_recycle_capacity_m3h_per_pv", None),
            0.0,
        )
        s.drain_low_threshold_m3h_per_pv = _f(
            cfg_dict.get("drain_low_threshold_m3h_per_pv")
            or getattr(config, "drain_low_threshold_m3h_per_pv", None),
            0.0,
        )
        s.adaptive_recovery_enabled = bool(
            cfg_dict.get("adaptive_recovery_enabled")
            or getattr(config, "adaptive_recovery_enabled", False)
        )
        s.brine_conductivity_limit_mgL = _f(
            cfg_dict.get("brine_conductivity_limit_mgL")
            or cfg_dict.get("brine_tds_limit_mgL")
            or getattr(config, "brine_conductivity_limit_mgL", None)
            or getattr(config, "brine_tds_limit_mgL", None),
            0.0,
        )
        s.adaptive_min_recovery_pct = _clamp(
            _f(
                cfg_dict.get("adaptive_min_recovery_pct")
                or getattr(config, "adaptive_min_recovery_pct", None),
                50.0,
            ),
            0.0,
            99.5,
        )
        s.hpp_sizing_mode = str(
            cfg_dict.get("hpp_sizing_mode") or getattr(config, "hpp_sizing_mode", "base")
        ).lower()
        s.hpp_count = max(1, _i(cfg_dict.get("hpp_count") or getattr(config, "hpp_count", 1), 1))
        s.p3_generated_head_bar = _f(
            cfg_dict.get("p3_generated_head_bar")
            or getattr(config, "p3_generated_head_bar", None),
            0.6,
        )
        s.p3_casing_pressure_rating_bar = _f(
            cfg_dict.get("p3_casing_pressure_rating_bar")
            or getattr(config, "p3_casing_pressure_rating_bar", None),
            12.0,
        )

        if s.adaptive_recovery_enabled and s.brine_conductivity_limit_mgL > max(s.Cf_mgL, 1e-9):
            # Simple protective CC stop approximation: final brine concentration
            # cannot exceed the configured conductivity/TDS limit. This separates
            # target recovery from actual cycle recovery.
            max_rec_by_brine = _clamp(
                (1.0 - (s.Cf_mgL / max(s.brine_conductivity_limit_mgL, 1e-9))) * 100.0,
                s.adaptive_min_recovery_pct,
                s.target_recovery_pct,
            )
            if max_rec_by_brine < s.target_recovery_pct - 1e-9:
                s.target_recovery_pct = max_rec_by_brine
                s.recovery_stop_reason = "brine_conductivity_limit"
        elif s.adaptive_recovery_enabled:
            s.recovery_stop_reason = "target_recovery_reached"

        s.rinse_volume_m3 = max(
            0.0,
            _f(
                cfg_dict.get("rinse_volume_m3")
                or getattr(config, "rinse_volume_m3", None),
                0.0,
            ),
        )
        s.rinse_interval_cycles = max(
            1,
            _i(
                cfg_dict.get("rinse_interval_cycles")
                or getattr(config, "rinse_interval_cycles", None),
                1,
            ),
        )
        s.rinse_uses_permeate = bool(
            cfg_dict.get("rinse_uses_permeate")
            or getattr(config, "rinse_uses_permeate", False)
        )

        s.cycle_spec = build_ccro_cycle_spec(
            net_feed_flow_m3h=s.Qf_m3h,
            target_recovery_pct=s.target_recovery_pct,
            vessel_count=s.vessel_count,
            loop_volume_m3=s.loop_volume_m3,
            cc_recycle_m3h_per_pv=s.cc_recycle_m3h_per_pv,
            recirc_flow_m3h_total=(s.q_circ_est_m3h * max(s.vessel_count, 1)),
            pf_feed_ratio_pct=s.pf_feed_ratio_pct,
            pf_recovery_pct=s.pf_recovery_pct,
            pf_cp_assist_enabled=s.pf_cp_assist_enabled,
            pf_cp_assist_flow_m3h_per_pv=s.pf_cp_assist_flow_m3h_per_pv,
            pf_mode=s.pf_mode,
            min_concentrate_flow_m3h_per_pv=s.min_concentrate_flow_m3h_per_pv,
            p3_recycle_capacity_m3h_per_pv=s.p3_recycle_capacity_m3h_per_pv,
            drain_low_threshold_m3h_per_pv=s.drain_low_threshold_m3h_per_pv,
            rinse_volume_m3=s.rinse_volume_m3,
            rinse_interval_cycles=s.rinse_interval_cycles,
            rinse_uses_permeate=s.rinse_uses_permeate,
        )

        return s

    def _simulate_batch_cycle(self, state: HRROSolveState) -> None:
        v_sys = state.loop_volume_m3
        Qp_target = state.Qf_m3h * (state.target_recovery_pct / 100.0)

        spec = state.cycle_spec or build_ccro_cycle_spec(
            net_feed_flow_m3h=state.Qf_m3h,
            target_recovery_pct=state.target_recovery_pct,
            vessel_count=state.vessel_count,
            loop_volume_m3=state.loop_volume_m3,
            cc_recycle_m3h_per_pv=state.cc_recycle_m3h_per_pv,
            recirc_flow_m3h_total=(state.q_circ_est_m3h * max(state.vessel_count, 1)),
            pf_feed_ratio_pct=state.pf_feed_ratio_pct,
            pf_recovery_pct=state.pf_recovery_pct,
            pf_cp_assist_enabled=state.pf_cp_assist_enabled,
            pf_cp_assist_flow_m3h_per_pv=state.pf_cp_assist_flow_m3h_per_pv,
            pf_mode=state.pf_mode,
            min_concentrate_flow_m3h_per_pv=state.min_concentrate_flow_m3h_per_pv,
            p3_recycle_capacity_m3h_per_pv=state.p3_recycle_capacity_m3h_per_pv,
            drain_low_threshold_m3h_per_pv=state.drain_low_threshold_m3h_per_pv,
            rinse_volume_m3=state.rinse_volume_m3,
            rinse_interval_cycles=state.rinse_interval_cycles,
            rinse_uses_permeate=state.rinse_uses_permeate,
        )
        state.cycle_spec = spec
        t_cc_min = max(0.0, spec.cc_sequence_duration_min)
        t_cycle_min = max(t_cc_min, spec.complete_sequence_duration_min)
        state.target_perm_volume_m3 = max(Qp_target * (t_cc_min / 60.0), 1e-12)

        cf0_ions = state.feed_ions if state.feed_ions else {"tds_bulk": state.Cf_mgL}
        sys_salt_g_ions = {ion: conc * v_sys for ion, conc in cf0_ions.items()}

        target_flux_lmh = (Qp_target * 1000.0) / max(1e-9, state.total_area_m2)
        bulk_passage = max(1e-6, 1.0 - (state.bulk_rejection_pct / 100.0))

        t_current = 0.0
        dt_minutes = state.dt_minutes

        while t_current <= t_cycle_min + 1e-9:
            cf_loop_ions = {ion: mass / v_sys for ion, mass in sys_salt_g_ions.items()}
            cf_loop = sum(cf_loop_ions.values())
            state.final_cc_tds = cf_loop

            Qp_pv = (
                target_flux_lmh * state.total_area_m2 / max(state.vessel_count, 1)
            ) / 1000.0
            is_pf = t_current > t_cc_min
            if not is_pf:
                Q_recirc_pv = spec.cc_concentrate_flow_m3h_per_pv
                Q_feed_pv = Qp_pv
                Q_blend_pv = spec.cc_net_feed_flow_m3h_per_pv or (Q_feed_pv + Q_recirc_pv)
            else:
                Q_recirc_pv = (
                    spec.pf_cp_assist_flow_m3h_per_pv
                    if spec.pf_cp_assist_enabled
                    else 0.0
                )
                Q_feed_pv = spec.pf_feed_flow_m3h_per_pv
                Q_blend_pv = max(Q_feed_pv + Q_recirc_pv, Qp_pv, 1e-9)

            # 🚀 [패치 1] 정밀 질량 수지 및 수렴 모델 이식
            # 단순 산술 평균이 아니라, Film Theory(필름 이론) 기반의 농도 분극 수렴(Iterative) 계산 도입
            cf_blend_ions = {
                ion: (Q_feed_pv * cf0_ions[ion] + Q_recirc_pv * cf_loop_ions[ion])
                / max(Q_blend_pv, 1e-6)
                for ion in cf0_ions
            }

            # 루프 회수율 (이 순간 엘리먼트를 통과하며 뽑히는 물의 비율)
            rec_inst = max(1e-9, min(0.99, Qp_pv / max(1e-9, Q_blend_pv)))
            conc_factor = math.log(1.0 / (1.0 - rec_inst)) / rec_inst

            # 멤브레인을 흐르는 유체의 진정한 평균 농도(Bulk)
            cf_avg_ions = {ion: cf_blend_ions[ion] * conc_factor for ion in cf0_ions}
            cf_avg = sum(cf_avg_ions.values())

            bulk_prof = _dict_to_profile(cf_avg_ions, state.T_C, state.ph)
            rho, mu, pi_bulk = _calc_water_properties(bulk_prof)

            v_cross = max(
                (Q_blend_pv / 3600.0) / (state.channel_area_m2 * state.sp_eps), 0.05
            )
            visc_ratio = VISC_REF_25C / max(mu, 1e-6)
            D_eff = state.diffusivity_m2_s * _clamp((visc_ratio**0.8), 0.2, 5.0)

            k_mt = _mass_transfer_coeff(rho, mu, v_cross, state.dh_m, D_eff)

            # 🚀 [패치 2] 동적 농도 분극 최적화 루프
            # 막을 통과하는 염(Cp)이 막 표면 농도(C_wall)에 영향을 주므로 수렴시킵니다.
            cp_inst_ions = {ion: 0.0 for ion in cf0_ions}
            cp_inst = 0.0
            wall_tds = 0.0

            # Newton-Raphson 유사 반복 수렴
            for _ in range(5):
                # Match RO/NF semantics: a larger tuning factor represents
                # stronger mass transfer and therefore lower concentration polarization.
                effective_k_mt = max(k_mt * _clamp(state.cp_tuning, 0.05, 20.0), 1e-9)
                beta = math.exp(
                    min((target_flux_lmh * LMH_TO_MPS) / effective_k_mt, 5.0)
                )

                wall_tds_ions = {
                    ion: (cf_avg_ions[ion] - cp_inst_ions[ion]) * beta
                    + cp_inst_ions[ion]
                    for ion in cf0_ions
                }
                wall_tds = sum(wall_tds_ions.values())

                B_eff_bulk = state.B_base * (
                    1.0 + state.b_sal_slope * min(wall_tds / 35000.0, 15.0)
                )

                new_cp_inst_ions = {}
                for ion, conc in wall_tds_ions.items():
                    R_i = state.ion_rejections.get(
                        ion, state.bulk_rejection_pct / 100.0
                    )
                    ratio = (1.0 - R_i) / bulk_passage
                    B_eff_ion = B_eff_bulk * ratio
                    new_cp_inst_ions[ion] = (
                        (B_eff_ion * conc) / (target_flux_lmh + B_eff_ion)
                        if B_eff_ion > 0
                        else 0.0
                    )

                cp_inst_ions = new_cp_inst_ions
                cp_inst = sum(cp_inst_ions.values())

            wall_prof = _dict_to_profile(wall_tds_ions, state.T_C, state.ph)
            _, _, pi_wall = _calc_water_properties(wall_prof)

            A_eff = state.A_base
            if pi_wall > PI_COMPACTION_THRESHOLD:
                A_eff *= math.exp(
                    -state.compaction_k * (pi_wall - PI_COMPACTION_THRESHOLD)
                )

            ndp_req = target_flux_lmh / max(A_eff, 0.1)
            flux_shift_factor = max(0.85, 1.0 - (cf_avg / 35000.0))
            ndp_req *= flux_shift_factor

            if state.override_dp_elem > 0:
                dp_mod = state.override_dp_elem * float(state.elements_per_vessel)
            else:
                dp_mod = _pressure_drop_spacer(
                    rho, mu, v_cross, state.dh_m, 1.016
                ) * float(state.elements_per_vessel)

            p_req = (
                pi_wall
                + ndp_req
                + (dp_mod * 0.5)
                + state.back_pressure_bar
                + HEADER_LOSS_BAR
            )

            if p_req > state.max_tmp_bar:
                state.pressure_limited = True
                p_req = state.max_tmp_bar
                target_flux_lmh = A_eff * max(
                    0.0, p_req - pi_wall - (dp_mod * 0.5) - state.back_pressure_bar
                )
                if target_flux_lmh <= 0.1:
                    break

            Qp_inst = (target_flux_lmh * state.total_area_m2) / 1000.0
            pwr_kw = (state.Qf_m3h * p_req) / (36.0 * max(0.1, state.pump_eff))
            sec_inst = pwr_kw / max(Qp_inst, 1e-6)
            r_inst = state.target_recovery_pct * min(
                1.0,
                state.tot_perm_vol / max(state.target_perm_volume_m3, 1e-12),
            )

            # p_req is recalculated for every CC and PF sample from the
            # current blended feed, osmotic pressure, required NDP, spacer
            # pressure drop, back pressure, and header loss.
            #
            # Do not carry the terminal CC pressure into PF history. Doing so
            # hides the P-2 VFD pressure reduction even though hydraulics and
            # energy are already using the newly calculated PF pressure.
            rec_p_req = p_req
            rec_cf_loop = (
                state.history[-1].tds_mgL if is_pf and state.history else cf_loop
            )
            rec_cp_inst = (
                state.history[-1].permeate_tds_mgL
                if is_pf and state.history
                else cp_inst
            )

            state.history.append(
                TimeSeriesPoint(
                    time_min=round(t_current, 3),
                    recovery_pct=round(r_inst, 2),
                    pressure_bar=round(float(rec_p_req), 2),
                    tds_mgL=round(float(rec_cf_loop), 0),
                    flux_lmh=round(float(target_flux_lmh), 2),
                    ndp_bar=round(float(ndp_req), 2),
                    permeate_flow_m3h=round(float(Qp_inst), 4),
                    permeate_tds_mgL=round(float(rec_cp_inst), 2),
                    specific_energy_kwh_m3=round(float(sec_inst), 2),
                    phase="PF" if is_pf else "CC",
                    feed_flow_m3h=round(float(Q_feed_pv * max(state.vessel_count, 1)), 4),
                    recirc_flow_m3h=round(float(Q_recirc_pv * max(state.vessel_count, 1)), 4),
                    concentrate_flow_m3h=round(
                        float(
                            (
                                spec.pf_concentrate_flow_m3h_per_pv
                                if is_pf
                                else spec.cc_concentrate_flow_m3h_per_pv
                            )
                            * max(state.vessel_count, 1)
                        ),
                        4,
                    ),
                )
            )

            if t_current >= t_cycle_min:
                break

            step_dt = min(dt_minutes, t_cycle_min - t_current)
            dt_hr = step_dt / 60.0

            if t_current <= t_cc_min:
                for ion in cf0_ions:
                    mass_in = (
                        Q_feed_pv * max(state.vessel_count, 1) * cf0_ions[ion] * dt_hr
                    )
                    mass_out = Qp_inst * cp_inst_ions[ion] * dt_hr
                    sys_salt_g_ions[ion] += mass_in - mass_out
            else:
                flush_rate = spec.pf_concentrate_flow_m3h_per_pv * max(state.vessel_count, 1)
                for ion in cf0_ions:
                    mass_in = (
                        Q_feed_pv * max(state.vessel_count, 1) * cf0_ions[ion] * dt_hr
                    )
                    mass_out = Qp_inst * cp_inst_ions[ion] * dt_hr
                    mass_flush = flush_rate * cf_loop_ions[ion] * dt_hr
                    sys_salt_g_ions[ion] = max(
                        sys_salt_g_ions[ion] + mass_in - mass_out - mass_flush,
                        v_sys * cf0_ions[ion],
                    )

            v_i = Qp_inst * dt_hr
            state.tot_perm_vol += v_i
            for ion in cf0_ions:
                state.tot_perm_mass_ions[ion] = (
                    state.tot_perm_mass_ions.get(ion, 0.0) + cp_inst_ions[ion] * v_i
                )

            t_current += step_dt

    def _aggregate_results(self, state: HRROSolveState) -> None:
        tot_vol, tot_nrg, tot_ndp = 0.0, 0.0, 0.0
        dt_hr = state.dt_minutes / 60.0

        for pt in state.history:
            v_i = (pt.permeate_flow_m3h or 0.0) * dt_hr
            tot_vol += v_i
            tot_nrg += (pt.specific_energy_kwh_m3 or 0.0) * v_i
            tot_ndp += (pt.ndp_bar or 0.0) * v_i

        state.avg_sec_kwhm3 = (tot_nrg / tot_vol) if tot_vol > 0 else 0.0
        state.avg_ndp_bar = (tot_ndp / tot_vol) if tot_vol > 0 else 0.0
        state.max_p_in_bar = max((pt.pressure_bar for pt in state.history), default=0.0)

        if state.history:
            last = state.history[-1]
            achieved_ratio = min(
                1.0,
                state.tot_perm_vol / max(state.target_perm_volume_m3, 1e-12),
            )
            state.actual_recovery_pct = state.target_recovery_pct * achieved_ratio
            state.Qp_m3h = state.Qf_m3h * (state.actual_recovery_pct / 100.0)
            state.Qc_m3h = max(1e-12, state.Qf_m3h - state.Qp_m3h)
            state.max_p_in_bar = max(state.max_p_in_bar, last.pressure_bar)
        else:
            state.actual_recovery_pct = 0.0
            state.Qp_m3h = 0.0
            state.Qc_m3h = state.Qf_m3h
            state.max_p_in_bar = state.max_tmp_bar if state.pressure_limited else 0.0

        if state.pressure_limited and state.recovery_stop_reason == "target_recovery_reached":
            state.recovery_stop_reason = "pressure_safety_limit"

        state.recovery_error_fraction = abs(
            state.actual_recovery_pct - state.target_recovery_pct
        ) / max(abs(state.target_recovery_pct), 1e-12)
        state.target_recovery_achieved = state.recovery_error_fraction <= 1e-3

        avg_cp_ions = {}
        if state.tot_perm_vol > 0:
            for ion, mass in state.tot_perm_mass_ions.items():
                avg_cp_ions[ion] = mass / state.tot_perm_vol
        else:
            avg_cp_ions = {ion: 0.0 for ion in state.feed_ions}

        avg_cp_ions = _apply_charge_balance(avg_cp_ions)
        state.avg_cp_mgL = sum(avg_cp_ions.values()) if avg_cp_ions else 0.0
        state.avg_cp_ions = avg_cp_ions

        calc_cc_ions = {}
        for ion, cf_ion in state.feed_ions.items():
            cp_ion = avg_cp_ions.get(ion, 0.0)
            cc_ion = (state.Qf_m3h * cf_ion - state.Qp_m3h * cp_ion) / max(
                state.Qc_m3h, 1e-6
            )
            calc_cc_ions[ion] = max(cc_ion, 0.0)

        state.calc_cc_mgL = (
            sum(calc_cc_ions.values()) if calc_cc_ions else state.final_cc_tds
        )
        state.calc_cc_ions = calc_cc_ions

        if state.wave_quality_alignment_enabled and state.Qf_m3h > 0 and state.Qp_m3h > 0 and state.Qc_m3h > 0:
            quality = build_hrro_wave_quality_alignment(
                feed_tds_mgL=state.Cf_mgL,
                feed_flow_m3h=state.Qf_m3h,
                product_flow_m3h=state.Qp_m3h,
                concentrate_flow_m3h=state.Qc_m3h,
                recovery_pct=state.actual_recovery_pct,
                bulk_rejection_pct=state.bulk_rejection_pct,
                membrane_model=state.membrane_model_name,
                raw_engine_product_tds_mgL=state.avg_cp_mgL,
                raw_engine_concentrate_tds_mgL=state.calc_cc_mgL,
                config=state.wave_quality_config,
            )
            state.wave_quality_alignment = quality.model_dump()
            state.avg_cp_mgL = quality.product_tds_mgL
            state.calc_cc_mgL = quality.final_concentrate_tds_mgL
            state.avg_cp_ions = scale_ions_to_tds(state.avg_cp_ions, state.avg_cp_mgL)
            state.calc_cc_ions = scale_ions_to_tds(state.calc_cc_ions, state.calc_cc_mgL)

        state.avg_flux_lmh = (
            ((state.Qp_m3h * 1000.0) / state.total_area_m2)
            if state.total_area_m2 > 0
            else 0.0
        )

    def _evaluate_guidelines(
        self, feed: FeedInput, config: StageConfig, state: HRROSolveState
    ) -> Tuple[Tuple[str, str], List[Dict[str, Any]]]:
        prof, reason = choose_guideline_profile(
            water_type=getattr(feed, "water_type", None),
            water_subtype=getattr(feed, "water_subtype", None),
            sdi15=getattr(feed, "sdi15", None),
            tds_mgL=state.Cf_mgL,
        )
        area_per_element = state.total_area_m2 / max(1, state.vessel_count * state.elements_per_vessel)
        inch = 8 if area_per_element >= 20.0 else 4
        g = (
            GUIDELINES.get(prof, {}).get(inch)
            or GUIDELINES.get("시수 (Municipal Supply)", {}).get(inch)
            or {}
        )
        v_list = []

        def _fail(k: str, msg: str, val: float, limit: Any, unit: str):
            v_list.append(
                {"key": k, "message": msg, "value": val, "limit": limit, "unit": unit}
            )

        avg_f = state.avg_flux_lmh
        rng = g.get("avg_flux_range_lmh")
        if isinstance(rng, tuple) and not (rng[0] <= avg_f <= rng[1]):
            _fail(
                "avg_flux_range",
                f"평균 플럭스 {avg_f:.2f} LMH가 범위 이탈.",
                avg_f,
                {"min": rng[0], "max": rng[1]},
                "LMH",
            )

        # For CCRO/HRRO, WAVE's minimum concentrate-flow guideline refers to
        # the closed-circuit recycle/crossflow through each pressure vessel,
        # not the small net brine leaving the plant at 90%+ recovery.
        qc_pv = (
            state.cycle_spec.cc_concentrate_flow_m3h_per_pv
            if state.cycle_spec is not None
            else (state.Qc_m3h / state.vessel_count if state.vessel_count > 0 else 0.0)
        )
        if (
            g.get("conc_flow_min_m3h_per_vessel")
            and qc_pv + 1e-12 < g["conc_flow_min_m3h_per_vessel"]
        ):
            _fail(
                "conc_flow_min",
                f"농축수 유량 {qc_pv:.2f} m³/h 미달.",
                qc_pv,
                g["conc_flow_min_m3h_per_vessel"],
                "m3/h",
            )

        qf_pv = (
            state.cycle_spec.cc_net_feed_flow_m3h_per_pv
            if state.cycle_spec is not None
            else (state.Qf_m3h / state.vessel_count if state.vessel_count > 0 else 0.0)
        )
        if (
            g.get("feed_flow_max_m3h_per_vessel")
            and qf_pv > g["feed_flow_max_m3h_per_vessel"] + 1e-9
        ):
            _fail(
                "feed_flow_max",
                f"유입수 유량 {qf_pv:.2f} m³/h 초과.",
                qf_pv,
                g["feed_flow_max_m3h_per_vessel"],
                "m3/h",
            )

        if state.cycle_spec is not None:
            v_list.extend(ccro_cycle_warnings(state.cycle_spec))

        if state.adaptive_recovery_enabled and state.recovery_stop_reason != "target_recovery_reached":
            _fail(
                "adaptive_recovery_stop",
                "목표 회수율 전에 보호 조건에 도달해 CC를 조기 종료하고 실제 회수율을 낮춥니다.",
                state.actual_recovery_pct or state.target_recovery_pct,
                {
                    "requested_target_recovery_pct": state.requested_target_recovery_pct,
                    "stop_reason": state.recovery_stop_reason,
                    "brine_conductivity_limit_mgL": state.brine_conductivity_limit_mgL,
                },
                "%",
            )

        if state.p3_casing_pressure_rating_bar > 0 and state.max_p_in_bar > state.p3_casing_pressure_rating_bar + 1e-9:
            _fail(
                "p3_casing_pressure_rating",
                "P-3는 저양정 펌프라도 고압 루프 내부 압력을 견뎌야 합니다. 케이싱 내압 등급을 확인하세요.",
                state.max_p_in_bar,
                state.p3_casing_pressure_rating_bar,
                "bar",
            )

        return {
            "profile": prof,
            "element_inch": inch,
            "limits": g,
            "profile_reason": reason,
        }, v_list

    def _build_result(
        self, state: HRROSolveState, g_used: Dict, violations: List
    ) -> StageMetric:
        c_prof = _dict_to_profile(state.calc_cc_ions, state.T_C, state.ph)
        chem_out = {
            "streams": {
                "feed": {
                    "flow_m3h": float(state.Qf_m3h),
                    "tds_mgL": float(state.Cf_mgL),
                    "pressure_bar": 0.0,
                    "ions": state.feed_ions,
                },
                "permeate": {
                    "flow_m3h": float(state.Qp_m3h),
                    "tds_mgL": float(state.avg_cp_mgL),
                    "pressure_bar": 0.0,
                    "ions": state.avg_cp_ions,
                },
                "concentrate": {
                    "flow_m3h": float(state.Qc_m3h),
                    "tds_mgL": float(state.calc_cc_mgL),
                    "pressure_bar": float(state.max_p_in_bar),
                    "ions": state.calc_cc_ions,
                },
            },
            "physics_parameters": {
                "total_area_m2": state.total_area_m2,
                "flux_lmh": state.avg_flux_lmh,
                "A_base": state.A_base,
                "B_base": state.B_base,
                "fouling_factor": state.fouling_factor,
                "B_fouling_factor": state.b_fouling_factor,
            },
            "ccro_cycle": (state.cycle_spec.model_dump() if state.cycle_spec else {}),
            "wave_quality_alignment": state.wave_quality_alignment,
            "model": {
                "target_recovery_achieved": state.target_recovery_achieved,
                "target_flow_achieved": state.target_recovery_achieved,
                "pressure_limited": state.pressure_limited,
                "recovery_error_fraction": state.recovery_error_fraction,
                "flow_error_fraction": state.recovery_error_fraction,
                "max_tmp_bar": state.max_tmp_bar,
                "b_salinity_slope": state.b_sal_slope,
                "loop_volume_m3": state.loop_volume_m3,
                "max_minutes": state.max_minutes,
                "ccro_mode_semantics": "WAVE-style CC/PF diagnostics plus V82 smart partial-drain PF/adaptive recovery control",
                "requested_target_recovery_pct": state.requested_target_recovery_pct,
                "actual_cycle_recovery_pct": state.actual_recovery_pct,
                "recovery_stop_reason": state.recovery_stop_reason,
                "adaptive_recovery_enabled": state.adaptive_recovery_enabled,
                "brine_conductivity_limit_mgL": state.brine_conductivity_limit_mgL,
                "hpp_sizing_mode": state.hpp_sizing_mode,
                "hpp_count": state.hpp_count,
                "p3_generated_head_bar": state.p3_generated_head_bar,
                "p3_casing_pressure_rating_bar": state.p3_casing_pressure_rating_bar,
                "pf_mode": state.pf_mode,
                "pf_feed_ratio_pct": state.pf_feed_ratio_pct,
                "pf_recovery_pct": state.pf_recovery_pct,
                "pf_cp_assist_enabled": state.pf_cp_assist_enabled,
                "smart_partial_drain_enabled": bool(state.cycle_spec and state.cycle_spec.pf_mode in {"smart_partial_drain", "field_optimized_low_fr"}),
                "pressure_profile_semantics": (
                    state.cycle_spec.pressure_profile_semantics if state.cycle_spec else {}
                ),
                "effective_recovery_after_rinse_pct": (
                    state.cycle_spec.effective_recovery_after_rinse_pct
                    if state.cycle_spec
                    else state.actual_recovery_pct
                ),
            },
            "guideline": {**g_used, "profile_reason": g_used.get("profile_reason", "")},
            "violations": violations,
            "scaling": {"final_brine": calc_scaling_indices(c_prof)},
        }

        return StageMetric(
            stage=state.stage_no,
            module_type=ModuleType.HRRO,
            recovery_pct=round(state.actual_recovery_pct, 2),
            net_recovery_pct=round(state.actual_recovery_pct, 2),
            flux_lmh=round(state.avg_flux_lmh, 3),
            sec_kwhm3=round(state.avg_sec_kwhm3, 2),
            ndp_bar=round(state.avg_ndp_bar, 2),
            p_in_bar=round(state.max_p_in_bar, 2),
            p_out_bar=0.0,
            Qf=state.Qf_m3h,
            Qp=state.Qp_m3h,
            Qc=state.Qc_m3h,
            Cf=state.Cf_mgL,
            Cp=round(state.avg_cp_mgL, 2),
            Cc=round(state.calc_cc_mgL, 2),
            time_history=state.history,
            chemistry=chem_out,
            warnings=state.warnings if state.warnings else None,
        )

    def _build_empty_metric(self, state: HRROSolveState) -> StageMetric:
        return StageMetric(
            stage=state.stage_no,
            module_type=ModuleType.HRRO,
            recovery_pct=0.0,
            net_recovery_pct=0.0,
            flux_lmh=0.0,
            sec_kwhm3=0.0,
            ndp_bar=0.0,
            p_in_bar=0.0,
            p_out_bar=0.0,
            Qf=state.Qf_m3h,
            Qp=0.0,
            Qc=state.Qf_m3h,
            Cf=state.Cf_mgL,
            Cp=0.0,
            Cc=state.Cf_mgL,
            time_history=[],
            chemistry={},
        )
