from __future__ import annotations

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.simulation.calibration.wave_correction_layer import build_v92_layer
from app.services.simulation.wave_corrected_engine import (
    WaveCorrectedSimulationEngine,
    extract_wave_correction_options,
    maybe_apply_wave_correction,
    run_simulation_with_optional_wave_correction,
)


class FakeRequest:
    def __init__(self, options=None):
        self.options = options or {}


class FakeEngine:
    def run(self, request):
        return {
            "streams": [
                {"label": "Product", "flow_m3h": 1.8, "tds_mgL": 8.0},
                {"label": "Brine", "flow_m3h": 0.2, "tds_mgL": 4000.0},
            ],
            "kpi": {"recovery_pct": 90.0, "flux_lmh": 16.3, "sec_kwhm3": 0.30, "prod_tds": 8.0},
            "stage_metrics": [
                {
                    "stage": 1,
                    "module_type": "HRRO",
                    "p_in_bar": 5.0,
                    "recovery_pct": 90.0,
                    "chemistry": {"ccro_cycle": {"pf_feed_ratio_pct": 270.0}},
                }
            ],
        }


def _layer():
    return build_v92_layer(
        [
            {
                "process_type": "ccro",
                "metric": "feed_pressure",
                "model_type": "scale_only",
                "train_n": 20,
                "holdout_n": 5,
                "train_corrected_mean_abs_error_pct": 2.0,
                "holdout_corrected_mean_abs_error_pct": 3.0,
                "holdout_improvement_pct": 70.0,
                "promotion_status": "promote_candidate",
                "promotion_flags": "",
                "model_payload": {"model_type": "scale_only", "scale_factor": 2.0},
            },
            {
                "process_type": "ccro",
                "metric": "specific_energy",
                "model_type": "scale_only",
                "train_n": 20,
                "holdout_n": 5,
                "train_corrected_mean_abs_error_pct": 2.0,
                "holdout_corrected_mean_abs_error_pct": 3.0,
                "holdout_improvement_pct": 70.0,
                "promotion_status": "promote_candidate",
                "promotion_flags": "",
                "model_payload": {"model_type": "scale_only", "scale_factor": 1.5},
            },
        ],
        enable_runtime_by_default=False,
    )


def test_v95_extract_options_from_request() -> None:
    req = FakeRequest(options={"enable_wave_correction": "yes"})
    assert extract_wave_correction_options(req)["enable_wave_correction"] == "yes"


def test_v95_default_engine_wrapper_is_off() -> None:
    engine = WaveCorrectedSimulationEngine(FakeEngine(), correction_layer=_layer(), config={"enabled": False})
    result = engine.run(FakeRequest())
    assert result["stage_metrics"][0]["p_in_bar"] == 5.0
    assert engine.last_wave_correction_report["status"] == "disabled"


def test_v95_request_opt_in_applies_after_real_engine_run() -> None:
    engine = WaveCorrectedSimulationEngine(FakeEngine(), correction_layer=_layer(), config={"enabled": False})
    result = engine.run(FakeRequest(options={"enable_wave_correction": True}))
    assert result["stage_metrics"][0]["p_in_bar"] == 10.0
    assert result["kpi"]["sec_kwhm3"] == 0.45
    assert engine.last_wave_correction_report["applied_count"] == 2


def test_v95_function_returns_result_and_report() -> None:
    result, report = run_simulation_with_optional_wave_correction(
        FakeRequest(options={"wave_correction_enabled": True}),
        engine=FakeEngine(),
        correction_layer=_layer(),
        config={"enabled": False},
    )
    assert report["status"] == "corrected"
    assert result["stage_metrics"][0]["p_in_bar"] == 10.0


def test_v95_missing_layer_opt_in_does_not_break_when_not_strict() -> None:
    result, report = maybe_apply_wave_correction(
        FakeEngine().run(FakeRequest()),
        request=FakeRequest(options={"enable_wave_correction": True}),
        layer_path=".data/definitely_missing_wave_layer.json",
        config={"enabled": False, "correction_layer_path": ".data/definitely_missing_wave_layer.json"},
    )
    assert result["stage_metrics"][0]["p_in_bar"] == 5.0
    assert report["status"] == "layer_missing_or_invalid"
