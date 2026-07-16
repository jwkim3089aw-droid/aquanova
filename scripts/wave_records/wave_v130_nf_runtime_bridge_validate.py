from __future__ import annotations

import csv
import json
import math
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.simulation.calibration.wave_runtime_correction import (
    apply_wave_runtime_corrections_to_output,
)

DATA_DIR = ROOT / "scripts/wave_records/results/_report_corpus"

LAYER_PATH = (
    DATA_DIR
    / "v130_nf_membrane_correction_layer.json"
)

SHADOW_ROWS_PATH = (
    DATA_DIR
    / "v130_nf_shadow_rows.csv"
)

OUTPUT_CSV = (
    DATA_DIR
    / "v130_nf_runtime_bridge_rows.csv"
)

OUTPUT_JSON = (
    DATA_DIR
    / "v130_nf_runtime_bridge_summary.json"
)

OUTPUT_MD = (
    DATA_DIR
    / "v130_nf_runtime_bridge_report.md"
)

METRIC_OUTPUT_KEYS = {
    "feed_pressure": "feed_pressure_bar",
    "product_tds": "product_tds_mgL",
    "specific_energy": "specific_energy_kwh_m3",
}

MEMBRANE_NAMES = {
    "NF270": "FilmTec NF270-400/34",
    "NF90": "FilmTec NF90-400/34",
}

EXPECTED_CASE_COUNTS = {
    "NF270": 8,
    "NF90": 7,
}

EXPECTED_RUNTIME_ROWS = 38
EXPECTED_SHADOW_ROWS = 7
EXPECTED_TOTAL_ROWS = 45


def boolish(value: Any) -> bool:
    return str(value or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "y",
        "on",
        "enabled",
    }


def number(value: Any) -> float:
    return float(value)


def close(
    actual: float,
    expected: float,
    *,
    tolerance: float = 1e-8,
) -> bool:
    return math.isclose(
        actual,
        expected,
        rel_tol=tolerance,
        abs_tol=tolerance,
    )


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


def mean(values: list[float]) -> float:
    return statistics.mean(values) if values else 0.0


def find_report_row(
    report: dict[str, Any],
    metric: str,
) -> dict[str, Any] | None:
    for row in report.get("corrections") or []:
        if row.get("metric") == metric:
            return dict(row)

    return None


def case_key(row: dict[str, str]) -> str:
    return (
        row.get("pair_id")
        or row.get("wave_pdf_name")
        or ""
    )


