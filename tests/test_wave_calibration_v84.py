from __future__ import annotations

from app.services.simulation.calibration.wave_calibration_features import (
    build_feature_rows,
    flatten_record,
    summarize_feature_rows,
)


def test_v84_feature_flattening_and_split_are_stable() -> None:
    record = {
        "case_id": "V84_CCRO_R90",
        "kind": "ccro",
        "pdf_name": "V84_CCRO_R90.pdf",
        "summary": {
            "feed_flow_m3h": 2.02,
            "product_flow_m3h": 1.82,
            "recovery_pct": 90.0,
            "feed_pressure_bar": 8.2,
            "product_tds_mgL": 9.28,
        },
        "ccro": {"pf_feed_ratio_pct": 270.0, "cc_concentrate_flow_m3h_per_pv": 4.54},
    }
    flat = flatten_record(record)
    assert flat["summary__feed_flow_m3h"] == 2.02
    assert flat["ccro__pf_feed_ratio_pct"] == 270.0

    rows_1 = build_feature_rows([record])
    rows_2 = build_feature_rows([record])
    assert rows_1 == rows_2
    row = rows_1[0]
    assert row["trace__case_id"] == "V84_CCRO_R90"
    assert "feature__summary__feed_flow_m3h" in row
    assert "target_candidate__summary__product_tds_mgl" in row
    assert row["split"] in {"train", "holdout"}


def test_v84_feature_summary_counts_targets() -> None:
    rows = build_feature_rows([
        {"id": "a", "process": "ro", "feed_pressure_bar": "8.2 bar", "product_tds_mgL": "9.28 mg/L"},
        {"id": "b", "process": "uf", "tmp_bar": "0.5 bar", "recovery_pct": "95%"},
    ])
    summary = summarize_feature_rows(rows)
    assert summary["row_count"] == 2
    assert summary["feature_column_count"] >= 1
    assert summary["target_candidate_column_count"] >= 2
    assert sum(summary["split_counts"].values()) == 2
