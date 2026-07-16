from __future__ import annotations

from app.services.simulation.calibration.wave_correction_layer import build_v92_layer
from app.services.simulation.calibration.wave_runtime_correction import (
    apply_wave_runtime_corrections_to_output,
    default_runtime_config,
)


def _layer(scale_pressure=6.0, scale_product=1.8, scale_brine=6.0):
    models = []
    for metric, scale in [
        ("feed_pressure", scale_pressure),
        ("product_tds", scale_product),
        ("final_concentrate_tds", scale_brine),
    ]:
        models.append({
            "process_type": "ccro",
            "metric": metric,
            "model_type": "scale_only",
            "train_n": 12,
            "holdout_n": 3,
            "train_corrected_mean_abs_error_pct": 1.0,
            "holdout_corrected_mean_abs_error_pct": 2.0,
            "holdout_improvement_pct": 80.0,
            "promotion_status": "promote_candidate",
            "promotion_flags": "",
            "model_payload": {"model_type": "scale_only", "scale_factor": scale},
        })
    return build_v92_layer(models, enable_runtime_by_default=False)


def _output(*, wave_aligned=True):
    chemistry = {"ccro_cycle": {"pf_feed_ratio_pct": 270.0}}
    if wave_aligned:
        chemistry["wave_quality_alignment"] = {
            "product_tds_mgL": 9.3,
            "final_concentrate_tds_mgL": 4040.3,
            "product_tds_source": "wave_quality_alignment",
            "concentrate_tds_source": "system_salt_mass_balance_with_wave_product_tds",
        }
    return {
        "streams": [
            {"label": "Product", "flow_m3h": 1.818, "tds_mgL": 9.3},
            {"label": "Brine", "flow_m3h": 0.202, "tds_mgL": 4040.3},
        ],
        "kpi": {"recovery_pct": 90.0, "flux_lmh": 16.3, "sec_kwhm3": 0.34, "prod_tds": 9.3},
        "stage_metrics": [
            {
                "stage": 1,
                "module_type": "HRRO",
                "p_in_bar": 9.94,
                "recovery_pct": 90.0,
                "average_flux_lmh": 16.3,
                "chemistry": chemistry,
            }
        ],
    }


def test_v97_blocks_v96_style_double_correction_and_extreme_pressure_jump() -> None:
    corrected, report = apply_wave_runtime_corrections_to_output(
        _output(wave_aligned=True),
        _layer(scale_pressure=6.0, scale_product=1.8, scale_brine=6.0),
        options={"enable_wave_correction": True},
        config=default_runtime_config(enabled=False),
    )
    assert report["status"] == "guarded_no_runtime_corrections_applied"
    assert report["applied_count"] == 0
    assert corrected["stage_metrics"][0]["p_in_bar"] == 9.94
    assert corrected["streams"][0]["tds_mgL"] == 9.3
    assert corrected["streams"][1]["tds_mgL"] == 4040.3
    reasons = {r.get("metric"): r.get("guard_reason", "") for r in report["corrections"]}
    assert "ratio_above_guard" in reasons["feed_pressure"]
    assert reasons["product_tds"] == "already_wave_aligned_metric"
    assert reasons["final_concentrate_tds"] == "already_wave_aligned_metric" or "ratio_above_guard" in reasons["final_concentrate_tds"]


def test_v97_allows_moderate_non_aligned_corrections() -> None:
    corrected, report = apply_wave_runtime_corrections_to_output(
        _output(wave_aligned=False),
        _layer(scale_pressure=1.5, scale_product=1.25, scale_brine=2.5),
        options={"enable_wave_correction": True},
        config=default_runtime_config(enabled=False),
    )
    assert report["status"] == "corrected"
    assert report["applied_count"] == 3
    assert corrected["stage_metrics"][0]["p_in_bar"] == round(9.94 * 1.5, 6)
    assert corrected["streams"][0]["tds_mgL"] == round(9.3 * 1.25, 6)
    assert corrected["streams"][1]["tds_mgL"] == round(4040.3 * 2.5, 6)
