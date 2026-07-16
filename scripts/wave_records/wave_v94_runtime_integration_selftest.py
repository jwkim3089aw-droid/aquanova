#!/usr/bin/env python3
"""Smoke test for V94 opt-in WAVE runtime correction bridge."""
from __future__ import annotations

from pathlib import Path
import sys
import tempfile

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.simulation.calibration.wave_correction_layer import build_v92_layer  # noqa: E402
from app.services.simulation.calibration.wave_runtime_correction import (  # noqa: E402
    apply_wave_runtime_corrections_to_output,
    default_runtime_config,
    install_runtime_layer,
    load_runtime_config,
)


def _layer() -> dict:
    models = [
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
        },
        {
            "process_type": "ccro",
            "metric": "specific_energy",
            "model_type": "scale_only",
            "train_n": 20,
            "holdout_n": 5,
            "train_corrected_mean_abs_error_pct": 2.0,
            "holdout_corrected_mean_abs_error_pct": 3.0,
            "holdout_improvement_pct": 70.0,
            "promotion_status": "promote_candidate",
            "promotion_flags": "",
            "model_payload": {"model_type": "scale_only", "scale_factor": 1.5},
        },
    ]
    return build_v92_layer(models, enable_runtime_by_default=False)


def _output() -> dict:
    return {
        "streams": [
            {"label": "Feed", "flow_m3h": 2.0, "tds_mgL": 400.0, "pressure_bar": 0.0},
            {"label": "Product", "flow_m3h": 1.8, "tds_mgL": 8.0, "pressure_bar": 0.0},
            {"label": "Brine", "flow_m3h": 0.2, "tds_mgL": 4000.0, "pressure_bar": 0.0},
        ],
        "kpi": {"recovery_pct": 90.0, "flux_lmh": 16.3, "sec_kwhm3": 0.3, "prod_tds": 8.0},
        "stage_metrics": [
            {
                "stage": 1,
                "module_type": "HRRO",
                "p_in_bar": 5.0,
                "recovery_pct": 90.0,
                "flux_lmh": 16.3,
                "chemistry": {"ccro_cycle": {"pf_feed_ratio_pct": 270.0}},
            }
        ],
    }


def main() -> int:
    layer = _layer()
    out = _output()
    disabled, disabled_report = apply_wave_runtime_corrections_to_output(out, layer)
    assert disabled is out
    assert disabled_report["status"] == "disabled"

    enabled, report = apply_wave_runtime_corrections_to_output(
        out,
        layer,
        options={"enable_wave_correction": True},
        config=default_runtime_config(enabled=False),
    )
    assert report["status"] == "corrected"
    assert report["applied_count"] == 2
    assert enabled["stage_metrics"][0]["p_in_bar"] == 10.0
    assert enabled["kpi"]["sec_kwhm3"] == 0.45
    assert out["stage_metrics"][0]["p_in_bar"] == 5.0  # input is not mutated

    with tempfile.TemporaryDirectory() as td:
        src = Path(td) / "layer.json"
        src.write_text(__import__("json").dumps(layer), encoding="utf-8")
        paths = install_runtime_layer(src, layer_dest=Path(td) / "runtime_layer.json", config_dest=Path(td) / "runtime_config.json")
        cfg = load_runtime_config(paths["config"])
        assert cfg["enabled"] is False
        assert Path(paths["layer"]).exists()
    print("V94 runtime correction selftest PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
