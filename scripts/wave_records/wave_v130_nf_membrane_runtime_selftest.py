from __future__ import annotations

import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.simulation.wave_corrected_engine import (
    extract_wave_correction_options,
)
from app.services.simulation.calibration.wave_runtime_correction import (
    apply_wave_runtime_corrections_to_output,
)


def assert_close(
    actual: float,
    expected: float,
    tolerance: float = 1e-9,
) -> None:
    if not math.isclose(
        actual,
        expected,
        rel_tol=tolerance,
        abs_tol=tolerance,
    ):
        raise AssertionError(
            f"actual={actual}, expected={expected}"
        )


def correction_by_metric(report, metric):
    for row in report.get("corrections") or []:
        if row.get("metric") == metric:
            return row

    raise AssertionError(
        f"metric not found in report: {metric}"
    )


def layer():
    return {
        "schema_version": (
            "aquanova.wave_correction_layer.v130.selftest"
        ),
        "models": [
            {
                "model_id": (
                    "v130_nf270_feed_pressure_scale"
                ),
                "process_type": "nf",
                "metric": "feed_pressure",
                "model_type": "scale_only",
                "regime": "nf_standard",
                "runtime_enabled": True,
                "nonnegative_output": True,
                "applicability": {
                    "membrane_models": [
                        "NF270",
                        "NF270-400",
                        "NF270-400/34",
                        "FilmTec NF270-400/34",
                    ],
                },
                "model_payload": {
                    "model_type": "scale_only",
                    "scale_factor": 1.3334576267425846,
                },
            },
            {
                "model_id": (
                    "v130_nf90_feed_pressure_scale"
                ),
                "process_type": "nf",
                "metric": "feed_pressure",
                "model_type": "scale_only",
                "regime": "nf_standard",
                "runtime_enabled": True,
                "nonnegative_output": True,
                "applicability": {
                    "membrane_models": [
                        "NF90",
                        "NF90-400",
                        "NF90-400/34",
                        "FilmTec NF90-400/34",
                    ],
                },
                "model_payload": {
                    "model_type": "scale_only",
                    "scale_factor": 1.6,
                },
            },
            {
                "model_id": (
                    "v130_nf90_product_tds_shadow"
                ),
                "process_type": "nf",
                "metric": "product_tds",
                "model_type": "affine_raw",
                "regime": "nf_standard",
                "runtime_enabled": False,
                "nonnegative_output": True,
                "applicability": {
                    "membrane_models": [
                        "NF90",
                        "NF90-400",
                        "NF90-400/34",
                        "FilmTec NF90-400/34",
                    ],
                },
                "model_payload": {
                    "model_type": "affine_raw",
                    "description": "intercept + raw",
                    "intercept": True,
                    "feature_names": [
                        "aquanova_raw_value",
                    ],
                    "feature_stats": {
                        "aquanova_raw_value": {
                            "mean": 434.5,
                            "std": 170.77267193552956,
                        },
                    },
                    "coefficients": {
                        "intercept": 19.137999999999998,
                        "aquanova_raw_value": (
                            5.46202244536354
                        ),
                    },
                },
            },
        ],
    }


def run_nf270() -> None:
    request = {
        "enable_wave_correction": True,
        "stages": [
            {
                "module_type": "NF",
                "membrane_model": (
                    "FilmTec NF270-400/34"
                ),
            },
        ],
    }

    options = extract_wave_correction_options(
        request
    )

    if options.get("wave_membrane_model") != (
        "FilmTec NF270-400/34"
    ):
        raise AssertionError(options)

    raw = {
        "process_type": "nf",
        "system": {
            "feed_pressure_bar": 3.0,
            "product_tds_mgL": 400.0,
            "specific_energy_kwh_m3": 0.13,
        },
    }

    corrected, report = (
        apply_wave_runtime_corrections_to_output(
            raw,
            layer(),
            options=options,
            config={"enabled": True},
        )
    )

    expected = 3.0 * 1.3334576267425846

    assert_close(
        corrected["system"]["feed_pressure_bar"],
        expected,
    )

    pressure_row = correction_by_metric(
        report,
        "feed_pressure",
    )

    if pressure_row.get("model_id") != (
        "v130_nf270_feed_pressure_scale"
    ):
        raise AssertionError(pressure_row)

    if report.get("applied_count") != 1:
        raise AssertionError(report)

    print("NF270 selector PASS")
    print(
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
        )
    )


def run_nf90() -> None:
    request = {
        "enable_wave_correction": True,
        "stages": [
            {
                "module_type": "NF",
                "membrane_model": (
                    "FilmTec NF90-400/34"
                ),
            },
        ],
    }

    options = extract_wave_correction_options(
        request
    )

    raw = {
        "process_type": "nf",
        "system": {
            "feed_pressure_bar": 3.0,
            "product_tds_mgL": 434.5,
            "specific_energy_kwh_m3": 0.13,
        },
    }

    corrected, report = (
        apply_wave_runtime_corrections_to_output(
            raw,
            layer(),
            options=options,
            config={"enabled": True},
        )
    )

    assert_close(
        corrected["system"]["feed_pressure_bar"],
        4.8,
    )

    # Product TDS model is shadow-only and must not
    # overwrite the raw result.
    assert_close(
        corrected["system"]["product_tds_mgL"],
        434.5,
    )

    pressure_row = correction_by_metric(
        report,
        "feed_pressure",
    )

    product_row = correction_by_metric(
        report,
        "product_tds",
    )

    if pressure_row.get("model_id") != (
        "v130_nf90_feed_pressure_scale"
    ):
        raise AssertionError(pressure_row)

    if product_row.get("status") != "shadow_only":
        raise AssertionError(product_row)

    assert_close(
        product_row["shadow_corrected_value"],
        19.137999999999998,
    )

    print("NF90 selector and shadow PASS")
    print(
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
        )
    )


def run_missing_membrane_guard() -> None:
    raw = {
        "process_type": "nf",
        "system": {
            "feed_pressure_bar": 3.0,
        },
    }

    corrected, report = (
        apply_wave_runtime_corrections_to_output(
            raw,
            layer(),
            options={
                "enable_wave_correction": True,
            },
            config={"enabled": True},
        )
    )

    assert_close(
        corrected["system"]["feed_pressure_bar"],
        3.0,
    )

    if report.get("status") != (
        "missing_membrane_context"
    ):
        raise AssertionError(report)

    print("Missing membrane safety guard PASS")


def main() -> int:
    run_nf270()
    run_nf90()
    run_missing_membrane_guard()

    print(
        "\nV130 NF membrane-aware runtime selftest PASS"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
