#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.simulation.calibration.wave_runtime_correction import apply_wave_runtime_corrections_to_output


@dataclass
class PassResult:
    feed_pressure_bar: float = 10.0
    specific_energy_kwh_m3: float = 0.30
    final_concentrate_tds_mgL: float = 4000.0


@dataclass
class SystemResult:
    product_flow_m3h: float = 1.82
    recovery_pct: float = 90.0
    product_tds_mgL: float = 9.3


@dataclass
class ScenarioResult:
    process_type: str = "ccro"
    system: SystemResult = field(default_factory=SystemResult)
    passes: list[PassResult] = field(default_factory=lambda: [PassResult()])


layer = {
    "schema_version": "aquanova.wave_scope_residual_layer.v117_pass_only",
    "runtime_enabled_by_default": False,
    "models": [
        {
            "model_id": "test_feed_pressure_small",
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
            "model_id": "test_product_tds_2pass",
            "process_type": "ccro",
            "metric": "product_tds",
            "regime": "ccro_2pass",
            "nonnegative_output": True,
            "model_payload": {
                "prediction_mode": "bounded_residual_delta",
                "delta_ratio": -0.35,
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

raw = ScenarioResult()
corrected, report = apply_wave_runtime_corrections_to_output(raw, layer, options={"enable_wave_correction": True}, config={"enabled": True})

assert report["schema_version"] == "aquanova.wave_runtime_correction.v118", report
assert report["applied_count"] == 1, report
assert corrected.passes[0].feed_pressure_bar == 9.0, corrected.passes[0].feed_pressure_bar
assert raw.passes[0].feed_pressure_bar == 10.0, "raw result must not be mutated"
assert corrected.system.product_tds_mgL == 9.3, "2-pass model must not apply to small 1-pass benchmark"
assert any(c["metric"] == "product_tds" and c["status"] == "no_model" for c in report["corrections"]), report

print("V118 residual-aware runtime bridge selftest PASS")
