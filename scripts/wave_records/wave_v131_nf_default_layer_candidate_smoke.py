from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.simulation.calibration.wave_runtime_correction import (
    apply_wave_runtime_corrections_to_output,
    load_correction_layer,
)
from app.services.simulation.wave_corrected_engine import (
    maybe_apply_wave_correction,
)

DEFAULT_LAYER_PATH = (
    ROOT
    / ".data"
    / "wave_correction_layer.json"
)

CANDIDATE_PATH = (
    ROOT
    / ".data"
    / "wave_correction_layer_v131_candidate.json"
)

OUTPUT_PATH = (
    ROOT
    / "scripts/wave_records/results/_report_corpus"
    / "v131_nf_default_layer_candidate_smoke.json"
)

METRIC_KEYS = {
    "feed_pressure": "feed_pressure_bar",
    "product_tds": "product_tds_mgL",
    "final_concentrate_tds": (
        "final_concentrate_tds_mgL"
    ),
    "specific_energy": (
        "specific_energy_kwh_m3"
    ),
}


def sha256(path: Path) -> str:
    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


def close(
    actual: Any,
    expected: Any,
    tolerance: float = 1e-8,
) -> bool:
    return math.isclose(
        float(actual),
        float(expected),
        rel_tol=tolerance,
        abs_tol=tolerance,
    )


def correction(
    report: dict[str, Any],
    metric: str,
) -> dict[str, Any]:
    for row in report.get("corrections") or []:
        if row.get("metric") == metric:
            return dict(row)

    raise AssertionError(
        f"Missing report metric: {metric}"
    )


def test_disabled(
    candidate: dict[str, Any],
) -> None:
    raw = {
        "process_type": "nf",
        "system": {
            "feed_pressure_bar": 3.0,
            "product_tds_mgL": 400.0,
            "specific_energy_kwh_m3": 0.13,
        },
    }

    request = {
        "stages": [
            {
                "module_type": "NF",
                "membrane_model": (
                    "FilmTec NF270-400/34"
                ),
            },
        ],
    }

    corrected, report = maybe_apply_wave_correction(
        raw,
        request=request,
        correction_layer=candidate,
        config={"enabled": False},
    )

    if report.get("status") != "disabled":
        raise AssertionError(report)

    if corrected != raw:
        raise AssertionError(
            "Disabled candidate changed output"
        )

    print("Candidate default-disabled PASS")


def test_nf270(
    candidate: dict[str, Any],
) -> None:
    raw = {
        "process_type": "nf",
        "system": {
            "feed_pressure_bar": 3.0,
            "product_tds_mgL": 400.0,
            "specific_energy_kwh_m3": 0.13,
        },
    }

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

    corrected, report = maybe_apply_wave_correction(
        raw,
        request=request,
        correction_layer=candidate,
        config={"enabled": False},
    )

    if report.get("status") != "corrected":
        raise AssertionError(report)

    if report.get("applied_count") != 3:
        raise AssertionError(report)

    if report.get("shadow_count") != 0:
        raise AssertionError(report)

    for metric in (
        "feed_pressure",
        "product_tds",
        "specific_energy",
    ):
        row = correction(report, metric)

        if row.get("status") != "applied":
            raise AssertionError(row)

        if not str(
            row.get("model_id") or ""
        ).startswith("v130_nf270_"):
            raise AssertionError(row)

    if close(
        corrected["system"]["feed_pressure_bar"],
        raw["system"]["feed_pressure_bar"],
    ):
        raise AssertionError(
            "NF270 pressure was not corrected"
        )

    print("Candidate NF270 runtime PASS")


def test_nf90(
    candidate: dict[str, Any],
) -> None:
    raw = {
        "process_type": "nf",
        "system": {
            "feed_pressure_bar": 3.0,
            "product_tds_mgL": 434.5,
            "specific_energy_kwh_m3": 0.13,
        },
    }

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

    corrected, report = maybe_apply_wave_correction(
        raw,
        request=request,
        correction_layer=candidate,
        config={"enabled": False},
    )

    if report.get("status") != "corrected":
        raise AssertionError(report)

    if report.get("applied_count") != 2:
        raise AssertionError(report)

    if report.get("shadow_count") != 1:
        raise AssertionError(report)

    pressure = correction(
        report,
        "feed_pressure",
    )

    product = correction(
        report,
        "product_tds",
    )

    energy = correction(
        report,
        "specific_energy",
    )

    for row in (pressure, product, energy):
        if not str(
            row.get("model_id") or ""
        ).startswith("v130_nf90_"):
            raise AssertionError(row)

    if product.get("status") != "shadow_only":
        raise AssertionError(product)

    if not close(
        corrected["system"]["product_tds_mgL"],
        raw["system"]["product_tds_mgL"],
    ):
        raise AssertionError(
            "NF90 shadow changed product TDS"
        )

    if product.get(
        "shadow_corrected_value"
    ) is None:
        raise AssertionError(product)

    print("Candidate NF90 runtime/shadow PASS")


