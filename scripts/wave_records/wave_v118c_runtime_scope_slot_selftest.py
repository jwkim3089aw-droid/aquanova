#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.simulation.calibration.wave_runtime_correction import apply_wave_runtime_corrections_to_output

result = {
    "process_type": "ccro",
    "stage_metrics": [
        {
            "p_in_bar": 10.0,
            "time_history": [
                {"pressure_bar": 7.85, "specific_energy_kwh_m3": 0.30, "permeate_tds_mgL": 0.97}
            ],
            "chemistry": {
                "wave_quality_alignment": {
                    "final_concentrate_tds_mgL": 4040.30342
                }
            }
        }
    ],
    "system": {
        "product_flow_m3h": 1.82,
        "recovery_pct": 90.0,
        "product_tds_mgL": 9.3,
    },
}

layer = {
    "schema_version": "aquanova.wave_scope_residual_layer.v117_pass_only",
    "runtime_enabled_by_default": False,
    "models": [
        {
            "model_id": "feed_small",
            "process_type": "ccro",
            "metric": "feed_pressure",
            "regime": "ccro_small_1p82_r90_already_aligned",
            "nonnegative_output": True,
            "model_payload": {
                "prediction_mode": "bounded_residual_delta",
                "delta_ratio": -0.10,
                "residual_guards": {"min_ratio": 0.55, "max_ratio": 1.45, "max_rel_delta": 0.35, "max_abs_delta": 4.0},
            },
        },
        {
            "model_id": "sec_recovery",
            "process_type": "ccro",
            "metric": "specific_energy",
            "regime": "ccro_recovery_sweep",
            "nonnegative_output": True,
            "model_payload": {
                "prediction_mode": "bounded_residual_delta",
                "delta_ratio": 0.20,
                "residual_guards": {"min_ratio": 0.55, "max_ratio": 1.65, "max_rel_delta": 0.45, "max_abs_delta": 20.0},
            },
        },
    ],
}

corrected, report = apply_wave_runtime_corrections_to_output(
    result,
    layer,
    options={"enable_wave_correction": True},
    config={"enabled": False},
)

assert report["regime"] == "ccro_small_1p82_r90_already_aligned", report
assert report["applied_count"] == 1, report
assert corrected["stage_metrics"][0]["p_in_bar"] == 9.0, corrected
assert corrected["stage_metrics"][0]["time_history"][0]["pressure_bar"] == 7.85, corrected
assert corrected["stage_metrics"][0]["time_history"][0]["specific_energy_kwh_m3"] == 0.30, corrected
assert any(c["metric"] == "specific_energy" and c["status"] == "no_model" for c in report["corrections"]), report

print("V118C runtime scope/slot selftest PASS")
