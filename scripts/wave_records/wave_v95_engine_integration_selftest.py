#!/usr/bin/env python3
"""Smoke test for V95 opt-in SimulationEngine correction wrapper."""
from __future__ import annotations

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.simulation.calibration.wave_correction_layer import build_v92_layer  # noqa: E402
from app.services.simulation.wave_corrected_engine import WaveCorrectedSimulationEngine  # noqa: E402


class _Request:
    def __init__(self, options=None):
        self.options = options or {}


class _Engine:
    def run(self, request):
        return {
            "streams": [
                {"label": "Product", "flow_m3h": 1.8, "tds_mgL": 8.0},
                {"label": "Brine", "flow_m3h": 0.2, "tds_mgL": 4000.0},
            ],
            "kpi": {"recovery_pct": 90.0, "flux_lmh": 16.3, "sec_kwhm3": 0.30, "prod_tds": 8.0},
            "stage_metrics": [
                {"stage": 1, "module_type": "HRRO", "p_in_bar": 5.0, "chemistry": {"ccro_cycle": {"pf_feed_ratio_pct": 270.0}}}
            ],
        }


def _layer() -> dict:
    return build_v92_layer(
        [
            {
                "process_type": "ccro",
                "metric": "feed_pressure",
                "model_type": "scale_only",
                "train_n": 20,
                "holdout_n": 5,
                "train_corrected_mean_abs_error_pct": 2.0,
                "holdout_corrected_mean_abs_error_pct": 3.0,
                "holdout_improvement_pct": 70.0,
                "promotion_status": "promote_candidate",
                "promotion_flags": "",
                "model_payload": {"model_type": "scale_only", "scale_factor": 2.0},
            }
        ],
        enable_runtime_by_default=False,
    )


def main() -> int:
    engine = WaveCorrectedSimulationEngine(_Engine(), correction_layer=_layer(), config={"enabled": False})
    off = engine.run(_Request())
    assert off["stage_metrics"][0]["p_in_bar"] == 5.0
    assert engine.last_wave_correction_report["status"] == "disabled"

    on = engine.run(_Request(options={"enable_wave_correction": True}))
    assert on["stage_metrics"][0]["p_in_bar"] == 10.0
    assert engine.last_wave_correction_report["applied_count"] == 1
    print("V95 engine integration selftest PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
