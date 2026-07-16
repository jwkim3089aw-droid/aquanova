"""V90 WAVE-vs-AquaNova error analysis for nonlinear calibration.

V89 creates a filled pair table where each usable WAVE anchor row has a matching
AquaNova raw result.  V90 converts that wide pair table into the first fitting
view:

* annotated wide rows with row-level quality flags
* metric-long error rows (one row per case/target metric)
* clean metric rows for the next nonlinear fitting stage
* process/metric summaries for train and holdout splits

This module is intentionally dependency-free so it can run inside the user's
existing AquaNova environment without requiring pandas/scikit-learn.
"""
from __future__ import annotations

import csv
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median
from typing import Any, Iterable, Mapping, MutableMapping, Sequence

ERROR_METRICS: tuple[dict[str, str], ...] = (
    {
        "metric": "feed_pressure",
        "unit": "bar",
        "wave_col": "wave_pass_feed_pressure_bar",
        "aquanova_col": "aquanova_feed_pressure_bar",
        "abs_col": "error_feed_pressure_abs",
        "pct_col": "error_feed_pressure_pct",
    },
    {
        "metric": "product_tds",
        "unit": "mg/L",
        "wave_col": "wave_system_product_tds_mgL",
        "aquanova_col": "aquanova_permeate_tds_mgL",
        "abs_col": "error_product_tds_abs",
        "pct_col": "error_product_tds_pct",
    },
    {
        "metric": "final_concentrate_tds",
        "unit": "mg/L",
        "wave_col": "wave_pass_final_concentrate_tds_mgL",
        "aquanova_col": "aquanova_brine_tds_mgL",
        "abs_col": "error_final_concentrate_tds_abs",
        "pct_col": "error_final_concentrate_tds_pct",
    },
    {
        "metric": "specific_energy",
        "unit": "kWh/m3",
        "wave_col": "wave_system_specific_energy_kwh_m3",
        "aquanova_col": "aquanova_sec_kwh_m3",
        "abs_col": "error_specific_energy_abs",
        "pct_col": "error_specific_energy_pct",
    },
    {
        "metric": "recovery",
        "unit": "%",
        "wave_col": "wave_system_recovery_pct",
        "aquanova_col": "aquanova_result_recovery_pct",
        "abs_col": "error_recovery_abs",
        "pct_col": "error_recovery_pct",
    },
)

FEATURE_COLUMNS: tuple[str, ...] = (
    "process_type",
    "split",
    "membrane_model_hint",
    "membrane_family_hint",
    "water_profile_hint",
    "pass_count_hint",
    "stage_count_hint",
    "target_recovery_pct_hint",
    "temperature_c_hint",
    "flow_factor_pct_hint",
    "is_stress_case",
    "wave_system_feed_flow_m3h",
    "wave_system_recovery_pct",
    "wave_system_net_recovery_pct",
    "wave_system_product_flow_m3h",
    "wave_system_temperature_c",
    "wave_pass_average_flux_lmh",
    "wave_pass_recovery_pct",
    "wave_pass_ndp_bar",
    "wave_ccro_pf_feed_ratio_pct",
    "wave_ccro_total_cycles",
    "wave_ccro_system_volume_m3",
    "wave_uf_net_product_flow_m3h",
    "wave_uf_recovery_pct",
)

# Thresholds are deliberately conservative.  V90 is not deleting data; it is
# marking rows/metric targets so V91 can choose strict/relaxed fitting views.
METRIC_THRESHOLDS: Mapping[str, Mapping[str, float]] = {
    "feed_pressure": {"warning_abs_pct": 25.0, "severe_abs_pct": 50.0},
    "product_tds": {"warning_abs_pct": 100.0, "severe_abs_pct": 500.0, "min_abs_for_pct_flag": 1.0},
    "final_concentrate_tds": {"warning_abs_pct": 30.0, "severe_abs_pct": 60.0},
    "specific_energy": {"warning_abs_pct": 35.0, "severe_abs_pct": 75.0},
    "recovery": {"warning_abs_pct": 1.0, "severe_abs_pct": 3.0},
}


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        f = float(value)
        return f if math.isfinite(f) else None
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "null"}:
        return None
    text = text.replace(",", "")
    for token in ("m3/h", "m³/h", "mg/L", "mg/l", "bar", "%", "LMH", "kWh/m3", "kWh/m³", "cycles", "min"):
        text = text.replace(token, "")
    try:
        out = float(text.strip())
    except ValueError:
        return None
    return out if math.isfinite(out) else None


def _r(value: Any, digits: int = 6) -> float | None:
    f = _to_float(value)
    if f is None:
        return None
    return round(f, digits)


