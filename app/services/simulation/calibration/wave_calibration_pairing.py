"""WAVE-to-AquaNova calibration pair-table helpers (V88).

V84 created a target-first WAVE feature table.  V88 turns the V81/V84 corpus
into a stable pairing surface for nonlinear correction work:

    WAVE target row  +  optional AquaNova raw result row  ->  calibration pair row

The module is intentionally conservative.  It never invents AquaNova raw values.
When no raw result is supplied, it emits a pair skeleton with ``pair_status`` set
to ``needs_aquanova_raw``.  Later runners can fill the AquaNova columns and then
fit correction functions against the WAVE targets.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

Number = int | float

WAVE_TARGET_METRIC_MAP: tuple[tuple[str, str], ...] = (
    ("wave_system_feed_flow_m3h", "system.feed_flow_m3h"),
    ("wave_system_concentrate_flow_m3h", "system.concentrate_flow_m3h"),
    ("wave_system_product_flow_m3h", "system.product_flow_m3h"),
    ("wave_system_recovery_pct", "system.recovery_pct"),
    ("wave_system_net_recovery_pct", "system.net_recovery_pct"),
    ("wave_system_product_tds_mgL", "system.product_tds_mgL"),
    ("wave_system_specific_energy_kwh_m3", "system.specific_energy_kwh_m3"),
    ("wave_system_temperature_c", "system.temperature_c"),
    ("wave_pass_feed_flow_m3h", "pass.feed_flow_m3h"),
    ("wave_pass_permeate_flow_m3h", "pass.permeate_flow_m3h"),
    ("wave_pass_feed_pressure_bar", "pass.feed_pressure_bar"),
    ("wave_pass_average_flux_lmh", "pass.average_flux_lmh"),
    ("wave_pass_recovery_pct", "pass.recovery_pct"),
    ("wave_pass_ndp_bar", "pass.ndp_bar"),
    ("wave_pass_final_concentrate_tds_mgL", "pass.final_concentrate_tds_mgL"),
    ("wave_uf_net_product_flow_m3h", "uf.net_product_flow_m3h"),
    ("wave_uf_recovery_pct", "uf.recovery_pct"),
    ("wave_uf_temperature_c", "uf.temperature_c"),
    ("wave_uf_ceb_interval", "uf.ceb_interval"),
    ("wave_ccro_cc_recovery_pct", "ccro.cc_recovery_pct"),
    ("wave_ccro_pf_recovery_pct", "ccro.pf_recovery_pct"),
    ("wave_ccro_pf_feed_ratio_pct", "ccro.pf_feed_ratio_pct"),
    ("wave_ccro_cc_concentrate_flow_m3h_per_pv", "ccro.cc_concentrate_flow_m3h_per_pv"),
    ("wave_ccro_pf_concentrate_flow_m3h_per_pv", "ccro.pf_concentrate_flow_m3h_per_pv"),
    ("wave_ccro_cc_net_feed_flow_m3h_per_pv", "ccro.cc_net_feed_flow_m3h_per_pv"),
    ("wave_ccro_pf_feed_flow_m3h_per_pv", "ccro.pf_feed_flow_m3h_per_pv"),
    ("wave_ccro_total_cycles", "ccro.total_cycles"),
    ("wave_ccro_pf_sequence_duration_min", "ccro.pf_sequence_duration_min"),
    ("wave_ccro_cc_sequence_duration_min", "ccro.cc_sequence_duration_min"),
    ("wave_ccro_complete_cycle_duration_min", "ccro.complete_cycle_duration_min"),
    ("wave_ccro_system_volume_m3", "ccro.cc_system_volume_m3"),
)

AQUANOVA_RAW_COLUMN_ALIASES: Mapping[str, tuple[str, ...]] = {
    "aquanova_case_id": ("Case_ID", "case_id", "id"),
    "aquanova_process": ("Process", "process", "process_type", "Water_Type"),
    "aquanova_membrane_model": ("Membrane_Model", "membrane_model", "element_model", "module_model"),
    "aquanova_feed_tds_mgL": ("Feed_TDS_mgL", "feed_tds_mgL", "feed_tds_mgl"),
    "aquanova_temperature_c": ("Temp_C", "temperature_c", "system_temperature_c"),
    "aquanova_target_recovery_pct": ("Target_Recovery_%", "target_recovery_pct"),
    "aquanova_result_recovery_pct": ("Result_Recovery_%", "result_recovery_pct", "recovery_pct"),
    "aquanova_feed_pressure_bar": ("Feed_Pressure_bar", "feed_pressure_bar", "pass_feed_pressure_bar"),
    "aquanova_permeate_flow_m3h": ("Permeate_Flow_m3h", "permeate_flow_m3h", "product_flow_m3h"),
    "aquanova_permeate_tds_mgL": ("Permeate_TDS_mgL", "permeate_tds_mgL", "product_tds_mgL"),
    "aquanova_brine_tds_mgL": ("Brine_TDS_mgL", "brine_tds_mgL", "final_concentrate_tds_mgL"),
    "aquanova_sec_kwh_m3": ("SEC_kwhm3", "sec_kwh_m3", "specific_energy_kwh_m3"),
    "aquanova_warnings": ("Warnings", "warnings", "design_warnings"),
    "aquanova_status": ("Status", "status"),
}

TARGETS_FOR_ERROR_COLUMNS: tuple[tuple[str, str, str], ...] = (
    ("feed_pressure", "wave_pass_feed_pressure_bar", "aquanova_feed_pressure_bar"),
    ("product_tds", "wave_system_product_tds_mgL", "aquanova_permeate_tds_mgL"),
    ("final_concentrate_tds", "wave_pass_final_concentrate_tds_mgL", "aquanova_brine_tds_mgL"),
    ("specific_energy", "wave_system_specific_energy_kwh_m3", "aquanova_sec_kwh_m3"),
    ("recovery", "wave_system_recovery_pct", "aquanova_result_recovery_pct"),
)


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        if math.isfinite(float(value)):
            return float(value)
        return None
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "null"}:
        return None
    text = text.replace(",", "")
    for token in ("m3/h", "m³/h", "mg/L", "mg/l", "bar", "%", "LMH", "kWh/m3", "kWh/m³", "min", "cycles"):
        text = text.replace(token, "")
    try:
        out = float(text.strip())
    except ValueError:
        return None
    return out if math.isfinite(out) else None


def _blank_to_none(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, str) and value.strip() == "":
        return None
    return value


def _norm_token(value: Any) -> str:
    text = "" if value is None else str(value)
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def _stable_id(*parts: Any, prefix: str = "pair") -> str:
    seed = "|".join(str(p) for p in parts if p is not None and str(p) != "")
    digest = hashlib.sha1(seed.encode("utf-8", errors="ignore")).hexdigest()[:12]
    return f"{prefix}_{digest}"


def _records_from_json_payload(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [dict(x) for x in payload if isinstance(x, Mapping)]
    if isinstance(payload, Mapping):
        for key in ("records", "items", "rows", "cases", "data"):
            maybe = payload.get(key)
            if isinstance(maybe, list):
                return [dict(x) for x in maybe if isinstance(x, Mapping)]
        return [dict(payload)]
    return []


def read_csv_rows(path: str | Path) -> list[dict[str, Any]]:
    p = Path(path)
    with p.open("r", encoding="utf-8-sig", newline="") as f:
        return [dict(row) for row in csv.DictReader(f)]


def load_corpus_records(path: str | Path) -> list[dict[str, Any]]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(p)
    if p.suffix.lower() == ".json":
        return _records_from_json_payload(json.loads(p.read_text(encoding="utf-8")))
    if p.suffix.lower() == ".csv":
        return read_csv_rows(p)
    raise ValueError(f"Unsupported corpus file type: {p.suffix}. Use JSON or CSV.")


def load_feature_splits(path: str | Path | None) -> dict[str, str]:
    if not path:
        return {}
    p = Path(path)
    if not p.exists():
        return {}
    splits: dict[str, str] = {}
    for row in read_csv_rows(p):
        pdf = row.get("trace__pdf_name") or row.get("trace__pdf") or row.get("pdf_name")
        split = row.get("split")
        if pdf and split:
            splits[str(pdf)] = str(split)
    return splits


def _metric(record: Mapping[str, Any], key: str) -> Any:
    metrics = record.get("metrics")
    if isinstance(metrics, Mapping):
        return metrics.get(key)
    return record.get(key) or record.get(key.replace(".", "__"))


def _extract_recovery_candidates(name: str) -> list[float]:
    values: list[float] = []
    for match in re.finditer(r"(?<![A-Z0-9])(?:P\d)?R(\d{2,3})(?![A-Z0-9])", name.upper()):
        value = _to_float(match.group(1))
        if value is not None:
            values.append(value)
    return values


def _extract_first_number_after(prefix: str, name: str) -> float | None:
    match = re.search(prefix + r"(\d{2,3})(?![A-Z0-9])", name.upper())
    if not match:
        return None
    return _to_float(match.group(1))


def infer_wave_case_metadata(record: Mapping[str, Any]) -> dict[str, Any]:
    pdf_name = str(record.get("pdf_name") or record.get("pdf") or record.get("source_file") or "")
    upper = pdf_name.upper()
    process = str(record.get("process") or record.get("report_family") or "unknown").lower()
    metrics = record.get("metrics") if isinstance(record.get("metrics"), Mapping) else {}

    recoveries = _extract_recovery_candidates(upper)
    metric_recovery = _to_float(metrics.get("system.recovery_pct") if isinstance(metrics, Mapping) else None)
    if metric_recovery is not None:
        target_recovery = metric_recovery
    elif recoveries:
        target_recovery = recoveries[-1]
    else:
        target_recovery = None

    temperature = _to_float(metrics.get("system.temperature_c") if isinstance(metrics, Mapping) else None)
    if temperature is None:
        temperature = _extract_first_number_after(r"(?<![A-Z0-9])T", upper)

    flow_factor_pct = _extract_first_number_after(r"(?<![A-Z0-9])F", upper)

    membrane_family = None
    membrane_model = None
    known_tokens = (
        "SOAR5000I", "SOAR-5000I", "BW30-400", "BW30", "NF270", "NF90",
        "SFP2660", "SFP-2660", "XFRLE", "XHR", "HRLE", "LCLE", "LC_HF", "LC_HR",
    )
    for token in known_tokens:
        if token in upper:
            membrane_model = token.replace("_", "-")
            if "NF" in token:
                membrane_family = "nf"
            elif "SFP" in token:
                membrane_family = "uf"
            elif "SOAR" in token:
                membrane_family = "soar"
            else:
                membrane_family = "ro"
            break

    pass_count = None
    if "2PASS" in upper or "P1R" in upper and "P2R" in upper:
        pass_count = 2
    elif "1PASS" in upper:
        pass_count = 1
    elif "2STAGE" in upper:
        pass_count = 1

    stage_count = None
    stage_match = re.search(r"(\d)STAGE", upper)
    if stage_match:
        stage_count = int(stage_match.group(1))

    water_profile = None
    if "LOWHARDNESS" in upper or "LOW_HARDNESS" in upper:
        water_profile = "low_hardness"
    elif "MEDHARDNESS" in upper or "MED_HARDNESS" in upper:
        water_profile = "medium_hardness"
    elif "HIGHHARDNESS" in upper or "HIGH_HARDNESS" in upper:
        water_profile = "high_hardness"
    elif "LOWTDS" in upper:
        water_profile = "low_tds"

    return {
        "wave_pdf_name": pdf_name,
        "process_type": process,
        "wave_case_key": _stable_id(pdf_name, process, prefix="wave"),
        "membrane_model_hint": membrane_model,
        "membrane_family_hint": membrane_family,
        "water_profile_hint": water_profile,
        "pass_count_hint": pass_count,
        "stage_count_hint": stage_count,
        "filename_recovery_candidates": "|".join(str(int(x)) if x.is_integer() else str(x) for x in recoveries),
        "target_recovery_pct_hint": target_recovery,
        "temperature_c_hint": temperature,
        "flow_factor_pct_hint": flow_factor_pct,
        "is_stress_case": bool("STRESS" in upper or "MAX" in upper or "MIN" in upper),
    }


def _stable_split_from_pdf(pdf_name: str) -> str:
    digest = hashlib.sha1(pdf_name.encode("utf-8", errors="ignore")).hexdigest()
    return "holdout" if int(digest[:8], 16) % 10 in {0, 1} else "train"


def normalize_raw_row(row: Mapping[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for canonical, aliases in AQUANOVA_RAW_COLUMN_ALIASES.items():
        value = None
        for alias in aliases:
            if alias in row and row[alias] not in (None, ""):
                value = row[alias]
                break
        out[canonical] = _blank_to_none(value)
    for key in (
        "aquanova_feed_tds_mgL", "aquanova_temperature_c", "aquanova_target_recovery_pct",
        "aquanova_result_recovery_pct", "aquanova_feed_pressure_bar", "aquanova_permeate_flow_m3h",
        "aquanova_permeate_tds_mgL", "aquanova_brine_tds_mgL", "aquanova_sec_kwh_m3",
    ):
        out[key] = _to_float(out.get(key))
    out["_raw_process_norm"] = _norm_token(out.get("aquanova_process"))
    out["_raw_membrane_norm"] = _norm_token(out.get("aquanova_membrane_model"))
    return out


def _score_raw_match(wave_row: Mapping[str, Any], raw: Mapping[str, Any]) -> float:
    score = 0.0
    process = _norm_token(wave_row.get("process_type"))
    raw_process = str(raw.get("_raw_process_norm") or "")
    if process and (process == raw_process or process in raw_process or raw_process in process):
        score += 0.35
    elif process in {"ro", "nf"} and "ro_nf" in raw_process:
        score += 0.25

    mem = _norm_token(wave_row.get("membrane_model_hint") or wave_row.get("membrane_family_hint"))
    raw_mem = str(raw.get("_raw_membrane_norm") or "")
    if mem and raw_mem:
        if mem in raw_mem or raw_mem in mem:
            score += 0.35
        elif wave_row.get("membrane_family_hint") and str(wave_row.get("membrane_family_hint")) in raw_mem:
            score += 0.18

    wave_rec = _to_float(wave_row.get("target_recovery_pct_hint"))
    raw_rec = _to_float(raw.get("aquanova_target_recovery_pct"))
    if wave_rec is not None and raw_rec is not None:
        delta = abs(wave_rec - raw_rec)
        if delta <= 1.0:
            score += 0.18
        elif delta <= 5.0:
            score += 0.10

    wave_temp = _to_float(wave_row.get("temperature_c_hint"))
    raw_temp = _to_float(raw.get("aquanova_temperature_c"))
    if wave_temp is not None and raw_temp is not None:
        delta = abs(wave_temp - raw_temp)
        if delta <= 1.0:
            score += 0.12
        elif delta <= 5.0:
            score += 0.05
    return score


def _best_raw_match(wave_row: Mapping[str, Any], raw_rows: Sequence[Mapping[str, Any]]) -> tuple[dict[str, Any] | None, float]:
    best: dict[str, Any] | None = None
    best_score = 0.0
    for raw in raw_rows:
        score = _score_raw_match(wave_row, raw)
        if score > best_score:
            best = dict(raw)
            best_score = score
    if best is None or best_score < 0.55:
        return None, best_score
    return best, best_score


def _add_error_columns(row: dict[str, Any]) -> None:
    for label, wave_col, aqua_col in TARGETS_FOR_ERROR_COLUMNS:
        wave = _to_float(row.get(wave_col))
        aqua = _to_float(row.get(aqua_col))
        abs_col = f"error_{label}_abs"
        pct_col = f"error_{label}_pct"
        if wave is None or aqua is None:
            row[abs_col] = None
            row[pct_col] = None
            continue
        diff = aqua - wave
        row[abs_col] = diff
        if abs(wave) > 1e-12:
            row[pct_col] = diff / wave * 100.0
        else:
            row[pct_col] = None


def build_pair_rows(
    corpus_records: Iterable[Mapping[str, Any]],
    *,
    feature_splits: Mapping[str, str] | None = None,
    aquanova_raw_rows: Sequence[Mapping[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Build target-first pair rows from WAVE corpus records.

    If ``aquanova_raw_rows`` is omitted, rows are emitted as skeletons with all
    AquaNova raw columns empty.  If raw rows are supplied, V88 performs a
    conservative fuzzy match and computes error columns only for matched rows.
    """
    splits = dict(feature_splits or {})
    raw_rows = [normalize_raw_row(r) for r in (aquanova_raw_rows or [])]
    rows: list[dict[str, Any]] = []
    for record in corpus_records:
        meta = infer_wave_case_metadata(record)
        pdf_name = str(meta.get("wave_pdf_name") or "")
        process = str(meta.get("process_type") or "unknown")
        row: dict[str, Any] = {
            "pair_id": _stable_id(pdf_name, process, prefix="pair"),
            "split": splits.get(pdf_name) or _stable_split_from_pdf(pdf_name),
            **meta,
            "wave_parse_warnings": "|".join(str(x) for x in record.get("parse_warnings", []) if str(x)),
            "wave_design_warnings": "|".join(str(x) for x in record.get("design_warnings", []) if str(x)),
        }
        target_count = 0
        for out_key, metric_key in WAVE_TARGET_METRIC_MAP:
            value = _metric(record, metric_key)
            value = _blank_to_none(value)
            row[out_key] = value
            if _to_float(value) is not None:
                target_count += 1
        row["wave_target_value_count"] = target_count

        raw, match_score = _best_raw_match(row, raw_rows) if raw_rows else (None, 0.0)
        row["aquanova_match_score"] = round(match_score, 4)
        if raw:
            for key in AQUANOVA_RAW_COLUMN_ALIASES:
                row[key] = raw.get(key)
            row["pair_status"] = "paired"
        else:
            for key in AQUANOVA_RAW_COLUMN_ALIASES:
                row[key] = None
            row["pair_status"] = "needs_aquanova_raw" if target_count > 0 else "wave_insufficient"
        _add_error_columns(row)
        rows.append(row)
    return rows


