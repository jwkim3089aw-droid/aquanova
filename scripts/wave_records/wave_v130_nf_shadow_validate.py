from __future__ import annotations

import csv
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.simulation.calibration.wave_correction_layer import (
    apply_correction,
)
from app.services.simulation.calibration.wave_runtime_correction import (
    _v130_model_for,
)

DATA_DIR = ROOT / "scripts/wave_records/results/_report_corpus"

LAYER_PATH = (
    DATA_DIR
    / "v130_nf_membrane_correction_layer.json"
)

ERROR_PATHS = [
    (
        DATA_DIR
        / "v129_nf270_v90_metric_errors.csv"
    ),
    (
        DATA_DIR
        / "v129_nf90_v90_metric_errors.csv"
    ),
]

OUTPUT_CSV = (
    DATA_DIR
    / "v130_nf_shadow_rows.csv"
)

OUTPUT_JSON = (
    DATA_DIR
    / "v130_nf_shadow_summary.json"
)

OUTPUT_MD = (
    DATA_DIR
    / "v130_nf_shadow_report.md"
)

EXPECTED_MODEL_ROWS = {
    "v130_nf270_feed_pressure_scale_only": 8,
    "v130_nf270_product_tds_affine_raw": 8,
    "v130_nf270_specific_energy_scale_only": 8,
    "v130_nf90_feed_pressure_scale_only": 7,
    "v130_nf90_specific_energy_scale_only": 7,
    "v130_nf90_product_tds_affine_raw": 7,
}

HOLDOUT_LIMITS = {
    "v130_nf270_feed_pressure_scale_only": 2.0,
    "v130_nf270_product_tds_affine_raw": 10.0,
    "v130_nf270_specific_energy_scale_only": 5.0,
    "v130_nf90_feed_pressure_scale_only": 5.0,
    "v130_nf90_specific_energy_scale_only": 5.0,
    "v130_nf90_product_tds_affine_raw": 20.0,
}


def number(value: Any) -> float:
    return float(value)


def abs_error_pct(
    predicted: float,
    expected: float,
) -> float:
    if expected == 0:
        return abs(predicted - expected) * 100.0

    return (
        abs(predicted - expected)
        / abs(expected)
        * 100.0
    )


def membrane_of(row: dict[str, str]) -> str:
    text = " ".join(
        str(value)
        for value in row.values()
        if value not in (None, "")
    ).upper()

    if "NF270" in text:
        return "NF270"

    if "NF90" in text:
        return "NF90"

    return ""


def mean(values: list[float]) -> float:
    return statistics.mean(values) if values else 0.0


