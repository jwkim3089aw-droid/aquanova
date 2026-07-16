from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Literal

PFMode = Literal["wave_true_plug_flow", "smart_partial_drain", "field_optimized_low_fr"]


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, float(v)))


def _safe(v: Any, default: float = 0.0) -> float:
    try:
        if v is None:
            return float(default)
        return float(v)
    except (TypeError, ValueError):
        return float(default)


def _norm_pf_mode(value: Any) -> PFMode:
    s = str(value or "wave_true_plug_flow").strip().lower().replace("-", "_")
    aliases = {
        "wave": "wave_true_plug_flow",
        "true_plug": "wave_true_plug_flow",
        "plug_flow": "wave_true_plug_flow",
        "wave_true_pf": "wave_true_plug_flow",
        "cp_assisted_pf": "smart_partial_drain",
        "p3_assisted_pf": "smart_partial_drain",
        "partial_drain": "smart_partial_drain",
        "smart_pf": "smart_partial_drain",
        "smart_partial_drain_pf": "smart_partial_drain",
        "low_fr": "field_optimized_low_fr",
        "field_optimized": "field_optimized_low_fr",
    }
    s = aliases.get(s, s)
    if s not in {"wave_true_plug_flow", "smart_partial_drain", "field_optimized_low_fr"}:
        return "wave_true_plug_flow"
    return s  # type: ignore[return-value]


@dataclass(frozen=True)
class CCROCycleSpec:
    """WAVE-style and field-optimized CCRO/PF sequence diagnostics.

    V82 deliberately separates two PF interpretations:

    * ``wave_true_plug_flow``: WAVE-like PF; P-3/CP off, brine valve open,
      PF crossflow is supplied mostly by P-2/feed. Low FR can violate the
      PF outlet concentrate-flow requirement, so FR tends to grow toward
      ~270% in small 8"/3-element designs.
    * ``smart_partial_drain``: field optimized PF; P-3/CP remains on and the
      brine valve is controlled by partial PID. External drain is the strict
      mass-balance setpoint ``PF feed - product`` and the remaining brine is
      recycled by P-3 to keep membrane crossflow high at FR 120-150%.
    """

    average_permeate_flow_m3h: float
    net_feed_flow_m3h: float
    target_recovery_pct: float
    cc_recovery_pct: float
    pf_recovery_pct: float
    pf_feed_ratio_pct: float
    vessel_count: int
    loop_volume_m3: float
    cc_concentrate_flow_m3h_per_pv: float
    cc_net_feed_flow_m3h_per_pv: float
    cc_permeate_flow_m3h_per_pv: float
    pf_feed_flow_m3h_per_pv: float
    pf_concentrate_flow_m3h_per_pv: float
    pf_permeate_flow_m3h_per_pv: float
    pf_cp_assist_enabled: bool
    pf_cp_assist_flow_m3h_per_pv: float
    pf_effective_crossflow_m3h_per_pv: float
    total_cycles: float
    cc_sequence_duration_min: float
    pf_sequence_duration_min: float
    complete_sequence_duration_min: float
    cc_system_volume_m3: float
    rinse_volume_m3: float
    rinse_interval_cycles: int
    rinse_uses_permeate: bool
    effective_recovery_after_rinse_pct: float

    # V82 smart PF / field-optimized diagnostics
    pf_mode: str = "wave_true_plug_flow"
    brine_valve_mode: str = "full_open"
    p3_required: bool = False
    p2_oversizing_required: bool = True
    crossflow_ok: bool = True
    required_pf_feed_ratio_for_crossflow_pct: float = 0.0
    min_concentrate_flow_m3h_per_pv: float = 0.0
    pf_external_drain_setpoint_m3h_per_pv: float = 0.0
    pf_drain_setpoint_m3h_per_pv: float = 0.0
    pf_p3_recycle_flow_m3h_per_pv: float = 0.0
    pf_membrane_total_feed_flow_m3h_per_pv: float = 0.0
    pf_membrane_concentrate_out_m3h_per_pv: float = 0.0
    pf_drain_fraction_of_concentrate: float = 0.0
    p3_recycle_capacity_m3h_per_pv: float = 0.0
    p3_recycle_capacity_ok: bool = True
    drain_low_threshold_m3h_per_pv: float = 0.0
    slow_flush_or_poor_salt_displacement: bool = False
    partial_drain_mass_balance_ok: bool = True
    pressure_profile_semantics: Dict[str, Any] | None = None

    def model_dump(self) -> Dict[str, Any]:
        return asdict(self)


