from __future__ import annotations

from app.services.simulation.calibration.wave_error_analysis import (
    build_v90_analysis,
    classify_metric_error,
    metric_long_rows,
)


def test_v90_product_tds_tiny_absolute_error_is_not_outlier() -> None:
    cls, flags = classify_metric_error("product_tds", abs_error=0.02, pct_error=999.0)
    assert cls == "clean"
    assert flags == []


def test_v90_product_tds_large_error_is_severe() -> None:
    cls, flags = classify_metric_error("product_tds", abs_error=584.66, pct_error=2545.32)
    assert cls == "severe"
    assert "product_tds_severe_pct_error" in flags


def test_v90_builds_metric_long_and_summary() -> None:
    rows = [
        {
            "pair_id": "p1",
            "split": "train",
            "pair_status": "paired",
            "process_type": "ccro",
            "wave_pdf_name": "case.pdf",
            "wave_pass_feed_pressure_bar": 8.2,
            "aquanova_feed_pressure_bar": 9.94,
            "error_feed_pressure_abs": 1.74,
            "error_feed_pressure_pct": 21.22,
            "wave_system_specific_energy_kwh_m3": 0.30,
            "aquanova_sec_kwh_m3": 0.34,
            "error_specific_energy_abs": 0.04,
            "error_specific_energy_pct": 13.33,
        }
    ]
    metric_rows = metric_long_rows(rows)
    assert [r["metric"] for r in metric_rows] == ["feed_pressure", "specific_energy"]
    analysis = build_v90_analysis(rows)
    assert analysis["summary"]["metric_error_row_count"] == 2
    assert analysis["summary"]["clean_metric_error_row_count"] == 2
    assert analysis["annotated_rows"][0]["v90_row_error_class"] == "clean"