def test_missing_membrane(
    candidate: dict[str, Any],
) -> None:
    raw = {
        "process_type": "nf",
        "system": {
            "feed_pressure_bar": 3.0,
        },
    }

    corrected, report = (
        apply_wave_runtime_corrections_to_output(
            raw,
            candidate,
            options={
                "enable_wave_correction": True,
            },
            config={"enabled": False},
        )
    )

    if report.get("status") != (
        "missing_membrane_context"
    ):
        raise AssertionError(report)

    if corrected != raw:
        raise AssertionError(
            "Missing membrane changed output"
        )

    print("Candidate missing-membrane guard PASS")


def test_existing_models_preserved(
    default: dict[str, Any],
    candidate: dict[str, Any],
) -> dict[str, Any]:
    default_models = list(
        default.get("models") or []
    )

    candidate_models = list(
        candidate.get("models") or []
    )

    if candidate_models[
        : len(default_models)
    ] != default_models:
        raise AssertionError(
            "Existing model order/content changed"
        )

    non_nf = [
        model
        for model in default_models
        if model.get("process_type") != "nf"
        and model.get("metric") in METRIC_KEYS
    ]

    if not non_nf:
        raise AssertionError(
            "No existing non-NF model available"
        )

    preferred = [
        model
        for model in non_nf
        if model.get("process_type") == "ro"
    ]

    selected = (
        preferred[0]
        if preferred
        else non_nf[0]
    )

    process_type = str(
        selected["process_type"]
    )

    metric = str(selected["metric"])
    output_key = METRIC_KEYS[metric]

    raw_value = (
        1.0
        if metric == "specific_energy"
        else 10.0
    )

    raw = {
        "process_type": process_type,
        "system": {
            output_key: raw_value,
        },
    }

    options = {
        "enable_wave_correction": True,
        "wave_process_type": process_type,
    }

    original_output, original_report = (
        apply_wave_runtime_corrections_to_output(
            raw,
            default,
            options=options,
            config={"enabled": True},
        )
    )

    candidate_output, candidate_report = (
        apply_wave_runtime_corrections_to_output(
            raw,
            candidate,
            options=options,
            config={"enabled": True},
        )
    )

    if candidate_output != original_output:
        raise AssertionError(
            "Existing non-NF output changed after merge"
        )

    comparable_keys = (
        "status",
        "applied_count",
        "skipped_count",
        "corrections",
    )

    for key in comparable_keys:
        if candidate_report.get(
            key
        ) != original_report.get(key):
            raise AssertionError(
                "Existing non-NF report changed: "
                f"key={key}\n"
                f"default={original_report.get(key)}\n"
                f"candidate={candidate_report.get(key)}"
            )

    print(
        "Existing non-NF model preservation PASS"
    )

    return {
        "selected_model_id": (
            selected.get("model_id")
        ),
        "process_type": process_type,
        "metric": metric,
        "report_status": (
            original_report.get("status")
        ),
    }


def main() -> int:
    if not DEFAULT_LAYER_PATH.exists():
        raise FileNotFoundError(
            DEFAULT_LAYER_PATH
        )

    if not CANDIDATE_PATH.exists():
        raise FileNotFoundError(
            CANDIDATE_PATH
        )

    default_hash_before = sha256(
        DEFAULT_LAYER_PATH
    )

    default = load_correction_layer(
        DEFAULT_LAYER_PATH
    )

    candidate = load_correction_layer(
        CANDIDATE_PATH
    )

    test_disabled(candidate)
    test_nf270(candidate)
    test_nf90(candidate)
    test_missing_membrane(candidate)

    legacy_result = (
        test_existing_models_preserved(
            default,
            candidate,
        )
    )

    default_hash_after = sha256(
        DEFAULT_LAYER_PATH
    )

    if default_hash_after != default_hash_before:
        raise AssertionError(
            "Default layer was modified"
        )

    result = {
        "schema_version": (
            "aquanova.nf_default_layer_candidate_smoke.v131"
        ),
        "status": "PASS",
        "default_layer_unchanged": True,
        "global_default_enabled": False,
        "nf270_runtime": "PASS",
        "nf90_runtime_shadow": "PASS",
        "missing_membrane_guard": "PASS",
        "existing_non_nf_preservation": (
            "PASS"
        ),
        "existing_non_nf_probe": (
            legacy_result
        ),
    }

    OUTPUT_PATH.write_text(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print("=" * 80)
    print("V131 NF DEFAULT-LAYER CANDIDATE SMOKE")
    print("=" * 80)
    print("default_layer_unchanged=True")
    print("global_default_enabled=False")
    print("nf270_runtime=PASS")
    print("nf90_runtime_shadow=PASS")
    print("missing_membrane_guard=PASS")
    print("existing_non_nf_preservation=PASS")
    print(
        f"existing_non_nf_probe="
        f"{legacy_result}"
    )
    print(
        "\nV131 NF default-layer "
        "candidate smoke PASS"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