def build_ccro_cycle_spec(
    *,
    net_feed_flow_m3h: float,
    target_recovery_pct: float,
    vessel_count: int,
    loop_volume_m3: float,
    cc_recycle_m3h_per_pv: float | None,
    recirc_flow_m3h_total: float | None,
    pf_feed_ratio_pct: float,
    pf_recovery_pct: float,
    pf_cp_assist_enabled: bool = False,
    pf_cp_assist_flow_m3h_per_pv: float | None = None,
    rinse_volume_m3: float = 0.0,
    rinse_interval_cycles: int = 1,
    rinse_uses_permeate: bool = False,
    pf_mode: str = "wave_true_plug_flow",
    min_concentrate_flow_m3h_per_pv: float | None = None,
    p3_recycle_capacity_m3h_per_pv: float | None = None,
    drain_low_threshold_m3h_per_pv: float | None = None,
) -> CCROCycleSpec:
    n_pv = max(1, int(vessel_count or 1))
    q_feed = max(0.0, _safe(net_feed_flow_m3h, 0.0))
    rec = _clamp(_safe(target_recovery_pct, 90.0), 0.0, 99.5)
    pf_rec = _clamp(_safe(pf_recovery_pct, 10.0), 0.0, 95.0)
    pf_ratio = max(0.0, _safe(pf_feed_ratio_pct, 120.0))
    v_sys = max(0.0, _safe(loop_volume_m3, 0.0))
    mode = _norm_pf_mode(pf_mode)

    q_perm_total = q_feed * rec / 100.0
    q_perm_pv = q_perm_total / n_pv

    cc_conc_pv = _safe(cc_recycle_m3h_per_pv, 0.0)
    if cc_conc_pv <= 1e-12:
        cc_conc_pv = _safe(recirc_flow_m3h_total, 0.0) / n_pv
    cc_conc_pv = max(0.0, cc_conc_pv)

    min_conc_pv = _safe(min_concentrate_flow_m3h_per_pv, cc_conc_pv)
    if min_conc_pv <= 1e-12:
        min_conc_pv = cc_conc_pv
    min_conc_pv = max(0.0, min_conc_pv)

    cc_net_feed_pv = q_perm_pv + cc_conc_pv
    cc_rec = (q_perm_pv / cc_net_feed_pv * 100.0) if cc_net_feed_pv > 1e-12 else 0.0

    pf_feed_pv = q_perm_pv * pf_ratio / 100.0

    required_ratio = 0.0
    if q_perm_pv > 1e-12 and pf_rec < 99.9 and min_conc_pv > 0:
        # WAVE true PF with P-3 OFF must supply minimum brine outlet flow
        # through P-2/feed alone: PF feed * (1 - PF recovery) >= Q_min_conc.
        required_ratio = min_conc_pv / max(q_perm_pv * (1.0 - pf_rec / 100.0), 1e-9) * 100.0

    capacity = max(0.0, _safe(p3_recycle_capacity_m3h_per_pv, 0.0))
    requested_assist = max(0.0, _safe(pf_cp_assist_flow_m3h_per_pv, 0.0))
    drain_low_threshold = _safe(drain_low_threshold_m3h_per_pv, 0.0)
    if drain_low_threshold <= 1e-12:
        drain_low_threshold = max(0.50, q_perm_pv * 0.25)

    p3_required = False
    p2_oversizing_required = True
    brine_valve_mode = "full_open"
    pf_external_drain = 0.0
    pf_p3_recycle = 0.0
    pf_membrane_feed = pf_feed_pv
    pf_membrane_conc_out = 0.0
    pf_perm_pv = 0.0
    pf_conc_pv = 0.0
    crossflow_ok = True
    capacity_ok = True
    slow_flush = False
    mass_balance_ok = True

    if mode == "wave_true_plug_flow":
        pf_perm_pv = pf_feed_pv * pf_rec / 100.0
        pf_conc_pv = max(0.0, pf_feed_pv - pf_perm_pv)
        pf_external_drain = pf_conc_pv
        pf_membrane_conc_out = pf_conc_pv
        assist_flow = 0.0
        if pf_cp_assist_enabled:
            # Backward compatible diagnostic only. It is not the official V82
            # smart-PF logic unless pf_mode is smart_partial_drain.
            assist_flow = requested_assist
            if assist_flow <= 1e-12:
                assist_flow = min(cc_conc_pv, pf_feed_pv) if pf_feed_pv > 0 else cc_conc_pv
            pf_p3_recycle = assist_flow
        effective_pf_crossflow = pf_conc_pv + pf_p3_recycle
        crossflow_ok = (pf_conc_pv + 1e-9 >= min_conc_pv * 0.95) if min_conc_pv > 0 else True
        p2_oversizing_required = pf_ratio + 1e-9 >= min(required_ratio, 999999.0) * 0.95 if required_ratio > 0 else False
        brine_valve_mode = "full_open"
    else:
        # Smart partial drain: P-2/feed is sized from FR while P-3 supplies the
        # missing membrane crossflow. The brine valve drains only the amount
        # required by mass conservation: Q_drain = Q_PF_feed - Q_product.
        p3_required = True
        p2_oversizing_required = False
        brine_valve_mode = "partial_pid"
        pf_perm_pv = q_perm_pv
        pf_external_drain = pf_feed_pv - q_perm_pv
        mass_balance_ok = pf_external_drain > 1e-9
        pf_external_drain = max(0.0, pf_external_drain)
        pf_membrane_conc_out = max(min_conc_pv, 0.0)
        pf_membrane_feed = q_perm_pv + pf_membrane_conc_out
        required_recycle = max(0.0, pf_membrane_feed - pf_feed_pv)

        if requested_assist > 0:
            pf_p3_recycle = requested_assist
        else:
            pf_p3_recycle = required_recycle
        if capacity <= 1e-12:
            capacity = pf_p3_recycle
        capacity_ok = capacity + 1e-9 >= required_recycle
        crossflow_ok = pf_p3_recycle + pf_feed_pv + 1e-9 >= pf_membrane_feed and capacity_ok
        pf_conc_pv = pf_membrane_conc_out
        effective_pf_crossflow = pf_membrane_feed
        pf_cp_assist_enabled = True
        slow_flush = 0.0 < pf_external_drain < drain_low_threshold

    if mode == "field_optimized_low_fr" and pf_ratio > 150.0:
        # Keep the mode semantics honest; it can still run, but the output will
        # tell users this is no longer a low-FR optimization case.
        p2_oversizing_required = False

    pf_dur_drain = pf_external_drain
    # PF duration for smart partial drain is governed by the external brine
    # drain setpoint, not by the membrane concentrate outlet flow. This is the
    # expected trade-off: lower FR/smaller drain can increase PF time.
    pf_dur = (v_sys / max(pf_dur_drain * n_pv, 1e-9)) * 60.0 if v_sys > 0 and pf_dur_drain > 0 else 0.0

    # CC duration follows WAVE's concentration-factor view: the CC sequence
    # makes enough permeate to move the loop from feed salinity to target CF.
    cf_max = 1.0 / max(1e-6, 1.0 - rec / 100.0)
    cc_dur = ((cf_max - 1.0) * v_sys / max(q_perm_total, 1e-9)) * 60.0 if v_sys > 0 else 0.0
    complete = cc_dur + pf_dur

    # WAVE's Total Cycles is close to CC duration divided by the hydraulic
    # residence time of the concentrate recycle through the loop.
    cc_conc_total = cc_conc_pv * n_pv
    total_cycles = (cc_dur / max((v_sys / max(cc_conc_total, 1e-9)) * 60.0, 1e-9)) if v_sys > 0 and cc_conc_total > 0 else 0.0

    rinse_v = max(0.0, _safe(rinse_volume_m3, 0.0))
    rinse_n = max(1, int(_safe(rinse_interval_cycles, 1)))
    rinse_per_cycle = rinse_v / rinse_n
    net_product_after_rinse = max(0.0, q_perm_total - (rinse_per_cycle / max(complete / 60.0, 1e-9) if rinse_uses_permeate and complete > 0 else 0.0))
    eff_rec = (net_product_after_rinse / q_feed * 100.0) if q_feed > 1e-12 else 0.0

    drain_fraction = pf_external_drain / max(pf_membrane_conc_out, 1e-9) if pf_membrane_conc_out > 0 else 0.0
    pressure_semantics = {
        "cc_phase": "P-2 VFD/PID ramps pressure upward to maintain constant permeate flow as osmotic pressure rises.",
        "pf_phase": "P-2 VFD/PID slows down and feed pressure drops after partial drain opens and low-TDS feed displaces brine.",
        "profile_shape": "sawtooth_pressure_ramp_up_during_CC_drop_during_PF",
        "control_basis": "constant_permeate_flow_in_CC_adaptive_cycle_recovery_overall",
    }

    return CCROCycleSpec(
        average_permeate_flow_m3h=q_perm_total,
        net_feed_flow_m3h=q_feed,
        target_recovery_pct=rec,
        cc_recovery_pct=cc_rec,
        pf_recovery_pct=pf_rec,
        pf_feed_ratio_pct=pf_ratio,
        vessel_count=n_pv,
        loop_volume_m3=v_sys,
        cc_concentrate_flow_m3h_per_pv=cc_conc_pv,
        cc_net_feed_flow_m3h_per_pv=cc_net_feed_pv,
        cc_permeate_flow_m3h_per_pv=q_perm_pv,
        pf_feed_flow_m3h_per_pv=pf_feed_pv,
        pf_concentrate_flow_m3h_per_pv=pf_conc_pv,
        pf_permeate_flow_m3h_per_pv=pf_perm_pv,
        pf_cp_assist_enabled=bool(pf_cp_assist_enabled),
        pf_cp_assist_flow_m3h_per_pv=pf_p3_recycle if pf_cp_assist_enabled else 0.0,
        pf_effective_crossflow_m3h_per_pv=effective_pf_crossflow,
        total_cycles=total_cycles,
        cc_sequence_duration_min=cc_dur,
        pf_sequence_duration_min=pf_dur,
        complete_sequence_duration_min=complete,
        cc_system_volume_m3=v_sys,
        rinse_volume_m3=rinse_v,
        rinse_interval_cycles=rinse_n,
        rinse_uses_permeate=bool(rinse_uses_permeate),
        effective_recovery_after_rinse_pct=eff_rec,
        pf_mode=mode,
        brine_valve_mode=brine_valve_mode,
        p3_required=p3_required,
        p2_oversizing_required=p2_oversizing_required,
        crossflow_ok=crossflow_ok,
        required_pf_feed_ratio_for_crossflow_pct=required_ratio,
        min_concentrate_flow_m3h_per_pv=min_conc_pv,
        pf_external_drain_setpoint_m3h_per_pv=pf_external_drain,
        pf_drain_setpoint_m3h_per_pv=pf_external_drain,
        pf_p3_recycle_flow_m3h_per_pv=pf_p3_recycle,
        pf_membrane_total_feed_flow_m3h_per_pv=pf_membrane_feed,
        pf_membrane_concentrate_out_m3h_per_pv=pf_membrane_conc_out,
        pf_drain_fraction_of_concentrate=drain_fraction,
        p3_recycle_capacity_m3h_per_pv=capacity,
        p3_recycle_capacity_ok=capacity_ok,
        drain_low_threshold_m3h_per_pv=drain_low_threshold,
        slow_flush_or_poor_salt_displacement=slow_flush,
        partial_drain_mass_balance_ok=mass_balance_ok,
        pressure_profile_semantics=pressure_semantics,
    )


