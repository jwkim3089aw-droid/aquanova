#!/usr/bin/env python3
"""Smoke test for V93 WAVE correction-layer shadow validation."""
from __future__ import annotations

from pathlib import Path
import sys
import tempfile

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.simulation.calibration.wave_correction_layer import build_v92_layer  # noqa: E402
from app.services.simulation.calibration.wave_shadow_validation import (  # noqa: E402
    build_shadow_metric_rows,
    summarize_shadow_rows,
    write_v93_outputs,
)


def main() -> int:
    model = {
        "process_type": "ccro",
        "metric": "feed_pressure",
        "model_type": "scale_only",
        "train_n": 12,
        "holdout_n": 3,
        "train_corrected_mean_abs_error_pct": 1.0,
        "holdout_corrected_mean_abs_error_pct": 1.0,
        "holdout_improvement_pct": 80.0,
        "promotion_status": "promote_candidate",
        "promotion_flags": "",
        "model_payload": {"model_type": "scale_only", "scale_factor": 2.0},
    }
    layer = build_v92_layer([model], enable_runtime_by_default=False)
    rows = [
        {
            "pair_id": "p1",
            "pair_status": "paired",
            "split": "train",
            "process_type": "ccro",
            "wave_pass_feed_pressure_bar": "10",
            "aquanova_feed_pressure_bar": "5",
            "wave_pdf_name": "demo.pdf",
        },
        {
            "pair_id": "p2",
            "pair_status": "paired",
            "split": "holdout",
            "process_type": "ccro",
            "wave_pass_feed_pressure_bar": "8",
            "aquanova_feed_pressure_bar": "4",
            "wave_pdf_name": "demo2.pdf",
        },
    ]
    metric_rows = build_shadow_metric_rows(rows, layer)
    assert len(metric_rows) == 2
    assert all(r["shadow_status"] == "corrected" for r in metric_rows)
    assert all(float(r["shadow_abs_error_pct"] or 0) == 0.0 for r in metric_rows)
    payload = summarize_shadow_rows(metric_rows, thresholds={"min_total_n": 2, "min_holdout_n": 1})
    assert payload["summary"]["shadow_pass_count"] == 1
    with tempfile.TemporaryDirectory() as td:
        outs = write_v93_outputs(rows, layer, Path(td) / "demo.csv", thresholds={"min_total_n": 2, "min_holdout_n": 1})
        for path in outs.values():
            assert Path(path).exists()
    print("V93 shadow validation selftest PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
