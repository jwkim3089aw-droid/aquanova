from __future__ import annotations

import csv
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
CORPUS_DIR = ROOT / "scripts/wave_records/results/_report_corpus"

SOURCE_CSV = CORPUS_DIR / "v129_nf_all_v88_calibration_pairs.csv"
OUTPUT_CSV = CORPUS_DIR / "v129_nf_v88_calibration_pairs.csv"
OUTPUT_JSON = CORPUS_DIR / "v129_nf_v88_calibration_pairs.json"


def normalize(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def first_value(row: dict[str, Any], *keys: str):
    normalized = {
        normalize(key): value
        for key, value in row.items()
    }

    for key in keys:
        value = normalized.get(normalize(key))
        if value not in (None, ""):
            return value

    return None


def row_text(row: dict[str, Any]) -> str:
    return " ".join(
        str(value)
        for value in row.values()
        if value not in (None, "")
    )


def detect_process(row: dict[str, Any]) -> str:
    value = first_value(
        row,
        "process_type",
        "process",
        "technology",
        "wave_process_type",
    )

    if value is not None:
        return normalize(value)

    text = row_text(row).lower()

    if re.search(r"\bnf(?:90|200|270)?\b", text):
        return "nf"

    return ""


def detect_membrane(row: dict[str, Any]) -> str:
    value = first_value(
        row,
        "membrane",
        "membrane_name",
        "element",
        "element_name",
        "p1s1_membrane",
    )

    text = f"{value or ''} {row_text(row)}"

    match = re.search(r"\b(NF270|NF90)\b", text, re.IGNORECASE)
    return match.group(1).upper() if match else "unknown"


def detect_case_name(row: dict[str, Any]) -> str:
    value = first_value(
        row,
        "wave_pdf_name",
        "pdf_name",
        "source_name",
        "filename",
        "file_name",
        "case_id",
    )

    return str(value or "")


def main() -> int:
    if not SOURCE_CSV.exists():
        print(f"FAIL: source V88 CSV not found: {SOURCE_CSV}")
        return 1

    with SOURCE_CSV.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)

    if not fieldnames:
        print("FAIL: V88 CSV has no header")
        return 1

    nf_rows = [
        row
        for row in rows
        if detect_process(row) == "nf"
    ]

    membrane_counts = Counter(
        detect_membrane(row)
        for row in nf_rows
    )

    if len(nf_rows) != 15:
        print(
            "FAIL: expected 15 NF pair rows, "
            f"actual={len(nf_rows)}"
        )
        print(f"headers={fieldnames}")
        return 1

    if dict(membrane_counts) != {
        "NF270": 8,
        "NF90": 7,
    }:
        print(
            "FAIL: membrane distribution mismatch: "
            f"{dict(membrane_counts)}"
        )
        return 1

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
        writer.writerows(nf_rows)

    OUTPUT_JSON.write_text(
        json.dumps(
            {
                "schema_version": (
                    "aquanova.nf_v88_pairs.v129"
                ),
                "source": str(SOURCE_CSV),
                "row_count": len(nf_rows),
                "membrane_counts": dict(membrane_counts),
                "rows": nf_rows,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print("=" * 80)
    print("V129 NF V88 PAIR EXTRACTION")
    print("=" * 80)
    print(f"source_rows={len(rows)}")
    print(f"nf_rows={len(nf_rows)}")
    print(f"membrane_counts={dict(membrane_counts)}")
    print(f"column_count={len(fieldnames)}")
    print(f"output_csv={OUTPUT_CSV}")
    print(f"output_json={OUTPUT_JSON}")

    print("\nNF CASES")

    for index, row in enumerate(nf_rows, start=1):
        print(
            f"{index:02d}. "
            f"{detect_case_name(row)} | "
            f"{detect_membrane(row)}"
        )

    print("\nV129 NF V88 pair extraction PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
