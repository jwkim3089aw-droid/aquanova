from __future__ import annotations

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.simulation.calibration.wave_correction_layer import build_v92_layer
from app.services.simulation.calibration.wave_runtime_correction import (
    apply_wave_runtime_corrections_to_output,
    default_runtime_config,
)


def _promoted_scale_model(metric: str, factor: float) -> dict:
    return {
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
        "model_payload": {"model_type": "scale_only", "scale_factor": factor},
    }


def main() -> int:
    layer = build_v92_layer([
        _promoted_scale_model("feed_pressure", 6.0),
        _promoted_scale_model("product_tds", 1.8),
        _promoted_scale_model("final_concentrate_tds", 6.0),
    ], enable_runtime_by_default=False)
    output = {
        "streams": [
            {"label": "Product", "tds_mgL": 9.3},
            {"label": "Brine", "tds_mgL": 4040.3},
        ],
        "kpi": {"recovery_pct": 90.0, "flux_lmh": 16.3, "sec_kwhm3": 0.34, "prod_tds": 9.3},
        "stage_metrics": [{
            "module_type": "HRRO",
            "p_in_bar": 9.94,
            "recovery_pct": 90.0,
            "average_flux_lmh": 16.3,
            "chemistry": {
                "ccro_cycle": {"pf_feed_ratio_pct": 270.0},
                "wave_quality_alignment": {
                    "product_tds_mgL": 9.3,
                    "final_concentrate_tds_mgL": 4040.3,
                    "product_tds_source": "wave_quality_alignment",
                    "concentrate_tds_source": "system_salt_mass_balance_with_wave_product_tds",
                },
            },
        }],
    }
    corrected, report = apply_wave_runtime_corrections_to_output(
        output,
        layer,
        options={"enable_wave_correction": True},
        config=default_runtime_config(enabled=False),
    )
    assert report["applied_count"] == 0, report
    assert report["status"] == "guarded_no_runtime_corrections_applied", report
    assert corrected["stage_metrics"][0]["p_in_bar"] == 9.94, corrected
    print("V97 runtime guard selftest PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
