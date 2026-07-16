from __future__ import annotations

from app.services.simulation.calibration.wave_correction_layer import build_v92_layer
from app.services.simulation.calibration.wave_runtime_correction import (
    apply_wave_runtime_corrections_to_output,
    default_runtime_config,
    runtime_enabled,
)


def _layer() -> dict:
    return build_v92_layer(
        [
            {
                "process_type": "ccro",
                "metric": "feed_pressure",
                "model_type": "scale_only",
                "train_n": 12,
                "holdout_n": 3,
                "train_corrected_mean_abs_error_pct": 1.0,
                "holdout_corrected_mean_abs_error_pct": 2.0,
                "holdout_improvement_pct": 80.0,
                "promotion_status": "promote_candidate",
                "promotion_flags": "",
                "model_payload": {"model_type": "scale_only", "scale_factor": 2.0},
            },
            {
                "process_type": "ccro",
                "metric": "product_tds",
                "model_type": "scale_only",
                "train_n": 12,
                "holdout_n": 3,
                "train_corrected_mean_abs_error_pct": 1.0,
                "holdout_corrected_mean_abs_error_pct": 2.0,
                "holdout_improvement_pct": 80.0,
                "promotion_status": "promote_candidate",
                "promotion_flags": "",
                "model_payload": {"model_type": "scale_only", "scale_factor": 1.25},
            },
        ],
        enable_runtime_by_default=False,
    )


def _output() -> dict:
    return {
        "streams": [
            {"label": "Product", "flow_m3h": 1.8, "tds_mgL": 8.0, "pressure_bar": 0.0},
            {"label": "Brine", "flow_m3h": 0.2, "tds_mgL": 4000.0, "pressure_bar": 0.0},
        ],
        "kpi": {"recovery_pct": 90.0, "flux_lmh": 16.3, "sec_kwhm3": 0.3, "prod_tds": 8.0},
        "stage_metrics": [
            {"stage": 1, "module_type": "HRRO", "p_in_bar": 5.0, "chemistry": {"ccro_cycle": {"pf_feed_ratio_pct": 270.0}}}
        ],
    }


def test_v94_runtime_defaults_off_and_does_not_mutate() -> None:
    out = _output()
    corrected, report = apply_wave_runtime_corrections_to_output(out, _layer())
    assert corrected is out
    assert report["status"] == "disabled"
    assert out["stage_metrics"][0]["p_in_bar"] == 5.0


def test_v94_runtime_opt_in_applies_promoted_shadow_models() -> None:
    corrected, report = apply_wave_runtime_corrections_to_output(
        _output(),
        _layer(),
        options={"enable_wave_correction": True},
        config=default_runtime_config(enabled=False),
    )
    assert report["status"] == "corrected"
    assert report["applied_count"] == 2
    assert corrected["stage_metrics"][0]["p_in_bar"] == 10.0
    assert corrected["streams"][0]["tds_mgL"] == 10.0
    assert corrected["kpi"]["prod_tds"] == 10.0


def test_v94_runtime_enable_flags() -> None:
    assert runtime_enabled({"wave_correction_enabled": "yes"}, default_runtime_config(enabled=False)) is True
    assert runtime_enabled({}, default_runtime_config(enabled=True)) is True
    assert runtime_enabled({"enable_wave_correction": False}, default_runtime_config(enabled=True)) is False