def ccro_cycle_warnings(spec: CCROCycleSpec) -> List[Dict[str, Any]]:
    warnings: List[Dict[str, Any]] = []
    mode = _norm_pf_mode(spec.pf_mode)

    if mode == "wave_true_plug_flow":
        if spec.pf_feed_ratio_pct > 150.0 + 1e-9:
            warnings.append(
                {
                    "key": "pf_feed_ratio_max",
                    "message": "WAVE true plug-flow PF 기준에서 PF Feed Ratio가 권장 최대값 150%를 초과합니다. 소형 시스템에서는 P-1/P-2 과대 선정 위험이 있습니다.",
                    "value": spec.pf_feed_ratio_pct,
                    "limit": 150.0,
                    "unit": "%",
                }
            )
        if (
            spec.required_pf_feed_ratio_for_crossflow_pct > 0
            and spec.pf_feed_ratio_pct < spec.required_pf_feed_ratio_for_crossflow_pct * 0.95
        ):
            warnings.append(
                {
                    "key": "pf_true_plug_crossflow_shortfall",
                    "message": "WAVE true plug-flow PF에서는 P-3가 꺼져 있어 현재 FR로는 막 말단 농축수/세정 유속을 만족하기 어렵습니다.",
                    "value": spec.pf_feed_ratio_pct,
                    "limit": {"required_pf_feed_ratio_pct": spec.required_pf_feed_ratio_for_crossflow_pct},
                    "unit": "%",
                }
            )
    else:
        if not spec.partial_drain_mass_balance_ok:
            warnings.append(
                {
                    "key": "partial_drain_impossible_mass_balance",
                    "message": "Smart partial drain PF에서 PF feed가 생산수 유량 이하라 외부 배출 setpoint가 0 이하입니다.",
                    "value": spec.pf_external_drain_setpoint_m3h_per_pv,
                    "limit": {"must_be_gt": 0.0},
                    "unit": "m3/h/PV",
                }
            )
        if not spec.p3_recycle_capacity_ok:
            warnings.append(
                {
                    "key": "p3_capacity_error",
                    "message": "Smart partial drain PF에 필요한 P-3 재순환 유량이 설정된 P-3 용량보다 큽니다.",
                    "value": spec.pf_p3_recycle_flow_m3h_per_pv,
                    "limit": {"p3_capacity_m3h_per_pv": spec.p3_recycle_capacity_m3h_per_pv},
                    "unit": "m3/h/PV",
                }
            )
        if spec.slow_flush_or_poor_salt_displacement:
            warnings.append(
                {
                    "key": "slow_flush_or_poor_salt_displacement",
                    "message": "부분 배출 PF의 외부 drain setpoint가 낮습니다. PF 시간이 길어지거나 염 배출 효율이 낮아질 수 있어 실증 검증이 필요합니다.",
                    "value": spec.pf_external_drain_setpoint_m3h_per_pv,
                    "limit": {"recommended_min_m3h_per_pv": spec.drain_low_threshold_m3h_per_pv},
                    "unit": "m3/h/PV",
                }
            )

    if mode == "wave_true_plug_flow" and spec.pf_feed_ratio_pct < 120.0 - 1e-9:
        warnings.append(
            {
                "key": "pf_feed_ratio_low",
                "message": "PF Feed Ratio가 일반 CCRO 기본값 120%보다 낮아 PF 세정/배출 검증이 필요합니다.",
                "value": spec.pf_feed_ratio_pct,
                "limit": {"min_reference": 120.0},
                "unit": "%",
            }
        )

    if mode == "wave_true_plug_flow" and spec.pf_cp_assist_enabled and spec.pf_cp_assist_flow_m3h_per_pv > spec.pf_feed_flow_m3h_per_pv * 1.05:
        warnings.append(
            {
                "key": "pf_cp_assist_suction_margin",
                "message": "PF 중 순환펌프 보조 유량이 PF feed 유량보다 큽니다. P-3 흡입 부족/공회전 인터록 검증이 필요합니다.",
                "value": spec.pf_cp_assist_flow_m3h_per_pv,
                "limit": {"pf_feed_flow_m3h_per_pv": spec.pf_feed_flow_m3h_per_pv},
                "unit": "m3/h/PV",
            }
        )
    return warnings
