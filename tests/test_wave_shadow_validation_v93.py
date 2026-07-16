from __future__ import annotations

from app.services.simulation.calibration.wave_correction_layer import build_v92_layer
from app.services.simulation.calibration.wave_shadow_validation import (
    build_shadow_metric_rows,
    summarize_shadow_rows,
)


def _layer(scale: float = 2.0) -> dict:
    model = {
        "process_type": "ccro",
        "metric": "feed_pressure",
        "model_type": "scale_only",
        "train_n": 20,
        "holdout_n": 5,
        "train_corrected_mean_abs_error_pct": 3.0,
        "holdout_corrected_mean_abs_error_pct": 4.0,
        "holdout_improvement_pct": 80.0,
        "promotion_status": "promote_candidate",
        "promotion_flags": "",
        "model_payload": {"model_type": "scale_only", "scale_factor": scale},
    }
    return build_v92_layer([model], enable_runtime_by_default=False)


def test_v93_shadow_rows_apply_v92_models_without_runtime_enable() -> None:
    rows = [
        {
            "pair_id": "p1",
            "pair_status": "paired",
            "split": "train",
            "process_type": "ccro",
            "wave_pass_feed_pressure_bar": "10",
            "aquanova_feed_pressure_bar": "5",
        }
    ]
    metric_rows = build_shadow_metric_rows(rows, _layer())
    assert len(metric_rows) == 1
    assert metric_rows[0]["runtime_enabled_in_layer"] is False
    assert metric_rows[0]["shadow_status"] == "corrected"
    assert float(metric_rows[0]["shadow_corrected_value"]) == 10.0
    assert float(metric_rows[0]["shadow_abs_error_pct"]) == 0.0


def test_v93_summary_passes_good_holdout_shadow_result() -> None:
    rows = [
        {"pair_id": "t1", "pair_status": "paired", "split": "train", "process_type": "ccro", "wave_pass_feed_pressure_bar": "10", "aquanova_feed_pressure_bar": "5"},
        {"pair_id": "t2", "pair_status": "paired", "split": "train", "process_type": "ccro", "wave_pass_feed_pressure_bar": "12", "aquanova_feed_pressure_bar": "6"},
        {"pair_id": "h1", "pair_status": "paired", "split": "holdout", "process_type": "ccro", "wave_pass_feed_pressure_bar": "8", "aquanova_feed_pressure_bar": "4"},
    ]
    metric_rows = build_shadow_metric_rows(rows, _layer())
    payload = summarize_shadow_rows(metric_rows, thresholds={"min_total_n": 3, "min_holdout_n": 1})
    assert payload["summary"]["shadow_pass_count"] == 1
    assert payload["summary_rows"][0]["decision"] == "shadow_pass"


def test_v93_summary_flags_negative_regression() -> None:
    rows = [
        {"pair_id": "t1", "pair_status": "paired", "split": "train", "process_type": "ccro", "wave_pass_feed_pressure_bar": "10", "aquanova_feed_pressure_bar": "9"},
        {"pair_id": "h1", "pair_status": "paired", "split": "holdout", "process_type": "ccro", "wave_pass_feed_pressure_bar": "10", "aquanova_feed_pressure_bar": "9"},
    ]
    metric_rows = build_shadow_metric_rows(rows, _layer(scale=2.0))
    payload = summarize_shadow_rows(metric_rows, thresholds={"min_total_n": 2, "min_holdout_n": 1})
    assert payload["summary"]["shadow_fail_count"] == 1
    assert "negative_regression" in payload["summary_rows"][0]["flags"]
