from __future__ import annotations

import csv
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
CORPUS_DIR = ROOT / "scripts/wave_records/results/_report_corpus"


def normalize(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def walk_dicts(obj: Any):
    if isinstance(obj, dict):
        yield obj
        for value in obj.values():
            yield from walk_dicts(value)
    elif isinstance(obj, list):
        for value in obj:
            yield from walk_dicts(value)


def direct_value(record: dict, *keys: str):
    wanted = {normalize(key) for key in keys}

    for obj in walk_dicts(record):
        for key, value in obj.items():
            if normalize(key) in wanted and not isinstance(value, (dict, list)):
                if value not in (None, ""):
                    return value

    return None


def build_metric_map(record: dict) -> dict[str, Any]:
    result: dict[str, Any] = {}

    label_keys = (
        "metric",
        "metric_name",
        "name",
        "key",
        "field",
        "parameter",
    )
    value_keys = (
        "value",
        "wave_value",
        "numeric_value",
        "metric_value",
        "result",
    )

    for obj in walk_dicts(record):
        # 일반 키-값 구조도 등록
        for key, value in obj.items():
            if not isinstance(value, (dict, list)) and value not in (None, ""):
                result.setdefault(normalize(key), value)

        # {"metric": "...", "value": ...} 형태 등록
        label = None
        for key in label_keys:
            if key in obj and obj[key] not in (None, ""):
                label = obj[key]
                break

        if label is None:
            continue

        metric_value = None
        for key in value_keys:
            if key in obj and not isinstance(obj[key], (dict, list)):
                if obj[key] not in (None, ""):
                    metric_value = obj[key]
                    break

        if metric_value is not None:
            result[normalize(label)] = metric_value

    return result


def metric_value(metric_map: dict[str, Any], *aliases: str):
    normalized_aliases = [normalize(alias) for alias in aliases]

    # 정확히 일치하는 이름 우선
    for alias in normalized_aliases:
        if alias in metric_map:
            return metric_map[alias]

    # system.product_tds_mgL 같은 경로형 이름 대응
    for alias in normalized_aliases:
        for key, value in metric_map.items():
            if key.endswith(alias):
                return value

    return None


def filename_value(record: dict) -> str:
    value = direct_value(
        record,
        "wave_pdf_name",
        "pdf_name",
        "source_name",
        "filename",
        "file_name",
    )
    return str(value or "")


def membrane_from_filename(filename: str):
    match = re.search(r"(NF270|NF90)", filename, re.IGNORECASE)
    return match.group(1).upper() if match else None


def recovery_from_filename(filename: str):
    match = re.search(r"(?:^|_)R(\d+(?:\.\d+)?)", filename, re.IGNORECASE)
    return float(match.group(1)) if match else None


def main() -> int:
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
        print(f"FAIL: original corpus JSON not found: {CORPUS_DIR}")
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
        and normalize(
            direct_value(record, "process_type", "process", "technology")
        ) == "nf"
    ]

    rows = []

    for record in nf_records:
        filename = filename_value(record)
        metrics = build_metric_map(record)

        membrane = (
            direct_value(
                record,
                "membrane",
                "membrane_name",
                "element",
                "element_name",
                "module_name",
            )
            or membrane_from_filename(filename)
        )

        recovery = metric_value(
            metrics,
            "recovery",
            "recovery_pct",
            "system_recovery_pct",
            "pass_recovery_pct",
        )

        if recovery in (None, ""):
            recovery = recovery_from_filename(filename)

        rows.append(
            {
                "wave_pdf_name": filename,
                "membrane": membrane,
                "feed_tds_mgL": metric_value(
                    metrics,
                    "feed_tds",
                    "feed_tds_mgL",
                    "raw_water_tds",
                ),
                "recovery_pct": recovery,
                "feed_pressure_bar": metric_value(
                    metrics,
                    "feed_pressure",
                    "feed_pressure_bar",
                    "pass_feed_pressure_bar",
                ),
                "product_tds_mgL": metric_value(
                    metrics,
                    "product_tds",
                    "product_tds_mgL",
                    "system_product_tds_mgL",
                ),
                "metric_count_detected": len(metrics),
            }
        )

    out_csv = CORPUS_DIR / "v126a_nf_anchor_inventory.csv"

    with out_csv.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()) if rows else [
            "wave_pdf_name",
            "membrane",
            "feed_tds_mgL",
            "recovery_pct",
            "feed_pressure_bar",
            "product_tds_mgL",
            "metric_count_detected",
        ])
        writer.writeheader()
        writer.writerows(rows)

    membrane_counts = Counter(
        str(row["membrane"] or "unknown") for row in rows
    )

    print("=" * 80)
    print("V126A NF CALIBRATION PREFLIGHT")
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
            f"product_tds={row['product_tds_mgL']} | "
            f"metrics={row['metric_count_detected']}"
        )

    missing = max(0, 15 - len(rows))

    print("\nRECOMMENDATION")

    if len(rows) < 8:
        print("status=INSUFFICIENT")
    elif len(rows) < 15:
        print("status=EXPANSION_REQUIRED")
    else:
        print("status=MINIMUM_ANCHOR_COUNT_REACHED")

    print("recommended_minimum_nf_records=15")
    print(f"additional_records_needed={missing}")

    print("\nV126A NF calibration preflight PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

