"""V93 WAVE correction-layer shadow validation.

V92 promotes safe correction candidates into a portable correction-layer JSON,
but intentionally keeps runtime disabled. V93 validates that layer in shadow
mode against the already-paired WAVE/AquaNova dataset. It computes what each
promoted model *would* have done, without mutating engine outputs.

The intended workflow is:

    V89 filled pairs CSV + V92 correction layer JSON
        -> V93 shadow metric table / summary / report

Only after a correction passes this shadow check should a later patch wire it
into the simulation engine as an explicit opt-in runtime correction.
"""
from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from app.services.simulation.calibration.wave_correction_layer import apply_correction

SCHEMA_VERSION = "aquanova.wave_shadow_validation.v93"

METRIC_COLUMNS: dict[str, tuple[str, str]] = {
    "feed_pressure": ("wave_pass_feed_pressure_bar", "aquanova_feed_pressure_bar"),
    "product_tds": ("wave_system_product_tds_mgL", "aquanova_permeate_tds_mgL"),
    "final_concentrate_tds": ("wave_pass_final_concentrate_tds_mgL", "aquanova_brine_tds_mgL"),
    "specific_energy": ("wave_system_specific_energy_kwh_m3", "aquanova_sec_kwh_m3"),
}

DEFAULT_SHADOW_THRESHOLDS: dict[str, float | int] = {
    "min_total_n": 5,
    "min_holdout_n": 2,
    "min_holdout_improvement_pct": 10.0,
    "max_holdout_corrected_mean_abs_error_pct": 30.0,
    "max_total_corrected_mean_abs_error_pct": 30.0,
    "max_negative_regression_pct_points": 2.0,
}


def _s(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    return str(value)


def _norm(value: Any) -> str:
    return "_".join("".join(ch.lower() if ch.isalnum() else " " for ch in _s(value)).split())


def _to_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        f = float(value)
        return f if math.isfinite(f) else None
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "null", "true", "false"}:
        return None
    text = text.replace(",", "")
    for token in ("m3/h", "m³/h", "mg/L", "mg/l", "bar", "%", "LMH", "kWh/m3", "kWh/m³", "cycles", "min"):
        text = text.replace(token, "")
    try:
        f = float(text.strip())
    except ValueError:
        return None
    return f if math.isfinite(f) else None


def _r(value: Any, digits: int = 6) -> float | None:
    f = _to_float(value)
    return round(f, digits) if f is not None else None


def _pct_error(predicted: float, target: float) -> float:
    denom = abs(target) if abs(target) > 1e-12 else 1.0
    return (predicted - target) / denom * 100.0


def _abs_pct_error(predicted: float, target: float) -> float:
    return abs(_pct_error(predicted, target))


def read_csv_rows(path: str | Path) -> list[dict[str, Any]]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as f:
        return [dict(row) for row in csv.DictReader(f)]


def read_layer(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("models"), list):
        raise ValueError(f"Unsupported correction-layer JSON: {path}")
    return payload


def _model_key_set(layer: Mapping[str, Any]) -> set[tuple[str, str]]:
    out: set[tuple[str, str]] = set()
    for model in layer.get("models") or []:
        if isinstance(model, Mapping):
            out.add((_norm(model.get("process_type")), _norm(model.get("metric"))))
    return out