def summarize_group(
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    raw_errors = [
        float(row["raw_error_pct"])
        for row in rows
    ]

    corrected_errors = [
        float(row["corrected_error_pct"])
        for row in rows
    ]

    raw_mae = mean(raw_errors)
    corrected_mae = mean(corrected_errors)

    improvement = (
        (raw_mae - corrected_mae)
        / raw_mae
        * 100.0
        if raw_mae > 0
        else 0.0
    )

    return {
        "row_count": len(rows),
        "raw_mean_abs_error_pct": raw_mae,
        "corrected_mean_abs_error_pct": (
            corrected_mae
        ),
        "improvement_pct": improvement,
        "max_corrected_abs_error_pct": (
            max(corrected_errors)
            if corrected_errors
            else 0.0
        ),
    }


def write_csv(
    rows: list[dict[str, Any]],
) -> None:
    fieldnames = [
        "pair_id",
        "split",
        "wave_pdf_name",
        "membrane",
        "metric",
        "model_id",
        "validation_mode",
        "runtime_enabled",
        "wave_value",
        "aquanova_raw_value",
        "corrected_value",
        "raw_error_pct",
        "corrected_error_pct",
        "row_improvement_pct",
    ]

    with OUTPUT_CSV.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fieldnames,
        )
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    if not LAYER_PATH.exists():
        print(f"FAIL: missing layer: {LAYER_PATH}")
        return 1

    for error_path in ERROR_PATHS:
        if not error_path.exists():
            print(
                f"FAIL: missing metric errors: "
                f"{error_path}"
            )
            return 1

    layer = json.loads(
        LAYER_PATH.read_text(encoding="utf-8")
    )

    source_rows = []

    for error_path in ERROR_PATHS:
        with error_path.open(
            "r",
            encoding="utf-8-sig",
            newline="",
        ) as handle:
            source_rows.extend(
                csv.DictReader(handle)
            )

    if len(source_rows) != 75:
        raise RuntimeError(
            "Expected 75 membrane-scoped metric rows, "
            f"actual={len(source_rows)}"
        )

    output_rows: list[dict[str, Any]] = []

    target_metrics = {
        "feed_pressure",
        "product_tds",
        "specific_energy",
    }

    for source in source_rows:
        metric = source.get("metric", "")

        if metric not in target_metrics:
            continue

        membrane = membrane_of(source)

        if membrane not in {"NF270", "NF90"}:
            continue

        membrane_hint = (
            source.get("membrane_model_hint")
            or membrane
        )

        model = _v130_model_for(
            layer,
            "nf",
            metric,
            "nf_standard",
            membrane_hint,
        )

        if model is None:
            raise RuntimeError(
                "No membrane-scoped model: "
                f"membrane={membrane}, "
                f"metric={metric}, "
                f"pdf={source.get('wave_pdf_name')}"
            )

        wave_value = number(
            source["wave_value"]
        )

        raw_value = number(
            source["aquanova_raw_value"]
        )

        prediction = apply_correction(
            {"models": [model]},
            "nf",
            metric,
            raw_value,
            {
                "membrane_model": membrane_hint,
                "regime": "nf_standard",
            },
            force=True,
        )

        if prediction.get("status") != "corrected":
            raise RuntimeError(
                f"Prediction failed: {prediction}"
            )

        corrected_value = number(
            prediction["corrected_value"]
        )

        if corrected_value < 0:
            raise RuntimeError(
                "Negative prediction: "
                f"{model['model_id']}"
            )

        raw_error = abs_error_pct(
            raw_value,
            wave_value,
        )

        corrected_error = abs_error_pct(
            corrected_value,
            wave_value,
        )

        row_improvement = (
            (raw_error - corrected_error)
            / raw_error
            * 100.0
            if raw_error > 0
            else 0.0
        )

        output_rows.append(
            {
                "pair_id": source.get(
                    "pair_id", ""
                ),
                "split": source.get(
                    "split", ""
                ),
                "wave_pdf_name": source.get(
                    "wave_pdf_name", ""
                ),
                "membrane": membrane,
                "metric": metric,
                "model_id": model["model_id"],
                "validation_mode": model.get(
                    "validation_mode", ""
                ),
                "runtime_enabled": bool(
                    model.get("runtime_enabled")
                ),
                "wave_value": wave_value,
                "aquanova_raw_value": raw_value,
                "corrected_value": corrected_value,
                "raw_error_pct": raw_error,
                "corrected_error_pct": (
                    corrected_error
                ),
                "row_improvement_pct": (
                    row_improvement
                ),
            }
        )

    if len(output_rows) != 45:
        raise RuntimeError(
            "Expected 45 validation rows, "
            f"actual={len(output_rows)}"
        )

    runtime_rows = [
        row
        for row in output_rows
        if row["runtime_enabled"]
    ]

    shadow_rows = [
        row
        for row in output_rows
        if not row["runtime_enabled"]
    ]

    if len(runtime_rows) != 38:
        raise RuntimeError(
            "Expected 38 runtime-candidate rows, "
            f"actual={len(runtime_rows)}"
        )

    if len(shadow_rows) != 7:
        raise RuntimeError(
            "Expected 7 shadow rows, "
            f"actual={len(shadow_rows)}"
        )

    by_model: dict[
        str,
        list[dict[str, Any]],
    ] = defaultdict(list)

    for row in output_rows:
        by_model[row["model_id"]].append(row)

    if set(by_model) != set(EXPECTED_MODEL_ROWS):
        raise RuntimeError(
            "Model-set mismatch: "
            f"actual={sorted(by_model)}"
        )

    model_summaries = {}

    for model_id, expected_count in (
        EXPECTED_MODEL_ROWS.items()
    ):
        rows = by_model[model_id]

        if len(rows) != expected_count:
            raise RuntimeError(
                f"{model_id}: "
                f"expected rows={expected_count}, "
                f"actual={len(rows)}"
            )

        train_rows = [
            row
            for row in rows
            if row["split"] == "train"
        ]

        holdout_rows = [
            row
            for row in rows
            if row["split"] == "holdout"
        ]

        expected_holdout = (
            3
            if "_nf270_" in model_id
            else 2
        )

        if len(holdout_rows) != expected_holdout:
            raise RuntimeError(
                f"{model_id}: "
                f"expected holdout="
                f"{expected_holdout}, "
                f"actual={len(holdout_rows)}"
            )

        all_summary = summarize_group(rows)
        train_summary = summarize_group(
            train_rows
        )
        holdout_summary = summarize_group(
            holdout_rows
        )

        holdout_limit = HOLDOUT_LIMITS[
            model_id
        ]

        if (
            holdout_summary[
                "corrected_mean_abs_error_pct"
            ]
            > holdout_limit
        ):
            raise RuntimeError(
                f"{model_id}: holdout error "
                f"{holdout_summary['corrected_mean_abs_error_pct']:.6f}% "
                f"> limit {holdout_limit:.6f}%"
            )

        if (
            holdout_summary["improvement_pct"]
            <= 0
        ):
            raise RuntimeError(
                f"{model_id}: no holdout improvement"
            )

        model_summaries[model_id] = {
            "validation_mode": rows[0][
                "validation_mode"
            ],
            "runtime_enabled": rows[0][
                "runtime_enabled"
            ],
            "all": all_summary,
            "train": train_summary,
            "holdout": holdout_summary,
            "holdout_limit_pct": (
                holdout_limit
            ),
            "status": "PASS",
        }

    aggregate = summarize_group(
        output_rows
    )

    runtime_aggregate = summarize_group(
        runtime_rows
    )

    shadow_aggregate = summarize_group(
        shadow_rows
    )

    summary = {
        "schema_version": (
            "aquanova.nf_shadow_validation.v130"
        ),
        "source_layer": str(LAYER_PATH),
        "source_metric_errors": [
            str(path)
            for path in ERROR_PATHS
        ],
        "row_count": len(output_rows),
        "runtime_candidate_row_count": len(
            runtime_rows
        ),
        "shadow_only_row_count": len(
            shadow_rows
        ),
        "aggregate": aggregate,
        "runtime_candidate_aggregate": (
            runtime_aggregate
        ),
        "shadow_only_aggregate": (
            shadow_aggregate
        ),
        "models": model_summaries,
        "status": "PASS",
    }

    write_csv(output_rows)

    OUTPUT_JSON.write_text(
        json.dumps(
            summary,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    markdown = [
        "# V130 NF Membrane Shadow Validation",
        "",
        f"- Rows: {len(output_rows)}",
        (
            "- Runtime candidate rows: "
            f"{len(runtime_rows)}"
        ),
        (
            "- Shadow-only rows: "
            f"{len(shadow_rows)}"
        ),
        (
            "- Aggregate raw MAE: "
            f"{aggregate['raw_mean_abs_error_pct']:.6f}%"
        ),
        (
            "- Aggregate corrected MAE: "
            f"{aggregate['corrected_mean_abs_error_pct']:.6f}%"
        ),
        (
            "- Aggregate improvement: "
            f"{aggregate['improvement_pct']:.6f}%"
        ),
        "",
        "## Models",
        "",
        (
            "| Model | Mode | Holdout raw MAE | "
            "Holdout corrected MAE | Improvement |"
        ),
        "|---|---:|---:|---:|---:|",
    ]

    for model_id, model_summary in (
        model_summaries.items()
    ):
        holdout = model_summary["holdout"]

        markdown.append(
            f"| {model_id} | "
            f"{model_summary['validation_mode']} | "
            f"{holdout['raw_mean_abs_error_pct']:.6f}% | "
            f"{holdout['corrected_mean_abs_error_pct']:.6f}% | "
            f"{holdout['improvement_pct']:.6f}% |"
        )

    markdown.extend(
        [
            "",
            "## Result",
            "",
            "**PASS**",
            "",
        ]
    )

    OUTPUT_MD.write_text(
        "\n".join(markdown),
        encoding="utf-8",
    )

    print("=" * 80)
    print("V130 NF FULL SHADOW VALIDATION")
    print("=" * 80)
    print(f"row_count={len(output_rows)}")
    print(
        f"runtime_candidate_rows="
        f"{len(runtime_rows)}"
    )
    print(
        f"shadow_only_rows="
        f"{len(shadow_rows)}"
    )
    print(
        f"raw_mae="
        f"{aggregate['raw_mean_abs_error_pct']:.6f}%"
    )
    print(
        f"corrected_mae="
        f"{aggregate['corrected_mean_abs_error_pct']:.6f}%"
    )
    print(
        f"improvement="
        f"{aggregate['improvement_pct']:.6f}%"
    )

    print("\nMODEL HOLDOUT RESULTS")

    for model_id, model_summary in (
        model_summaries.items()
    ):
        holdout = model_summary["holdout"]

        print(
            f"{model_id}: "
            f"raw={holdout['raw_mean_abs_error_pct']:.6f}% "
            f"corrected="
            f"{holdout['corrected_mean_abs_error_pct']:.6f}% "
            f"improvement="
            f"{holdout['improvement_pct']:.6f}% "
            f"status=PASS"
        )

    print(f"\ncsv={OUTPUT_CSV}")
    print(f"json={OUTPUT_JSON}")
    print(f"markdown={OUTPUT_MD}")
    print(
        "\nV130 NF full shadow validation PASS"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