def _s(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    return str(value)


def _norm(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", _s(value).lower()).strip("_")


def read_csv_rows(path: str | Path) -> list[dict[str, Any]]:
    p = Path(path)
    with p.open("r", encoding="utf-8-sig", newline="") as f:
        return [dict(row) for row in csv.DictReader(f)]


def read_pair_rows(path: str | Path) -> list[dict[str, Any]]:
    p = Path(path)
    if p.suffix.lower() == ".csv":
        return read_csv_rows(p)
    if p.suffix.lower() == ".json":
        payload = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(payload, Mapping) and isinstance(payload.get("records"), list):
            return [dict(x) for x in payload["records"] if isinstance(x, Mapping)]
        if isinstance(payload, list):
            return [dict(x) for x in payload if isinstance(x, Mapping)]
    raise ValueError(f"Unsupported V89 input: {p}")


def write_csv_rows(rows: Sequence[Mapping[str, Any]], path: str | Path, fieldnames: Sequence[str] | None = None) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    keys: list[str] = []
    seen: set[str] = set()
    if fieldnames is None:
        for row in rows:
            for key in row:
                if key not in seen:
                    keys.append(key)
                    seen.add(key)
        fieldnames = keys
    with out.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(fieldnames), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(dict(row))
    return out


def write_json(payload: Mapping[str, Any], path: str | Path) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return out


def classify_metric_error(metric: str, abs_error: float | None, pct_error: float | None) -> tuple[str, list[str]]:
    """Classify a single metric target as clean/warn/severe/missing.

    The percent denominator can be tiny for product TDS, so V90 combines percent
    with absolute error for that metric.  This prevents a harmless 0.02 mg/L
    difference from becoming a fake outlier when WAVE product TDS is near zero.
    """
    if abs_error is None and pct_error is None:
        return "missing", ["missing_error"]
    abs_pct = abs(pct_error) if pct_error is not None else None
    abs_abs = abs(abs_error) if abs_error is not None else None
    thresholds = METRIC_THRESHOLDS.get(metric, {})
    severe = thresholds.get("severe_abs_pct", 999999.0)
    warning = thresholds.get("warning_abs_pct", 999999.0)
    min_abs_for_pct_flag = thresholds.get("min_abs_for_pct_flag", 0.0)
    flags: list[str] = []
    if abs_pct is None:
        return "missing", ["missing_pct_error"]
    pct_flag_allowed = abs_abs is None or abs_abs >= min_abs_for_pct_flag
    if pct_flag_allowed and abs_pct > severe:
        flags.append(f"{metric}_severe_pct_error")
        return "severe", flags
    if pct_flag_allowed and abs_pct > warning:
        flags.append(f"{metric}_warning_pct_error")
        return "warn", flags
    return "clean", flags


def metric_long_rows(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        pair_status = _norm(row.get("pair_status"))
        process = _norm(row.get("process_type")) or "unknown"
        if pair_status != "paired":
            continue
        for spec in ERROR_METRICS:
            metric = spec["metric"]
            wave_value = _to_float(row.get(spec["wave_col"]))
            aquanova_value = _to_float(row.get(spec["aquanova_col"]))
            abs_error = _to_float(row.get(spec["abs_col"]))
            pct_error = _to_float(row.get(spec["pct_col"]))
            if wave_value is None or aquanova_value is None or (abs_error is None and pct_error is None):
                continue
            cls, flags = classify_metric_error(metric, abs_error, pct_error)
            fit_eligible = cls in {"clean", "warn"}
            # UF currently has no numeric pressure/TDS/SEC targets in the V89
            # pair table.  If a future UF metric is added, it will pass here.
            entry: dict[str, Any] = {
                "pair_id": row.get("pair_id", ""),
                "split": row.get("split", ""),
                "process_type": process,
                "metric": metric,
                "unit": spec["unit"],
                "wave_pdf_name": row.get("wave_pdf_name", ""),
                "wave_value": round(wave_value, 8),
                "aquanova_raw_value": round(aquanova_value, 8),
                "error_abs": _r(abs_error, 8),
                "error_pct": _r(pct_error, 8),
                "abs_error_pct": round(abs(pct_error), 8) if pct_error is not None else None,
                "v90_error_class": cls,
                "v90_metric_flags": "|".join(flags),
                "v90_fit_eligible": bool(fit_eligible),
            }
            for feature in FEATURE_COLUMNS:
                entry[feature] = row.get(feature, "")
            out.append(entry)
    return out


def annotate_pair_rows(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    long_rows = metric_long_rows(rows)
    by_pair: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for item in long_rows:
        by_pair[_s(item.get("pair_id"))].append(item)

    out: list[dict[str, Any]] = []
    for row in rows:
        pair_id = _s(row.get("pair_id"))
        metrics = by_pair.get(pair_id, [])
        class_counts = Counter(_s(x.get("v90_error_class")) for x in metrics)
        flags: list[str] = []
        for x in metrics:
            flags.extend([f for f in _s(x.get("v90_metric_flags")).split("|") if f])
        process = _norm(row.get("process_type")) or "unknown"
        pair_status = _norm(row.get("pair_status"))
        if pair_status != "paired":
            row_class = "not_paired"
        elif not metrics:
            row_class = "no_numeric_error_targets"
        elif class_counts.get("severe", 0):
            row_class = "has_severe_error"
        elif class_counts.get("warn", 0):
            row_class = "has_warning_error"
        else:
            row_class = "clean"
        new = dict(row)
        new.update({
            "v90_process_group": process,
            "v90_numeric_metric_count": len(metrics),
            "v90_clean_metric_count": class_counts.get("clean", 0),
            "v90_warning_metric_count": class_counts.get("warn", 0),
            "v90_severe_metric_count": class_counts.get("severe", 0),
            "v90_row_error_class": row_class,
            "v90_row_flags": "|".join(sorted(set(flags))),
            "v90_row_fit_eligible": bool(pair_status == "paired" and metrics and row_class != "has_severe_error"),
        })
        out.append(new)
    return out


def _safe_mean(values: Sequence[float]) -> float | None:
    vals = [float(v) for v in values if math.isfinite(float(v))]
    if not vals:
        return None
    return sum(vals) / len(vals)


def _quantile(values: Sequence[float], q: float) -> float | None:
    vals = sorted(float(v) for v in values if math.isfinite(float(v)))
    if not vals:
        return None
    if len(vals) == 1:
        return vals[0]
    pos = (len(vals) - 1) * q
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return vals[int(pos)]
    return vals[lo] * (hi - pos) + vals[hi] * (pos - lo)


def summarize_metric_rows(metric_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for row in metric_rows:
        groups[(_s(row.get("process_type")), _s(row.get("metric")), _s(row.get("split")) or "all")].append(row)
        groups[(_s(row.get("process_type")), _s(row.get("metric")), "all")].append(row)
    out: list[dict[str, Any]] = []
    for (process, metric, split), items in sorted(groups.items()):
        pct_values = [_to_float(x.get("error_pct")) for x in items]
        pct_values = [x for x in pct_values if x is not None]
        abs_pct_values = [abs(x) for x in pct_values]
        abs_values = [_to_float(x.get("error_abs")) for x in items]
        abs_values = [x for x in abs_values if x is not None]
        cls_counts = Counter(_s(x.get("v90_error_class")) for x in items)
        fit_count = sum(1 for x in items if _s(x.get("v90_fit_eligible")).lower() in {"true", "1", "yes"} or x.get("v90_fit_eligible") is True)
        out.append({
            "process_type": process,
            "metric": metric,
            "split": split,
            "row_count": len(items),
            "fit_eligible_count": fit_count,
            "clean_count": cls_counts.get("clean", 0),
            "warning_count": cls_counts.get("warn", 0),
            "severe_count": cls_counts.get("severe", 0),
            "mean_error_pct": _r(_safe_mean(pct_values), 6),
            "median_error_pct": _r(median(pct_values), 6) if pct_values else None,
            "mean_abs_error_pct": _r(_safe_mean(abs_pct_values), 6),
            "p90_abs_error_pct": _r(_quantile(abs_pct_values, 0.90), 6),
            "max_abs_error_pct": _r(max(abs_pct_values), 6) if abs_pct_values else None,
            "mean_abs_error": _r(_safe_mean([abs(x) for x in abs_values]), 6),
        })
    return out


def top_error_rows(metric_rows: Sequence[Mapping[str, Any]], limit: int = 10) -> list[dict[str, Any]]:
    sortable = []
    for row in metric_rows:
        pct = _to_float(row.get("abs_error_pct"))
        if pct is None:
            continue
        sortable.append((pct, row))
    sortable.sort(key=lambda x: x[0], reverse=True)
    out: list[dict[str, Any]] = []
    for pct, row in sortable[:limit]:
        out.append({
            "process_type": row.get("process_type", ""),
            "metric": row.get("metric", ""),
            "split": row.get("split", ""),
            "wave_pdf_name": row.get("wave_pdf_name", ""),
            "wave_value": row.get("wave_value"),
            "aquanova_raw_value": row.get("aquanova_raw_value"),
            "error_pct": row.get("error_pct"),
            "abs_error_pct": pct,
            "v90_error_class": row.get("v90_error_class", ""),
        })
    return out


def build_v90_analysis(rows: Sequence[Mapping[str, Any]], *, top_n: int = 15) -> dict[str, Any]:
    annotated = annotate_pair_rows(rows)
    metric_rows = metric_long_rows(rows)
    clean_metric_rows = [row for row in metric_rows if row.get("v90_fit_eligible") is True]
    summary_rows = summarize_metric_rows(metric_rows)

    summary = {
        "schema_version": "aquanova.wave_error_analysis.v90",
        "row_count": len(rows),
        "annotated_row_count": len(annotated),
        "metric_error_row_count": len(metric_rows),
        "clean_metric_error_row_count": len(clean_metric_rows),
        "process_counts": dict(Counter(_norm(r.get("process_type")) or "unknown" for r in rows)),
        "pair_status_counts": dict(Counter(_norm(r.get("pair_status")) or "unknown" for r in rows)),
        "row_error_class_counts": dict(Counter(_s(r.get("v90_row_error_class")) for r in annotated)),
        "metric_error_class_counts": dict(Counter(_s(r.get("v90_error_class")) for r in metric_rows)),
        "summary_row_count": len(summary_rows),
        "top_error_count": min(top_n, len(metric_rows)),
    }
    return {
        "summary": summary,
        "annotated_rows": annotated,
        "metric_rows": metric_rows,
        "clean_metric_rows": clean_metric_rows,
        "summary_rows": summary_rows,
        "top_errors": top_error_rows(metric_rows, limit=top_n),
    }


def write_markdown_report(analysis: Mapping[str, Any], path: str | Path) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    summary = dict(analysis.get("summary") or {})
    summary_rows = list(analysis.get("summary_rows") or [])
    top_errors = list(analysis.get("top_errors") or [])
    lines: list[str] = []
    lines.append("# V90 WAVE vs AquaNova Error Analysis")
    lines.append("")
    lines.append(f"- Schema: `{summary.get('schema_version', '')}`")
    lines.append(f"- Pair rows: {summary.get('row_count', 0)}")
    lines.append(f"- Metric error rows: {summary.get('metric_error_row_count', 0)}")
    lines.append(f"- Clean metric rows for V91: {summary.get('clean_metric_error_row_count', 0)}")
    lines.append(f"- Process counts: {summary.get('process_counts', {})}")
    lines.append(f"- Row error classes: {summary.get('row_error_class_counts', {})}")
    lines.append(f"- Metric error classes: {summary.get('metric_error_class_counts', {})}")
    lines.append("")
    lines.append("## Process/Metric Summary")
    lines.append("")
    lines.append("| Process | Metric | Split | N | Fit N | Mean % | Median % | Mean Abs % | P90 Abs % | Max Abs % | Severe |")
    lines.append("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for row in summary_rows:
        if row.get("split") not in {"all", "train", "holdout"}:
            continue
        lines.append(
            "| {process_type} | `{metric}` | {split} | {row_count} | {fit_eligible_count} | {mean_error_pct} | {median_error_pct} | {mean_abs_error_pct} | {p90_abs_error_pct} | {max_abs_error_pct} | {severe_count} |".format(**row)
        )
    lines.append("")
    lines.append("## Top Absolute Percent Errors")
    lines.append("")
    lines.append("| Process | Metric | Split | PDF | WAVE | AquaNova raw | Error % | Class |")
    lines.append("|---|---|---|---|---:|---:|---:|---|")
    for row in top_errors:
        lines.append(
            "| {process_type} | `{metric}` | {split} | {wave_pdf_name} | {wave_value} | {aquanova_raw_value} | {error_pct} | {v90_error_class} |".format(**row)
        )
    lines.append("")
    lines.append("## Notes")
    lines.append("")
    lines.append("V90 does not apply correction. It only classifies error surfaces and prepares a clean metric-long view for V91 nonlinear fitting.")
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


def write_v90_outputs(analysis: Mapping[str, Any], base_output: str | Path) -> dict[str, str]:
    base = Path(base_output)
    outputs = {
        "annotated_csv": str(base.with_name(base.stem + "_v90_error_rows.csv")),
        "metric_csv": str(base.with_name(base.stem + "_v90_metric_errors.csv")),
        "clean_metric_csv": str(base.with_name(base.stem + "_v90_clean_metric_errors.csv")),
        "summary_csv": str(base.with_name(base.stem + "_v90_summary.csv")),
        "summary_json": str(base.with_name(base.stem + "_v90_summary.json")),
        "markdown": str(base.with_name(base.stem + "_v90_error_analysis.md")),
    }
    write_csv_rows(list(analysis.get("annotated_rows") or []), outputs["annotated_csv"])
    write_csv_rows(list(analysis.get("metric_rows") or []), outputs["metric_csv"])
    write_csv_rows(list(analysis.get("clean_metric_rows") or []), outputs["clean_metric_csv"])
    write_csv_rows(list(analysis.get("summary_rows") or []), outputs["summary_csv"])
    write_json({"summary": analysis.get("summary"), "top_errors": analysis.get("top_errors")}, outputs["summary_json"])
    write_markdown_report(analysis, outputs["markdown"])
    return outputs