def build_shadow_metric_rows(
    pair_rows: Sequence[Mapping[str, Any]],
    layer: Mapping[str, Any],
    *,
    include_unmodeled: bool = False,
) -> list[dict[str, Any]]:
    """Return one shadow-validation row per process/metric target.

    ``include_unmodeled`` can be used for diagnostics, but default output is
    intentionally limited to promoted V92 models so the summary measures only
    the candidate correction layer.
    """
    model_keys = _model_key_set(layer)
    metric_rows: list[dict[str, Any]] = []
    for row in pair_rows:
        if _norm(row.get("pair_status")) != "paired":
            continue
        process = _norm(row.get("process_type") or row.get("aquanova_process"))
        if not process:
            continue
        split = _norm(row.get("split")) or "unknown"
        for metric, (wave_col, raw_col) in METRIC_COLUMNS.items():
            has_model = (process, metric) in model_keys
            if not include_unmodeled and not has_model:
                continue
            wave = _to_float(row.get(wave_col))
            raw = _to_float(row.get(raw_col))
            if wave is None or raw is None:
                continue
            shadow = apply_correction(layer, process, metric, raw, row, force=True)
            corrected = _to_float(shadow.get("corrected_value"))
            status = _s(shadow.get("status")) or "unknown"
            if corrected is None:
                corrected = raw
                status = status or "invalid_correction"
            raw_abs = _abs_pct_error(raw, wave)
            corr_abs = _abs_pct_error(corrected, wave)
            improvement = raw_abs - corr_abs
            improvement_pct = (improvement / raw_abs * 100.0) if raw_abs > 1e-12 else 0.0
            metric_rows.append({
                "schema_version": SCHEMA_VERSION,
                "pair_id": row.get("pair_id", ""),
                "split": split,
                "process_type": process,
                "metric": metric,
                "wave_pdf_name": row.get("wave_pdf_name", ""),
                "wave_value": _r(wave),
                "aquanova_raw_value": _r(raw),
                "shadow_corrected_value": _r(corrected),
                "raw_error_pct": _r(_pct_error(raw, wave)),
                "raw_abs_error_pct": _r(raw_abs),
                "shadow_error_pct": _r(_pct_error(corrected, wave)),
                "shadow_abs_error_pct": _r(corr_abs),
                "shadow_improvement_pct": _r(improvement_pct),
                "shadow_abs_error_delta_pct_points": _r(corr_abs - raw_abs),
                "shadow_status": status,
                "model_id": shadow.get("model_id", ""),
                "has_model": bool(has_model),
                "runtime_enabled_in_layer": _model_runtime_enabled(layer, process, metric),
                "wave_case_key": row.get("wave_case_key", ""),
                "is_stress_case": row.get("is_stress_case", ""),
                "target_recovery_pct_hint": row.get("target_recovery_pct_hint", ""),
                "wave_pass_average_flux_lmh": row.get("wave_pass_average_flux_lmh", ""),
                "wave_ccro_pf_feed_ratio_pct": row.get("wave_ccro_pf_feed_ratio_pct", ""),
            })
    return metric_rows


def _model_runtime_enabled(layer: Mapping[str, Any], process_type: str, metric: str) -> bool:
    process = _norm(process_type)
    metric_n = _norm(metric)
    for model in layer.get("models") or []:
        if isinstance(model, Mapping) and _norm(model.get("process_type")) == process and _norm(model.get("metric")) == metric_n:
            return bool(model.get("runtime_enabled"))
    return False


def _mean(values: Iterable[float]) -> float | None:
    vals = [float(v) for v in values if math.isfinite(float(v))]
    if not vals:
        return None
    return sum(vals) / len(vals)


def _group_key(row: Mapping[str, Any], fields: Sequence[str]) -> tuple[str, ...]:
    return tuple(_s(row.get(f)) for f in fields)


