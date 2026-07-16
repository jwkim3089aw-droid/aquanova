from __future__ import annotations

import csv
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
CORPUS_DIR = ROOT / "scripts/wave_records/results/_report_corpus"

SOURCE = CORPUS_DIR / "v129_nf_v90_metric_errors.csv"

OUTPUTS = {
    "NF270": CORPUS_DIR / "v129_nf270_v90_metric_errors.csv",
    "NF90": CORPUS_DIR / "v129_nf90_v90_metric_errors.csv",
}

# 각 막에서 운전 조건이 한쪽으로 몰리지 않도록 명시적으로 지정한다.
#
# NF270:
#   Low Hardness R85
#   Med Hardness R65
#   High Hardness R75
#
# NF90:
#   Low Hardness R85
#   High Hardness R65
HOLDOUT_CASE_IDS = {
    "NF270": {
        "V128_NF_002",
        "V128_NF_003",
        "V46_NF_001",
    },
    "NF90": {
        "V128_NF_008",
        "V128_NF_011",
    },
}

EXPECTED_METRICS = {
    "feed_pressure",
    "product_tds",
    "final_concentrate_tds",
    "specific_energy",
    "recovery",
}


def normalize(value: Any) -> str:
    return re.sub(
        r"[^a-z0-9]+",
        "",
        str(value or "").lower(),
    )


def membrane_of(row: dict[str, str]) -> str:
    hint = row.get("membrane_model_hint", "")

    match = re.search(
        r"\b(NF270|NF90)\b",
        hint,
        re.IGNORECASE,
    )

    if match:
        return match.group(1).upper()

    text = " ".join(
        str(value)
        for value in row.values()
        if value not in (None, "")
    )

    match = re.search(
        r"\b(NF270|NF90)\b",
        text,
        re.IGNORECASE,
    )

    if match:
        return match.group(1).upper()

    return "UNKNOWN"


def case_id_of(row: dict[str, str]) -> str:
    pdf_name = row.get("wave_pdf_name", "")

    match = re.search(
        r"(?<![A-Za-z0-9])(V(?:128|46)_NF_\d{3})(?=_|\.|$)",
        pdf_name,
        re.IGNORECASE,
    )

    if not match:
        return ""

    return match.group(1).upper()


def write_rows(
    path: Path,
    fieldnames: list[str],
    rows: list[dict[str, str]],
) -> None:
    with path.open(
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


def validate_scope(
    membrane: str,
    rows: list[dict[str, str]],
) -> None:
    expected_total = 8 if membrane == "NF270" else 7
    expected_train = 5
    expected_holdout = 3 if membrane == "NF270" else 2

    metric_rows: dict[str, list[dict[str, str]]] = defaultdict(list)

    for row in rows:
        metric_rows[row["metric"]].append(row)

    actual_metrics = set(metric_rows)

    if actual_metrics != EXPECTED_METRICS:
        raise RuntimeError(
            f"{membrane}: metric mismatch "
            f"expected={sorted(EXPECTED_METRICS)} "
            f"actual={sorted(actual_metrics)}"
        )

    for metric in sorted(EXPECTED_METRICS):
        metric_subset = metric_rows[metric]

        split_counts = Counter(
            row["split"]
            for row in metric_subset
        )

        if len(metric_subset) != expected_total:
            raise RuntimeError(
                f"{membrane}/{metric}: "
                f"expected total={expected_total}, "
                f"actual={len(metric_subset)}"
            )

        if split_counts["train"] != expected_train:
            raise RuntimeError(
                f"{membrane}/{metric}: "
                f"expected train={expected_train}, "
                f"actual={split_counts['train']}"
            )

        if split_counts["holdout"] != expected_holdout:
            raise RuntimeError(
                f"{membrane}/{metric}: "
                f"expected holdout={expected_holdout}, "
                f"actual={split_counts['holdout']}"
            )


def main() -> int:
    if not SOURCE.exists():
        print(f"FAIL: source not found: {SOURCE}")
        return 1

    with SOURCE.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        source_rows = list(reader)

    required_columns = {
        "pair_id",
        "split",
        "process_type",
        "metric",
        "wave_pdf_name",
        "membrane_model_hint",
    }

    missing = sorted(required_columns - set(fieldnames))

    if missing:
        print(f"FAIL: required columns missing: {missing}")
        return 1

    if len(source_rows) != 75:
        print(
            "FAIL: expected 75 source metric rows, "
            f"actual={len(source_rows)}"
        )
        return 1

    scoped_rows = {
        "NF270": [],
        "NF90": [],
    }

    unknown_rows = []

    for original in source_rows:
        row = dict(original)

        membrane = membrane_of(row)
        case_id = case_id_of(row)

        if membrane not in scoped_rows:
            unknown_rows.append(
                {
                    "pdf": row.get("wave_pdf_name"),
                    "hint": row.get("membrane_model_hint"),
                }
            )
            continue

        if not case_id:
            print(
                "FAIL: case id could not be detected: "
                f"{row.get('wave_pdf_name')}"
            )
            return 1

        row["split"] = (
            "holdout"
            if case_id in HOLDOUT_CASE_IDS[membrane]
            else "train"
        )

        # V91이 이미 지원하는 NF 처리 경로를 그대로 사용한다.
        row["process_type"] = "nf"

        scoped_rows[membrane].append(row)

    if unknown_rows:
        print(f"FAIL: unknown membrane rows: {unknown_rows}")
        return 1

    validate_scope("NF270", scoped_rows["NF270"])
    validate_scope("NF90", scoped_rows["NF90"])

    for membrane, output_path in OUTPUTS.items():
        write_rows(
            output_path,
            fieldnames,
            scoped_rows[membrane],
        )

    print("=" * 80)
    print("V129 NF MEMBRANE-SCOPED V90 SPLIT")
    print("=" * 80)
    print(f"source={SOURCE}")
    print(f"source_rows={len(source_rows)}")

    for membrane in ("NF270", "NF90"):
        rows = scoped_rows[membrane]

        pair_splits = {}

        for row in rows:
            case_id = case_id_of(row)
            pair_splits[case_id] = row["split"]

        metric_counts = Counter(
            row["metric"]
            for row in rows
        )

        split_counts = Counter(
            row["split"]
            for row in rows
        )

        print(f"\n{membrane}")
        print(f"metric_rows={len(rows)}")
        print(f"case_count={len(pair_splits)}")
        print(f"metric_counts={dict(metric_counts)}")
        print(f"metric_row_split_counts={dict(split_counts)}")
        print(f"output={OUTPUTS[membrane]}")

        print("cases:")

        for case_id, split in sorted(pair_splits.items()):
            print(f"  {case_id}: {split}")

    print("\nV129 NF membrane-scoped split PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
