from __future__ import annotations

from app.services.simulation.calibration.wave_correction_layer import (
    apply_correction,
    build_v92_layer,
    promotion_decision,
)


def _good_model(metric: str = "feed_pressure") -> dict:
    return {
        "process_type": "ccro",
        "metric": metric,
        "model_type": "scale_only",
        "train_n": 20,
        "holdout_n": 5,
        "train_corrected_mean_abs_error_pct": 3.0,
        "holdout_corrected_mean_abs_error_pct": 4.0,
        "holdout_improvement_pct": 80.0,
        "promotion_status": "promote_candidate",
        "promotion_flags": "",
        "model_payload": {"model_type": "scale_only", "scale_factor": 1.25},
    }


def test_v92_promotes_only_metrics_that_pass_gate() -> None:
    good = _good_model()
    bad = _good_model("recovery")
    decision_good = promotion_decision(good)
    decision_bad = promotion_decision(bad)
    assert decision_good["decision"] == "promoted"
    assert decision_bad["decision"] == "rejected"
    assert "metric_not_promotable" in decision_bad["rejection_flags"]


def test_v92_builds_shadow_layer_and_can_force_apply() -> None:
    layer = build_v92_layer([_good_model()], enable_runtime_by_default=False)
    assert layer["summary"]["promoted_model_count"] == 1
    shadow = apply_correction(layer, "ccro", "feed_pressure", 8.0)
    assert shadow["status"] == "shadow_only"
    forced = apply_correction(layer, "ccro", "feed_pressure", 8.0, force=True)
    assert forced["status"] == "corrected"
    assert round(float(forced["corrected_value"]), 6) == 10.0


def test_v92_rejects_high_holdout_error_even_if_v91_promoted() -> None:
    model = _good_model("product_tds")
    model["holdout_corrected_mean_abs_error_pct"] = 57.0
    model["holdout_improvement_pct"] = 8.0
    decision = promotion_decision(model)
    assert decision["decision"] == "rejected"
    assert "holdout_error_above_gate" in decision["rejection_flags"]
    assert "holdout_improvement_below_gate" in decision["rejection_flags"]