def summarize_shadow_rows(
    metric_rows: Sequence[Mapping[str, Any]],
    *,
    thresholds: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    thr = dict(DEFAULT_SHADOW_THRESHOLDS)
    for key, value in dict(thresholds or {}).items():
        if key in thr:
            base = thr[key]
            thr[key] = int(value) if isinstance(base, int) else float(value)

    summary_rows: list[dict[str, Any]] = []
    groups: dict[tuple[str, str], list[Mapping[str, Any]]] = {}
    for row in metric_rows:
        groups.setdefault((_norm(row.get("process_type")), _norm(row.get("metric"))), []).append(row)

    passed = 0
    review = 0
    failed = 0
    for (process, metric), rows in sorted(groups.items()):
        all_raw = [_to_float(r.get("raw_abs_error_pct")) for r in rows]
        all_corr = [_to_float(r.get("shadow_abs_error_pct")) for r in rows]
        raw_mean = _mean(v for v in all_raw if v is not None)
        corr_mean = _mean(v for v in all_corr if v is not None)
        improvement_pct = ((raw_mean - corr_mean) / raw_mean * 100.0) if raw_mean and corr_mean is not None else None
        holdout = [r for r in rows if _norm(r.get("split")) == "holdout"]
        train = [r for r in rows if _norm(r.get("split")) == "train"]
        train_raw = _mean((_to_float(r.get("raw_abs_error_pct")) or 0.0) for r in train)
        train_corr = _mean((_to_float(r.get("shadow_abs_error_pct")) or 0.0) for r in train)
        hold_raw = _mean((_to_float(r.get("raw_abs_error_pct")) or 0.0) for r in holdout)
        hold_corr = _mean((_to_float(r.get("shadow_abs_error_pct")) or 0.0) for r in holdout)
        hold_improvement_pct = ((hold_raw - hold_corr) / hold_raw * 100.0) if hold_raw and hold_corr is not None else None
        train_improvement_pct = ((train_raw - train_corr) / train_raw * 100.0) if train_raw and train_corr is not None else None

        flags: list[str] = []
        if len(rows) < int(thr["min_total_n"]):
            flags.append("total_n_below_gate")
        if len(holdout) < int(thr["min_holdout_n"]):
            flags.append("holdout_n_below_gate")
        if hold_improvement_pct is None or hold_improvement_pct < float(thr["min_holdout_improvement_pct"]):
            flags.append("holdout_improvement_below_gate")
        if hold_corr is None or hold_corr > float(thr["max_holdout_corrected_mean_abs_error_pct"]):
            flags.append("holdout_corrected_error_above_gate")
        if corr_mean is None or corr_mean > float(thr["max_total_corrected_mean_abs_error_pct"]):
            flags.append("total_corrected_error_above_gate")
        if corr_mean is not None and raw_mean is not None and (corr_mean - raw_mean) > float(thr["max_negative_regression_pct_points"]):
            flags.append("total_negative_regression")
        if hold_corr is not None and hold_raw is not None and (hold_corr - hold_raw) > float(thr["max_negative_regression_pct_points"]):
            flags.append("holdout_negative_regression")

        if not flags:
            decision = "shadow_pass"
            passed += 1
        elif any("negative_regression" in f or "above_gate" in f for f in flags):
            decision = "shadow_fail"
            failed += 1
        else:
            decision = "shadow_review"
            review += 1
        model_ids = sorted({_s(r.get("model_id")) for r in rows if _s(r.get("model_id"))})
        summary_rows.append({
            "process_type": process,
            "metric": metric,
            "decision": decision,
            "flags": "|".join(flags),
            "row_count": len(rows),
            "train_n": len(train),
            "holdout_n": len(holdout),
            "raw_mean_abs_error_pct": _r(raw_mean),
            "shadow_mean_abs_error_pct": _r(corr_mean),
            "shadow_improvement_pct": _r(improvement_pct),
            "train_raw_mean_abs_error_pct": _r(train_raw),
            "train_shadow_mean_abs_error_pct": _r(train_corr),
            "train_shadow_improvement_pct": _r(train_improvement_pct),
            "holdout_raw_mean_abs_error_pct": _r(hold_raw),
            "holdout_shadow_mean_abs_error_pct": _r(hold_corr),
            "holdout_shadow_improvement_pct": _r(hold_improvement_pct),
            "model_ids": "|".join(model_ids),
        })

    raw_all = _mean((_to_float(r.get("raw_abs_error_pct")) or 0.0) for r in metric_rows)
    corr_all = _mean((_to_float(r.get("shadow_abs_error_pct")) or 0.0) for r in metric_rows)
    overall_improvement = ((raw_all - corr_all) / raw_all * 100.0) if raw_all and corr_all is not None else None
    return {
        "schema_version": SCHEMA_VERSION,
        "summary": {
            "schema_version": SCHEMA_VERSION,
            "metric_row_count": len(metric_rows),
            "process_metric_group_count": len(groups),
            "shadow_pass_count": passed,
            "shadow_review_count": review,
            "shadow_fail_count": failed,
            "raw_mean_abs_error_pct": _r(raw_all),
            "shadow_mean_abs_error_pct": _r(corr_all),
            "shadow_overall_improvement_pct": _r(overall_improvement),
            "thresholds": thr,
        },
        "summary_rows": summary_rows,
    }


def write_csv_rows(rows: Sequence[Mapping[str, Any]], path: str | Path, fieldnames: Sequence[str] | None = None) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        keys: list[str] = []
        seen: set[str] = set()
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


def write_markdown_report(payload: Mapping[str, Any], path: str | Path) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    summary = dict(payload.get("summary") or {})
    rows = list(payload.get("summary_rows") or [])
    lines: list[str] = []
    lines.append("# V93 WAVE Correction Layer Shadow Validation")
    lines.append("")
    lines.append(f"- Schema: `{summary.get('schema_version', '')}`")
    lines.append(f"- Shadow metric rows: {summary.get('metric_row_count', 0)}")
    lines.append(f"- Process/metric groups: {summary.get('process_metric_group_count', 0)}")
    lines.append(f"- Shadow pass/review/fail: {summary.get('shadow_pass_count', 0)} / {summary.get('shadow_review_count', 0)} / {summary.get('shadow_fail_count', 0)}")
    lines.append(f"- Raw mean abs error: {summary.get('raw_mean_abs_error_pct')}%")
    lines.append(f"- Shadow mean abs error: {summary.get('shadow_mean_abs_error_pct')}%")
    lines.append(f"- Overall improvement: {summary.get('shadow_overall_improvement_pct')}%")
    lines.append("")
    lines.append("## Process / Metric Results")
    lines.append("")
    lines.append("| Process | Metric | Decision | N | Holdout N | Raw abs % | Shadow abs % | Holdout raw abs % | Holdout shadow abs % | Holdout improve % | Flags |")
    lines.append("|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|")
    for row in rows:
        lines.append(
            "| {process_type} | `{metric}` | {decision} | {row_count} | {holdout_n} | {raw_mean_abs_error_pct} | {shadow_mean_abs_error_pct} | {holdout_raw_mean_abs_error_pct} | {holdout_shadow_mean_abs_error_pct} | {holdout_shadow_improvement_pct} | `{flags}` |".format(**row)
        )
    lines.append("")
    lines.append("## Notes")
    lines.append("")
    lines.append("V93 is a shadow validation only. It force-applies the V92 correction layer inside the validation table, but does not enable runtime correction in AquaNova.")
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


def write_v93_outputs(
    pair_rows: Sequence[Mapping[str, Any]],
    layer: Mapping[str, Any],
    base_output: str | Path,
    *,
    include_unmodeled: bool = False,
    thresholds: Mapping[str, Any] | None = None,
) -> dict[str, str]:
    metric_rows = build_shadow_metric_rows(pair_rows, layer, include_unmodeled=include_unmodeled)
    payload = summarize_shadow_rows(metric_rows, thresholds=thresholds)
    base = Path(base_output)
    outputs = {
        "shadow_rows_csv": str(base.with_name(base.stem + "_v93_shadow_rows.csv")),
        "summary_csv": str(base.with_name(base.stem + "_v93_shadow_summary.csv")),
        "summary_json": str(base.with_name(base.stem + "_v93_shadow_summary.json")),
        "markdown": str(base.with_name(base.stem + "_v93_shadow_report.md")),
    }
    write_csv_rows(metric_rows, outputs["shadow_rows_csv"])
    write_csv_rows(list(payload.get("summary_rows") or []), outputs["summary_csv"])
    write_json(payload, outputs["summary_json"])
    write_markdown_report(payload, outputs["markdown"])
    return outputs
