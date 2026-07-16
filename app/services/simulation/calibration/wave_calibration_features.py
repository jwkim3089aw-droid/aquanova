"""Feature extraction helpers for WAVE-anchor nonlinear calibration.

This module is intentionally schema-tolerant because the WAVE report corpus is
built from PDFs and historical feedback bundles whose JSON shape can vary by
version.  It flattens records, preserves traceability fields, and extracts a
stable set of candidate feature/target columns for later nonlinear correction
layers.

It does *not* fit a model yet.  V84's job is to make the WAVE anchor extraction
and calibration-table intake reproducible before we train/tune correction
functions.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Iterable, Mapping

FEATURE_HINTS = (
    "process", "kind", "case", "membrane", "element", "module", "water", "profile",
    "feed", "product", "permeate", "concentrate", "recovery", "tds", "temperature",
    "flux", "flow_factor", "stage", "pass", "pf_feed_ratio", "pf_recovery",
    "cc_recovery", "cc_concentrate", "pf_concentrate", "cycles", "duration",
    "pressure", "ndp", "tmp", "backwash", "ceb", "warning", "classification",
)

CALIBRATION_TARGET_HINTS = (
    "product_tds", "permeate_tds", "final_concentrate_tds", "feed_pressure",
    "ndp", "specific_energy", "average_flux", "recovery", "tmp", "warning",
)

TRACE_KEYS = ("source_file", "pdf", "pdf_name", "case_id", "id", "kind", "process", "classification")


def _safe_key(part: str) -> str:
    out = []
    for ch in str(part).strip():
        if ch.isalnum():
            out.append(ch.lower())
        else:
            out.append("_")
    key = "".join(out).strip("_")
    while "__" in key:
        key = key.replace("__", "_")
    return key or "value"


def flatten_record(record: Mapping[str, Any], *, prefix: str = "", max_list_items: int = 12) -> dict[str, Any]:
    """Flatten a nested corpus record into a one-level dictionary."""
    flat: dict[str, Any] = {}

    def visit(value: Any, parts: list[str]) -> None:
        key = "__".join(_safe_key(p) for p in parts if str(p) != "")
        if isinstance(value, Mapping):
            for k, v in value.items():
                visit(v, parts + [str(k)])
        elif isinstance(value, list):
            # Keep small scalar lists; expand small lists of dicts for traceability.
            if all(not isinstance(x, (Mapping, list)) for x in value):
                flat[key] = "|".join(str(x) for x in value)
            else:
                for idx, item in enumerate(value[:max_list_items]):
                    visit(item, parts + [str(idx)])
                if len(value) > max_list_items:
                    flat[f"{key}__truncated_count"] = len(value) - max_list_items
        else:
            flat[key] = value

    visit(record, [prefix] if prefix else [])
    return flat


def _records_from_json_payload(payload: Any) -> list[Mapping[str, Any]]:
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, Mapping)]
    if isinstance(payload, Mapping):
        for key in ("records", "items", "rows", "cases", "data"):
            maybe = payload.get(key)
            if isinstance(maybe, list):
                return [x for x in maybe if isinstance(x, Mapping)]
        # Some exports are a single record.
        return [payload]
    return []


def load_wave_corpus_records(path: str | Path) -> list[dict[str, Any]]:
    """Load records from a V81 corpus JSON/CSV/MD-adjacent path.

    JSON is preferred.  CSV is accepted for quick inspection workflows.  Markdown
    is not parsed because it is a rendered report, not a stable data format.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(p)
    suffix = p.suffix.lower()
    if suffix == ".json":
        payload = json.loads(p.read_text(encoding="utf-8"))
        return [dict(x) for x in _records_from_json_payload(payload)]
    if suffix == ".csv":
        with p.open("r", encoding="utf-8-sig", newline="") as f:
            return [dict(row) for row in csv.DictReader(f)]
    raise ValueError(f"Unsupported corpus file type: {p.suffix}. Use JSON or CSV.")


def _looks_relevant(key: str) -> bool:
    lk = key.lower()
    return any(hint in lk for hint in FEATURE_HINTS)


def _looks_target(key: str) -> bool:
    lk = key.lower()
    return any(hint in lk for hint in CALIBRATION_TARGET_HINTS)


def _to_float_or_original(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        if isinstance(value, float) and not math.isfinite(value):
            return None
        return value
    text = str(value).strip().replace(",", "")
    if text == "":
        return ""
    # Strip common units that appear in corpus CSVs.
    for token in ("m3/h", "m³/h", "mg/L", "bar", "%", "LMH", "kWh/m3", "kWh/m³", "min", "cycles"):
        text = text.replace(token, "")
    try:
        number = float(text.strip())
        if math.isfinite(number):
            return number
    except ValueError:
        return value
    return value


def _stable_split_id(row: Mapping[str, Any]) -> str:
    seed_parts = []
    for key in TRACE_KEYS:
        for actual_key, value in row.items():
            if actual_key.endswith(key) or actual_key == key:
                seed_parts.append(str(value))
                break
    if not seed_parts:
        seed_parts = [json.dumps(row, ensure_ascii=False, sort_keys=True)[:500]]
    digest = hashlib.sha1("|".join(seed_parts).encode("utf-8", errors="ignore")).hexdigest()
    bucket = int(digest[:8], 16) % 10
    return "holdout" if bucket in {0, 1} else "train"


def build_feature_rows(records: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Build flattened candidate feature rows from WAVE corpus records."""
    rows: list[dict[str, Any]] = []
    for idx, record in enumerate(records):
        flat = flatten_record(record)
        row: dict[str, Any] = {"row_index": idx}
        # Trace fields first.
        for key, value in flat.items():
            lk = key.lower()
            if any(lk.endswith(trace) or lk == trace for trace in TRACE_KEYS):
                row[f"trace__{key}"] = value
        # Candidate features/targets.
        for key, value in flat.items():
            if _looks_relevant(key):
                prefix = "target_candidate" if _looks_target(key) else "feature"
                row[f"{prefix}__{key}"] = _to_float_or_original(value)
        row["split"] = _stable_split_id(row or flat)
        rows.append(row)
    return rows


def write_feature_table(rows: list[Mapping[str, Any]], path: str | Path) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    keys: list[str] = []
    seen: set[str] = set()
    preferred_prefixes = ("row_index", "split", "trace__", "feature__", "target_candidate__")
    for prefix in preferred_prefixes:
        for row in rows:
            for key in row.keys():
                if key in seen:
                    continue
                if key == prefix or key.startswith(prefix):
                    keys.append(key)
                    seen.add(key)
    for row in rows:
        for key in row.keys():
            if key not in seen:
                keys.append(key)
                seen.add(key)
    with out.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        for row in rows:
            writer.writerow(dict(row))
    return out


def summarize_feature_rows(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"row_count": 0, "split_counts": {}, "feature_column_count": 0, "target_candidate_column_count": 0}
    split_counts: dict[str, int] = {}
    feature_cols: set[str] = set()
    target_cols: set[str] = set()
    for row in rows:
        split = str(row.get("split", "unknown"))
        split_counts[split] = split_counts.get(split, 0) + 1
        feature_cols.update(k for k in row if k.startswith("feature__"))
        target_cols.update(k for k in row if k.startswith("target_candidate__"))
    return {
        "row_count": len(rows),
        "split_counts": split_counts,
        "feature_column_count": len(feature_cols),
        "target_candidate_column_count": len(target_cols),
    }
