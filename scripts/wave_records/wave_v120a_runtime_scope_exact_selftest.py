#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.simulation.calibration.wave_runtime_correction import apply_wave_runtime_corrections_to_output


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
                "residual_guards": {
                    "min_ratio": 0.55,
                    "max_ratio": 1.45,
                    "max_rel_delta": 0.35,
                    "max_abs_delta": 4.0,
                },
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
                "residual_guards": {
                    "min_ratio": 0.55,
                    "max_ratio": 1.65,
                    "max_rel_delta": 0.45,
                    "max_abs_delta": 20.0,
                },
            },
        },
    ],
}

ui_general = {
    "process_type": "ccro",
    "kpi": {"feed_m3h": 20.0, "permeate_m3h": 18.0, "recovery_pct": 90.0},
    "stage_metrics": [{
        "p_in_bar": 30.41,
        "Qf": 20.0,
        "Qp": 18.0,
        "recovery_pct": 90.0,
        "chemistry": {"wave_quality_alignment": {"product_tds_mgL": 124.2, "final_concentrate_tds_mgL": 18882.0}},
        "time_history": [{"specific_energy_kwh_m3": 0.26}]
    }]
}

corrected, report = apply_wave_runtime_corrections_to_output(
    ui_general,
    layer,
    options={"enable_wave_correction": True},
    config={"enabled": False},
)
assert report["regime"] == "ccro_other", report
assert report["applied_count"] == 0, report
assert corrected["stage_metrics"][0]["p_in_bar"] == 30.41, corrected

small = {
    "process_type": "ccro",
    "kpi": {"feed_m3h": 2.02, "permeate_m3h": 1.82, "recovery_pct": 90.0},
    "stage_metrics": [{
        "p_in_bar": 10.0,
        "Qf": 2.02,
        "Qp": 1.82,
        "recovery_pct": 90.0,
        "chemistry": {"wave_quality_alignment": {"product_tds_mgL": 9.3, "final_concentrate_tds_mgL": 4040.0}},
        "time_history": [{"specific_energy_kwh_m3": 0.30}]
    }]
}

corrected2, report2 = apply_wave_runtime_corrections_to_output(
    small,
    layer,
    options={"enable_wave_correction": True},
    config={"enabled": False},
)
assert report2["regime"] == "ccro_small_1p82_r90_already_aligned", report2
assert report2["applied_count"] == 1, report2
assert corrected2["stage_metrics"][0]["p_in_bar"] == 9.0, corrected2

print("V120A exact runtime scope selftest PASS")