def write_pair_table(rows: Sequence[Mapping[str, Any]], path: str | Path) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    ordered_prefixes = (
        "pair_id", "split", "pair_status", "wave_pdf_name", "process_type", "wave_case_key",
        "membrane_", "water_", "pass_", "stage_", "target_", "temperature_", "flow_",
        "is_stress", "filename_", "wave_", "aquanova_", "error_",
    )
    keys: list[str] = []
    seen: set[str] = set()
    for prefix in ordered_prefixes:
        for row in rows:
            for key in row:
                if key in seen:
                    continue
                if key == prefix or key.startswith(prefix):
                    keys.append(key)
                    seen.add(key)
    for row in rows:
        for key in row:
            if key not in seen:
                keys.append(key)
                seen.add(key)
    with out.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        for row in rows:
            writer.writerow(dict(row))
    return out


def write_pair_json(rows: Sequence[Mapping[str, Any]], path: str | Path, *, source_corpus: str | None = None) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "aquanova.wave_calibration_pairs.v88",
        "source_corpus": source_corpus,
        "summary": summarize_pair_rows(rows),
        "records": list(rows),
    }
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return out


def write_pair_markdown(rows: Sequence[Mapping[str, Any]], path: str | Path) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    summary = summarize_pair_rows(rows)
    lines = [
        "# V88 WAVE ↔ AquaNova Calibration Pair Table",
        "",
        f"- Rows: `{summary['row_count']}`",
        f"- Pair status: `{summary['pair_status_counts']}`",
        f"- Process counts: `{summary['process_counts']}`",
        f"- Split counts: `{summary['split_counts']}`",
        f"- Ready target rows: `{summary['ready_target_row_count']}`",
        "",
        "| Process | PDF | Status | WAVE target values | Split |",
        "|---|---|---:|---:|---|",
    ]
    for row in rows[:80]:
        lines.append(
            f"| {row.get('process_type','')} | `{row.get('wave_pdf_name','')}` | {row.get('pair_status','')} | "
            f"{row.get('wave_target_value_count','')} | {row.get('split','')} |"
        )
    if len(rows) > 80:
        lines.append(f"\n... truncated preview: {len(rows) - 80} more row(s).")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


def summarize_pair_rows(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    process_counts: dict[str, int] = {}
    status_counts: dict[str, int] = {}
    split_counts: dict[str, int] = {}
    ready = 0
    paired = 0
    for row in rows:
        process = str(row.get("process_type") or "unknown")
        status = str(row.get("pair_status") or "unknown")
        split = str(row.get("split") or "unknown")
        process_counts[process] = process_counts.get(process, 0) + 1
        status_counts[status] = status_counts.get(status, 0) + 1
        split_counts[split] = split_counts.get(split, 0) + 1
        if int(_to_float(row.get("wave_target_value_count")) or 0) > 0:
            ready += 1
        if status == "paired":
            paired += 1
    return {
        "schema_version": "aquanova.wave_calibration_pairs.v88",
        "row_count": len(rows),
        "process_counts": dict(sorted(process_counts.items())),
        "pair_status_counts": dict(sorted(status_counts.items())),
        "split_counts": dict(sorted(split_counts.items())),
        "ready_target_row_count": ready,
        "paired_row_count": paired,
        "needs_aquanova_raw_count": status_counts.get("needs_aquanova_raw", 0),
        "wave_insufficient_count": status_counts.get("wave_insufficient", 0),
    }
