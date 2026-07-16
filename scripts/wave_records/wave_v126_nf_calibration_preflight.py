from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CORPUS_DIR = ROOT / "scripts/wave_records/results/_report_corpus"
OUT_DIR = CORPUS_DIR


def value_from(record: dict, *names):
    for name in names:
        value = record.get(name)
        if value not in (None, ""):
            return value
    return None


def main() -> int:
    import re

    corpus_files = sorted(
        [
            path
            for path in CORPUS_DIR.glob("wave_report_corpus_*.json")
            if re.fullmatch(
                r"wave_report_corpus_\d{8}_\d{6}\.json",
                path.name,
            )
        ],
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )

    if not corpus_files:
        print(f"FAIL: corpus JSON not found: {CORPUS_DIR}")
        return 1

    corpus_path = corpus_files[0]
    payload = json.loads(corpus_path.read_text(encoding="utf-8"))

    if isinstance(payload, dict):
        records = payload.get("records") or payload.get("rows") or []
    elif isinstance(payload, list):
        records = payload
    else:
        records = []

    nf_records = [
        record
        for record in records
        if isinstance(record, dict)
        and str(
            value_from(record, "process_type", "process", "technology") or ""
        ).strip().lower() == "nf"
    ]

    rows = []
    for record in nf_records:
        metrics = record.get("metrics")
        if not isinstance(metrics, dict):
            metrics = {}

        rows.append(
            {
                "wave_pdf_name": value_from(
                    record,
                    "wave_pdf_name",
                    "pdf_name",
                    "source_name",
                    "filename",
                ),
                "membrane": value_from(
                    record,
                    "membrane",
                    "membrane_name",
                    "element",
                ),
                "feed_tds": value_from(
                    record,
                    "feed_tds_mgL",
                    "feed_tds",
                )
                or metrics.get("feed_tds_mgL"),
                "recovery_pct": value_from(
                    record,
                    "recovery_pct",
                    "recovery",
                )
                or metrics.get("recovery_pct"),
                "feed_pressure_bar": value_from(
                    record,
                    "feed_pressure_bar",
                    "feed_pressure",
                )
                or metrics.get("feed_pressure_bar"),
                "product_tds_mgL": value_from(
                    record,
                    "product_tds_mgL",
                    "product_tds",
                )
                or metrics.get("product_tds_mgL"),
                "warning_count": len(record.get("warnings") or []),
            }
        )

    out_csv = OUT_DIR / "v126_nf_anchor_inventory.csv"

    with out_csv.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "wave_pdf_name",
                "membrane",
                "feed_tds",
                "recovery_pct",
                "feed_pressure_bar",
                "product_tds_mgL",
                "warning_count",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    membrane_counts = Counter(
        str(row["membrane"] or "unknown") for row in rows
    )

    print("=" * 80)
    print("V126 NF CALIBRATION PREFLIGHT")
    print("=" * 80)
    print(f"corpus={corpus_path}")
    print(f"total_records={len(records)}")
    print(f"nf_record_count={len(rows)}")
    print(f"membrane_counts={dict(membrane_counts)}")
    print(f"inventory_csv={out_csv}")

    print("\nNF RECORDS")
    for index, row in enumerate(rows, start=1):
        print(
            f"{index}. {row['wave_pdf_name']} | "
            f"membrane={row['membrane']} | "
            f"recovery={row['recovery_pct']} | "
            f"pressure={row['feed_pressure_bar']} | "
            f"product_tds={row['product_tds_mgL']}"
        )

    missing = max(0, 15 - len(rows))

    print("\nRECOMMENDATION")
    if len(rows) < 8:
        print("status=INSUFFICIENT")
    elif len(rows) < 15:
        print("status=EXPANSION_REQUIRED")
    else:
        print("status=MINIMUM_ANCHOR_COUNT_REACHED")

    print(f"recommended_minimum_nf_records=15")
    print(f"additional_records_needed={missing}")
    print("\nV126 NF calibration preflight PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

