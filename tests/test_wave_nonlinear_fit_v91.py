from __future__ import annotations

from app.services.simulation.calibration.wave_nonlinear_fit import (
    build_v91_fit,
    engineered_features,
    usable_fit_rows,
)


def test_v91_engineered_features_include_interactions() -> None:
    row = {
        "aquanova_raw_value": "10",
        "target_recovery_pct_hint": "90",
        "wave_pass_average_flux_lmh": "16",
        "wave_ccro_pf_feed_ratio_pct": "270",
        "is_stress_case": "true",
    }
    features = engineered_features(row)
    assert features["recovery_frac"] == 0.9
    assert features["pf_feed_ratio_frac"] == 2.7
    assert features["aquanova_raw_x_recovery_frac"] == 9.0
    assert features["is_stress_case_num"] == 1.0


def test_v91_usable_fit_rows_can_include_severe() -> None:
    rows = [
        {"wave_value": 20, "aquanova_raw_value": 10, "v90_error_class": "severe"},
        {"wave_value": 11, "aquanova_raw_value": 10, "v90_error_class": "clean"},
    ]
    assert len(usable_fit_rows(rows, include_severe=True)) == 2
    assert len(usable_fit_rows(rows, include_severe=False)) == 1


def test_v91_builds_candidate_models() -> None:
    rows = []
    for idx in range(12):
        raw = 5.0 + idx
        wave = 1.5 + 1.2 * raw
        rows.append({
            "pair_id": f"p{idx}",
            "split": "holdout" if idx in {1, 9} else "train",
            "process_type": "ro",
            "metric": "product_tds",
            "wave_value": wave,
            "aquanova_raw_value": raw,
            "v90_error_class": "clean",
        })
    payload = build_v91_fit(rows)
    assert payload["summary"]["fitted_group_count"] == 1
    assert payload["recommended_models"][0]["process_type"] == "ro"
    assert payload["candidate_rows"]
