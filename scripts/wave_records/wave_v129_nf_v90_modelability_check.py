from __future__ import annotations

import csv
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PATH = (
    ROOT
    / "scripts/wave_records/results/_report_corpus"
    / "v129_nf_v90_metric_errors.csv"
)


def normalize(value):
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def get_value(row, *names):
    normalized = {
        normalize(key): value
        for key, value in row.items()
    }

    for name in names:
        value = normalized.get(normalize(name))
        if value not in (None, ""):
            return value

    return ""


def membrane_of(row):
    text = " ".join(str(value) for value in row.values())

    if re.search(r"\bNF270\b", text, re.IGNORECASE):
        return "NF270"

    if re.search(r"\bNF90\b", text, re.IGNORECASE):
        return "NF90"

    return "unknown"


def main():
    if not PATH.exists():
        print(f"FAIL: missing {PATH}")
        return 1

    with PATH.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as handle:
        reader = csv.DictReader(handle)
        fields = list(reader.fieldnames or [])
        rows = list(reader)

    print("=" * 80)
    print("V129 NF V90 MODELABILITY CHECK")
    print("=" * 80)
    print(f"file={PATH}")
    print(f"rows={len(rows)}")
    print(f"columns={len(fields)}")
    print(f"headers={fields}")

    process_counts = Counter(
        get_value(
            row,
            "process_type",
            "process",
            "technology",
        )
        for row in rows
    )

    metric_counts = Counter(
        get_value(
            row,
            "metric",
            "metric_name",
            "target_metric",
        )
        for row in rows
    )

    membrane_counts = Counter(
        membrane_of(row)
        for row in rows
    )

    split_counts = Counter(
        get_value(
            row,
            "split",
            "dataset_split",
            "train_holdout",
        )
        for row in rows
    )

    metric_membrane = defaultdict(Counter)
    metric_split = defaultdict(Counter)

    for row in rows:
        metric = get_value(
            row,
            "metric",
            "metric_name",
            "target_metric",
        )

        metric_membrane[metric][membrane_of(row)] += 1

        split = get_value(
            row,
            "split",
            "dataset_split",
            "train_holdout",
        )

        metric_split[metric][split] += 1

    print(f"\nprocess_counts={dict(process_counts)}")
    print(f"membrane_counts={dict(membrane_counts)}")
    print(f"split_counts={dict(split_counts)}")

    print("\nMETRIC COUNTS")

    for metric, count in metric_counts.most_common():
        print(
            f"{metric}: total={count} "
            f"membranes={dict(metric_membrane[metric])} "
            f"splits={dict(metric_split[metric])}"
        )

    has_membrane_column = any(
        "membrane" in normalize(field)
        or "element" in normalize(field)
        for field in fields
    )

    print(f"\nhas_membrane_column={has_membrane_column}")

    if set(process_counts) == {"nf"}:
        print(
            "status=MEMBRANE_SCOPE_SPLIT_REQUIRED_BEFORE_V91"
        )
    else:
        print(
            "status=CHECK_PROCESS_SCOPE_BEFORE_V91"
        )

    print("\nV129 NF V90 modelability check PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
