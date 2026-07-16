from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.schemas.simulation import ScenarioInput
from app.services.simulation.engine import SimulationEngine


def _base_stage(**overrides: Any) -> Dict[str, Any]:
    stage = {
        "module_type": "HRRO",
        "element_inch": 8,
        "elements": 3,
        "vessel_count": 1,
        "elements_per_vessel": 3,
        "membrane_model": "FilmTec SOAR 5000i",
        "membrane_area_m2": 37.16,
        "membrane_A_lmh_bar": 5.50,
        "membrane_B_lmh": 0.060,
        "membrane_salt_rejection_pct": 99.5,
        "flow_factor": 0.70,
        "recovery_target_pct": 90.0,
        "feed_flow_m3h": 2.02,
        "loop_volume_m3": 0.09,
        "cc_recycle_m3h_per_pv": 4.50,
        "recirc_flow_m3h": 4.50,
        "min_concentrate_flow_m3h_per_pv": 4.50,
        "pf_recovery_pct": 10.0,
        "timestep_s": 30,
        "max_minutes": 60,
        "pump_eff": 0.80,
        "dp_per_elem_bar": 0.0333,
        "max_tmp_bar": 12.0,
    }
    stage.update(overrides)
    return stage


def _scenario(name: str, stage: Dict[str, Any]) -> ScenarioInput:
    return ScenarioInput(
        **{
            "project_id": "v82-smart-pf-cases",
            "scenario_name": name,
            "feed": {
                "flow_m3h": 2.02,
                "tds_mgL": 412.4,
                "temperature_C": 25.0,
                "ph": 6.5,
            },
            "stages": [stage],
        }
    )


def run_cases() -> List[Dict[str, Any]]:
    cases = [
        (
            "case_1_wave_true_plug_FR270",
            _base_stage(pf_mode="wave_true_plug_flow", pf_feed_ratio_pct=270.0),
        ),
        (
            "case_2_smart_partial_drain_FR150",
            _base_stage(
                pf_mode="smart_partial_drain",
                pf_feed_ratio_pct=150.0,
                p3_recycle_capacity_m3h_per_pv=3.70,
            ),
        ),
        (
            "case_3_field_optimized_low_FR120",
            _base_stage(
                pf_mode="field_optimized_low_fr",
                pf_feed_ratio_pct=120.0,
                p3_recycle_capacity_m3h_per_pv=4.30,
            ),
        ),
        (
            "case_4_adaptive_recovery_brine_limit",
            _base_stage(
                pf_mode="smart_partial_drain",
                pf_feed_ratio_pct=150.0,
                p3_recycle_capacity_m3h_per_pv=3.70,
                adaptive_recovery_enabled=True,
                brine_conductivity_limit_mgL=3000.0,
                adaptive_min_recovery_pct=50.0,
            ),
        ),
    ]

    rows: List[Dict[str, Any]] = []
    engine = SimulationEngine()
    for name, stage in cases:
        out = engine.run(_scenario(name, stage))
        metric = out.stage_metrics[0]
        cycle = metric.chemistry.get("ccro_cycle", {})
        model = metric.chemistry.get("model", {})
        rows.append(
            {
                "case": name,
                "recovery_pct": metric.recovery_pct,
                "pf_mode": cycle.get("pf_mode"),
                "pf_feed_ratio_pct": cycle.get("pf_feed_ratio_pct"),
                "pf_feed_m3h_per_pv": cycle.get("pf_feed_flow_m3h_per_pv"),
                "drain_setpoint_m3h_per_pv": cycle.get("pf_external_drain_setpoint_m3h_per_pv"),
                "p3_recycle_m3h_per_pv": cycle.get("pf_p3_recycle_flow_m3h_per_pv"),
                "membrane_total_feed_m3h_per_pv": cycle.get("pf_membrane_total_feed_flow_m3h_per_pv"),
                "crossflow_ok": cycle.get("crossflow_ok"),
                "brine_valve_mode": cycle.get("brine_valve_mode"),
                "p2_oversizing_required": cycle.get("p2_oversizing_required"),
                "recovery_stop_reason": model.get("recovery_stop_reason"),
                "warning_keys": [getattr(w, "key", "") for w in (out.warnings or [])],
            }
        )
    return rows


def _markdown(rows: List[Dict[str, Any]]) -> str:
    lines = [
        "# V82 Smart Partial Drain PF Cases",
        "",
        "| Case | Mode | FR % | PF feed | Drain setpoint | P-3 recycle | Membrane feed | Crossflow | Valve | P-2 oversized? | Recovery | Stop reason | Warnings |",
        "|---|---|---:|---:|---:|---:|---:|---|---|---|---:|---|---|",
    ]
    for r in rows:
        lines.append(
            "| {case} | {pf_mode} | {pf_feed_ratio_pct:.1f} | {pf_feed_m3h_per_pv:.3f} | "
            "{drain_setpoint_m3h_per_pv:.3f} | {p3_recycle_m3h_per_pv:.3f} | "
            "{membrane_total_feed_m3h_per_pv:.3f} | {crossflow_ok} | {brine_valve_mode} | "
            "{p2_oversizing_required} | {recovery_pct:.2f} | {recovery_stop_reason} | {warnings} |".format(
                warnings=", ".join(r["warning_keys"]), **r
            )
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", help="Print JSON instead of markdown.")
    parser.add_argument("--out", type=Path, default=None, help="Optional output file.")
    args = parser.parse_args()
    rows = run_cases()
    text = json.dumps(rows, ensure_ascii=False, indent=2) if args.json else _markdown(rows)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
