#!/usr/bin/env python3
"""Small dependency-free smoke test for V90 error analysis."""
from __future__ import annotations

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.simulation.calibration.wave_error_analysis import build_v90_analysis  # noqa: E402


def main() -> int:
    rows = [
        {
            "pair_id": "p1",
            "split": "train",
            "pair_status": "paired",
            "process_type": "ccro",
            "wave_pdf_name": "case1.pdf",
            "wave_pass_feed_pressure_bar": 8.2,
            "aquanova_feed_pressure_bar": 9.94,
            "error_feed_pressure_abs": 1.74,
            "error_feed_pressure_pct": 21.22,
            "wave_system_product_tds_mgL": 9.28,
            "aquanova_permeate_tds_mgL": 9.30,
            "error_product_tds_abs": 0.02,
            "error_product_tds_pct": 0.22,
        },
        {
            "pair_id": "p2",
            "split": "holdout",
            "pair_status": "paired",
            "process_type": "nf",
            "wave_pdf_name": "case2.pdf",
            "wave_system_product_tds_mgL": 22.97,
            "aquanova_permeate_tds_mgL": 607.63,
            "error_product_tds_abs": 584.66,
            "error_product_tds_pct": 2545.32,
        },
    ]
    analysis = build_v90_analysis(rows)
    summary = analysis["summary"]
    assert summary["row_count"] == 2
    assert summary["metric_error_row_count"] == 3
    assert summary["metric_error_class_counts"]["severe"] == 1
    assert summary["clean_metric_error_row_count"] == 2
    print("V90 error analysis selftest PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