def load_rows() -> list[dict[str, str]]:
    if not SHADOW_ROWS_PATH.exists():
        raise FileNotFoundError(
            SHADOW_ROWS_PATH
        )

    with SHADOW_ROWS_PATH.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as handle:
        return list(csv.DictReader(handle))


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
        "runtime_enabled",
        "expected_status",
        "actual_status",
        "raw_value",
        "wave_value",
        "direct_corrected_value",
        "runtime_output_value",
        "shadow_corrected_value",
        "raw_error_pct",
        "runtime_error_pct",
        "value_match",
        "model_match",
        "guard_reason",
        "output_path",
        "case_report_status",
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
        print(
            f"FAIL: missing layer: {LAYER_PATH}"
        )
        return 1

    layer = json.loads(
        LAYER_PATH.read_text(encoding="utf-8")
    )

    source_rows = load_rows()

    if len(source_rows) != EXPECTED_TOTAL_ROWS:
        raise RuntimeError(
            "Expected 45 shadow rows, "
            f"actual={len(source_rows)}"
        )

    grouped: dict[
        str,
        list[dict[str, str]],
    ] = defaultdict(list)

    for row in source_rows:
        key = case_key(row)

        if not key:
            raise RuntimeError(
                f"Missing case key: {row}"
            )

        grouped[key].append(row)

    if len(grouped) != 15:
        raise RuntimeError(
            "Expected 15 NF cases, "
            f"actual={len(grouped)}"
        )

    output_rows: list[dict[str, Any]] = []
    case_reports: list[dict[str, Any]] = []

    failure_messages: list[str] = []

    for key, rows in sorted(grouped.items()):
        if len(rows) != 3:
            failure_messages.append(
                f"{key}: expected 3 metric rows, "
                f"actual={len(rows)}"
            )
            continue

        membrane_values = {
            row["membrane"]
            for row in rows
        }

        if len(membrane_values) != 1:
            failure_messages.append(
                f"{key}: mixed membranes "
                f"{sorted(membrane_values)}"
            )
            continue

        membrane = next(iter(membrane_values))

        if membrane not in MEMBRANE_NAMES:
            failure_messages.append(
                f"{key}: unknown membrane={membrane}"
            )
            continue

        by_metric = {
            row["metric"]: row
            for row in rows
        }

        missing_metrics = (
            set(METRIC_OUTPUT_KEYS)
            - set(by_metric)
        )

        if missing_metrics:
            failure_messages.append(
                f"{key}: missing metrics="
                f"{sorted(missing_metrics)}"
            )
            continue

        raw_system = {}

        for metric, output_key in (
            METRIC_OUTPUT_KEYS.items()
        ):
            raw_system[output_key] = number(
                by_metric[metric][
                    "aquanova_raw_value"
                ]
            )

        raw_result = {
            "process_type": "nf",
            "system": raw_system,
        }

        options = {
            "enable_wave_correction": True,
            "wave_membrane_model": (
                MEMBRANE_NAMES[membrane]
            ),
        }

        corrected_result, report = (
            apply_wave_runtime_corrections_to_output(
                raw_result,
                layer,
                options=options,
                config={"enabled": True},
            )
        )

        expected_applied = (
            3 if membrane == "NF270" else 2
        )

        expected_shadow = (
            0 if membrane == "NF270" else 1
        )

        case_report = {
            "pair_id": key,
            "membrane": membrane,
            "status": report.get("status"),
            "applied_count": report.get(
                "applied_count", 0
            ),
            "shadow_count": report.get(
                "shadow_count", 0
            ),
            "skipped_count": report.get(
                "skipped_count", 0
            ),
            "expected_applied_count": (
                expected_applied
            ),
            "expected_shadow_count": (
                expected_shadow
            ),
        }

        case_reports.append(case_report)

        if report.get("status") != "corrected":
            failure_messages.append(
                f"{key}: runtime report status="
                f"{report.get('status')}"
            )

        if (
            int(report.get("applied_count", 0))
            != expected_applied
        ):
            failure_messages.append(
                f"{key}: applied_count="
                f"{report.get('applied_count')} "
                f"expected={expected_applied}"
            )

        if (
            int(report.get("shadow_count", 0))
            != expected_shadow
        ):
            failure_messages.append(
                f"{key}: shadow_count="
                f"{report.get('shadow_count')} "
                f"expected={expected_shadow}"
            )

        for metric, source in by_metric.items():
            report_row = find_report_row(
                report,
                metric,
            )

            runtime_enabled = boolish(
                source["runtime_enabled"]
            )

            expected_status = (
                "applied"
                if runtime_enabled
                else "shadow_only"
            )

            expected_model_id = source[
                "model_id"
            ]

            raw_value = number(
                source["aquanova_raw_value"]
            )

            wave_value = number(
                source["wave_value"]
            )

            direct_corrected = number(
                source["corrected_value"]
            )

            output_key = METRIC_OUTPUT_KEYS[
                metric
            ]

            runtime_output = number(
                corrected_result["system"][
                    output_key
                ]
            )

            actual_status = (
                report_row.get("status")
                if report_row
                else "missing_report_row"
            )

            actual_model_id = (
                report_row.get("model_id", "")
                if report_row
                else ""
            )

            model_match = (
                actual_model_id
                == expected_model_id
            )

            shadow_corrected = None
            guard_reason = ""
            output_path = ""

            if report_row:
                shadow_value = report_row.get(
                    "shadow_corrected_value"
                )

                if shadow_value is not None:
                    shadow_corrected = number(
                        shadow_value
                    )

                guard_reason = str(
                    report_row.get(
                        "guard_reason", ""
                    )
                )

                output_path = str(
                    report_row.get("path", "")
                )

            if runtime_enabled:
                value_match = close(
                    runtime_output,
                    direct_corrected,
                )

                runtime_error = abs_error_pct(
                    runtime_output,
                    wave_value,
                )
            else:
                value_match = (
                    close(runtime_output, raw_value)
                    and shadow_corrected is not None
                    and close(
                        shadow_corrected,
                        direct_corrected,
                    )
                )

                runtime_error = abs_error_pct(
                    runtime_output,
                    wave_value,
                )

            if actual_status != expected_status:
                failure_messages.append(
                    f"{key}/{metric}: "
                    f"status={actual_status}, "
                    f"expected={expected_status}, "
                    f"guard={guard_reason}"
                )

            if not model_match:
                failure_messages.append(
                    f"{key}/{metric}: "
                    f"model={actual_model_id}, "
                    f"expected={expected_model_id}"
                )

            if not value_match:
                failure_messages.append(
                    f"{key}/{metric}: "
                    "runtime/direct value mismatch "
                    f"runtime={runtime_output}, "
                    f"direct={direct_corrected}, "
                    f"raw={raw_value}, "
                    f"shadow={shadow_corrected}"
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
                    "model_id": actual_model_id,
                    "runtime_enabled": (
                        runtime_enabled
                    ),
                    "expected_status": (
                        expected_status
                    ),
                    "actual_status": actual_status,
                    "raw_value": raw_value,
                    "wave_value": wave_value,
                    "direct_corrected_value": (
                        direct_corrected
                    ),
                    "runtime_output_value": (
                        runtime_output
                    ),
                    "shadow_corrected_value": (
                        shadow_corrected
                    ),
                    "raw_error_pct": abs_error_pct(
                        raw_value,
                        wave_value,
                    ),
                    "runtime_error_pct": (
                        runtime_error
                    ),
                    "value_match": value_match,
                    "model_match": model_match,
                    "guard_reason": guard_reason,
                    "output_path": output_path,
                    "case_report_status": (
                        report.get("status")
                    ),
                }
            )

    write_csv(output_rows)

    status_counts = Counter(
        row["actual_status"]
        for row in output_rows
    )

    membrane_case_counts = Counter(
        report["membrane"]
        for report in case_reports
    )

    guard_rows = [
        row
        for row in output_rows
        if row["actual_status"]
        == "blocked_runtime_guard"
    ]

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

    raw_errors = [
        float(row["raw_error_pct"])
        for row in output_rows
    ]

    runtime_effective_errors = []

    for row in output_rows:
        if row["runtime_enabled"]:
            runtime_effective_errors.append(
                float(row["runtime_error_pct"])
            )
        else:
            # Shadow models are intentionally not part
            # of runtime-effective MAE.
            pass

    summary = {
        "schema_version": (
            "aquanova.nf_runtime_bridge_validation.v130"
        ),
        "case_count": len(case_reports),
        "row_count": len(output_rows),
        "runtime_candidate_row_count": len(
            runtime_rows
        ),
        "shadow_only_row_count": len(
            shadow_rows
        ),
        "status_counts": dict(
            status_counts
        ),
        "membrane_case_counts": dict(
            membrane_case_counts
        ),
        "blocked_runtime_guard_count": len(
            guard_rows
        ),
        "failure_count": len(
            failure_messages
        ),
        "raw_all_row_mae_pct": mean(
            raw_errors
        ),
        "runtime_candidate_effective_mae_pct": (
            mean(runtime_effective_errors)
        ),
        "failures": failure_messages,
        "cases": case_reports,
        "status": (
            "PASS"
            if not failure_messages
            else "FAIL"
        ),
    }

    OUTPUT_JSON.write_text(
        json.dumps(
            summary,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    markdown = [
        "# V130 NF Runtime Bridge Validation",
        "",
        f"- Cases: {len(case_reports)}",
        f"- Rows: {len(output_rows)}",
        (
            "- Runtime candidates: "
            f"{len(runtime_rows)}"
        ),
        (
            "- Shadow only: "
            f"{len(shadow_rows)}"
        ),
        (
            "- Runtime guard blocks: "
            f"{len(guard_rows)}"
        ),
        (
            "- Failures: "
            f"{len(failure_messages)}"
        ),
        (
            "- Runtime-candidate effective MAE: "
            f"{summary['runtime_candidate_effective_mae_pct']:.6f}%"
        ),
        "",
        "## Status counts",
        "",
    ]

    for status, count in sorted(
        status_counts.items()
    ):
        markdown.append(
            f"- {status}: {count}"
        )

    if failure_messages:
        markdown.extend(
            [
                "",
                "## Failures",
                "",
            ]
        )

        for message in failure_messages:
            markdown.append(f"- {message}")

    markdown.extend(
        [
            "",
            "## Result",
            "",
            (
                "**PASS**"
                if not failure_messages
                else "**FAIL**"
            ),
            "",
        ]
    )

    OUTPUT_MD.write_text(
        "\n".join(markdown),
        encoding="utf-8",
    )

    print("=" * 80)
    print("V130 NF RUNTIME BRIDGE VALIDATION")
    print("=" * 80)
    print(f"case_count={len(case_reports)}")
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
        f"status_counts="
        f"{dict(status_counts)}"
    )
    print(
        f"membrane_case_counts="
        f"{dict(membrane_case_counts)}"
    )
    print(
        f"blocked_runtime_guard_count="
        f"{len(guard_rows)}"
    )
    print(
        f"failure_count="
        f"{len(failure_messages)}"
    )
    print(
        "runtime_candidate_effective_mae="
        f"{summary['runtime_candidate_effective_mae_pct']:.6f}%"
    )

    if failure_messages:
        print("\nFAILURES")

        for message in failure_messages:
            print(f"- {message}")

    print(f"\ncsv={OUTPUT_CSV}")
    print(f"json={OUTPUT_JSON}")
    print(f"markdown={OUTPUT_MD}")

    if failure_messages:
        print(
            "\nV130 NF runtime bridge "
            "validation FAIL"
        )
        return 1

    if len(output_rows) != EXPECTED_TOTAL_ROWS:
        raise RuntimeError(
            f"Expected rows={EXPECTED_TOTAL_ROWS}, "
            f"actual={len(output_rows)}"
        )

    if len(runtime_rows) != EXPECTED_RUNTIME_ROWS:
        raise RuntimeError(
            f"Expected runtime rows="
            f"{EXPECTED_RUNTIME_ROWS}, "
            f"actual={len(runtime_rows)}"
        )

    if len(shadow_rows) != EXPECTED_SHADOW_ROWS:
        raise RuntimeError(
            f"Expected shadow rows="
            f"{EXPECTED_SHADOW_ROWS}, "
            f"actual={len(shadow_rows)}"
        )

    if dict(membrane_case_counts) != (
        EXPECTED_CASE_COUNTS
    ):
        raise RuntimeError(
            "Membrane case-count mismatch: "
            f"{dict(membrane_case_counts)}"
        )

    print(
        "\nV130 NF runtime bridge "
        "validation PASS"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
