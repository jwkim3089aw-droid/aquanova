#!/usr/bin/env python3
"""Small smoke test for V92 correction-layer promotion."""
from __future__ import annotations

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.simulation.calibration.wave_correction_layer import apply_correction, build_v92_layer  # noqa: E402


def main() -> int:
    models = [
        {
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
            "model_payload": {"model_type": "scale_only", "scale_factor": 1.2},
        },
        {
            "process_type": "nf",
            "metric": "product_tds",
            "model_type": "scale_only",
            "train_n": 2,
            "holdout_n": 1,
            "train_corrected_mean_abs_error_pct": 3.0,
            "holdout_corrected_mean_abs_error_pct": 4.0,
            "holdout_improvement_pct": 80.0,
            "promotion_status": "review_required",
            "promotion_flags": "insufficient_anchor_count",
            "model_payload": {"model_type": "scale_only", "scale_factor": 2.0},
        },
    ]
    layer = build_v92_layer(models, enable_runtime_by_default=False)
    assert layer["summary"]["promoted_model_count"] == 1
    assert layer["summary"]["rejected_model_count"] == 1
    shadow = apply_correction(layer, "ccro", "feed_pressure", 10.0)
    assert shadow["status"] == "shadow_only"
    corrected = apply_correction(layer, "ccro", "feed_pressure", 10.0, force=True)
    assert corrected["status"] == "corrected"
    assert round(float(corrected["corrected_value"]), 6) == 12.0
    print("V92 correction layer selftest PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
