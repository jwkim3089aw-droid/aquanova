"""V98 scope-aware bounded residual correction fitting.

V91/V92 intentionally learned absolute target surfaces.  V96 showed that a
promoted absolute surface can be dangerous at runtime: a well-aligned HRRO case
was double-corrected and pressure/TDS predictions jumped outside the physical
regime.  V98 switches the next calibration artifact to a safer form:

    corrected = raw + bounded_residual_delta(raw, operating_context)

The key differences from V91/V92 are:

* fit residuals, not absolute WAVE targets;
* split by process/metric/regime before fitting;
* skip already-aligned quality metrics instead of trying to improve noise;
* export runtime-disabled scope-aware residual layer candidates only.

The module uses only the Python standard library so it can run inside the
existing AquaNova virtual environment.
"""
from __future__ import annotations

import csv
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median
from typing import Any, Iterable, Mapping, Sequence

SCHEMA_VERSION = "aquanova.wave_scope_residual_fit.v98"
LAYER_SCHEMA_VERSION = "aquanova.wave_scope_residual_layer.v98"

RESIDUAL_PROMOTABLE_METRICS: set[str] = {
    "feed_pressure",
    "product_tds",
    "final_concentrate_tds",
    "specific_energy",
}

DEFAULT_THRESHOLDS: dict[str, float | int] = {
    "min_total_n": 3,
    "min_train_n": 2,
    "min_holdout_n_for_promote": 2,
    "already_aligned_mean_abs_error_pct": 3.0,
    "min_total_improvement_pct": 5.0,
    "min_holdout_improvement_pct": 5.0,
    "max_corrected_mean_abs_error_pct": 25.0,
}

# Metric-level hard bounds for residual corrections.  These are intentionally
# much tighter than V97 absolute prediction guards because V98 predicts a delta.
DEFAULT_RESIDUAL_GUARDS: dict[str, dict[str, float]] = {
    "feed_pressure": {"max_abs_delta": 4.0, "max_rel_delta": 0.35, "min_ratio": 0.55, "max_ratio": 1.45},
    "product_tds": {"max_abs_delta": 20.0, "max_rel_delta": 0.45, "min_ratio": 0.55, "max_ratio": 1.65},
    "final_concentrate_tds": {"max_abs_delta": 6000.0, "max_rel_delta": 0.65, "min_ratio": 0.55, "max_ratio": 1.80},
    "specific_energy": {"max_abs_delta": 0.25, "max_rel_delta": 0.40, "min_ratio": 0.55, "max_ratio": 1.70},
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


def _boolish(value: Any) -> bool:
    return _s(value).strip().lower() in {"1", "true", "yes", "y", "on", "enabled"}


def _r(value: Any, digits: int = 6) -> float | None:
    f = _to_float(value)
    return round(f, digits) if f is not None else None


def _mean(values: Iterable[float]) -> float | None:
    vals = [float(v) for v in values if math.isfinite(float(v))]
    return sum(vals) / len(vals) if vals else None


def _error_pct(pred: float, actual: float) -> float | None:
    if abs(actual) < 1e-12:
        return None
    return (pred - actual) / actual * 100.0


def _mae_pct(preds: Sequence[float], ys: Sequence[float]) -> float | None:
    vals: list[float] = []
    for p, y in zip(preds, ys):
        ep = _error_pct(p, y)
        if ep is not None and math.isfinite(ep):
            vals.append(abs(ep))
    return _mean(vals)


def read_metric_rows(path: str | Path) -> list[dict[str, Any]]:
    p = Path(path)
    if p.suffix.lower() == ".json":
        payload = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(payload, Mapping) and isinstance(payload.get("metric_rows"), list):
            return [dict(x) for x in payload["metric_rows"] if isinstance(x, Mapping)]
        if isinstance(payload, list):
            return [dict(x) for x in payload if isinstance(x, Mapping)]
    with p.open("r", encoding="utf-8-sig", newline="") as f:
        return [dict(row) for row in csv.DictReader(f)]


def write_csv_rows(rows: Sequence[Mapping[str, Any]], path: str | Path, fieldnames: Sequence[str] | None = None) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        keys: list[str] = []
        seen: set[str] = set()
        for row in rows:
            for key in row:
                if isinstance(row.get(key), (dict, list)):
                    continue
                if key not in seen:
                    keys.append(key)
                    seen.add(key)
        fieldnames = keys
    with out.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(fieldnames), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            flat = {k: (json.dumps(v, ensure_ascii=False, sort_keys=True) if isinstance(v, (dict, list)) else v) for k, v in dict(row).items()}
            writer.writerow(flat)
    return out


def write_json(payload: Mapping[str, Any], path: str | Path) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return out


def _pdf_name(row: Mapping[str, Any]) -> str:
    return _s(row.get("wave_pdf_name") or row.get("pdf_name") or row.get("case_id"))


def _target_recovery(row: Mapping[str, Any]) -> float | None:
    return _to_float(row.get("target_recovery_pct_hint")) or _to_float(row.get("wave_system_recovery_pct")) or _to_float(row.get("wave_pass_recovery_pct"))


def _pass_count(row: Mapping[str, Any]) -> int:
    val = _to_float(row.get("pass_count_hint"))
    return int(round(val)) if val is not None else 1


def classify_regime(row: Mapping[str, Any]) -> str:
    """Return a conservative process-specific regime label.

    Regime labels are intentionally simple and based on fields already present
    in the V90 metric table.  They prevent one fitted surface from crossing
    from, for example, CCRO flow sweep cases into an already WAVE-aligned HRRO
    1.82 m3/h benchmark.
    """
    process = _norm(row.get("process_type")) or "unknown"
    name_n = _norm(_pdf_name(row))
    recovery = _target_recovery(row)
    feed = _to_float(row.get("wave_system_feed_flow_m3h"))
    product = _to_float(row.get("wave_system_product_flow_m3h"))
    pass_count = _pass_count(row)
    stress = _boolish(row.get("is_stress_case")) or "stress" in name_n

    if process == "ccro":
        if stress:
            return "ccro_stress"
        if pass_count >= 2 or "2pass" in name_n:
            return "ccro_2pass"
        if product is not None and 1.70 <= product <= 2.05 and recovery is not None and 88.0 <= recovery <= 92.0:
            return "ccro_small_1p82_r90_already_aligned"
        if any(tok in name_n for tok in ("f070", "f085", "f100", "f115", "f130")) and recovery is not None and 88.0 <= recovery <= 92.0:
            return "ccro_flow_sweep"
        if recovery is not None and recovery >= 93.0:
            return "ccro_high_recovery"
        if recovery is not None:
            return "ccro_recovery_sweep"
        if feed is not None:
            return "ccro_flow_unknown_recovery"
        return "ccro_generic"

    if process == "ro":
        if stress:
            return "ro_stress"
        if pass_count >= 2 or "2pass" in name_n or "multipass" in name_n:
            return "ro_multipass"
        stage_count = _to_float(row.get("stage_count_hint")) or 1.0
        if stage_count >= 2:
            return "ro_multistage"
        return "ro_singlepass"

    if process == "nf":
        if stress:
            return "nf_stress"
        return "nf_baseline_low_anchor"

    if process == "uf":
        return "uf_no_numeric_targets"
    return process or "unknown"


def _usable_rows(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        process = _norm(row.get("process_type"))
        metric = _norm(row.get("metric"))
        if metric not in RESIDUAL_PROMOTABLE_METRICS:
            continue
        wave = _to_float(row.get("wave_value"))
        raw = _to_float(row.get("aquanova_raw_value"))
        if wave is None or raw is None:
            continue
        if abs(raw) < 1e-12 and abs(wave) > 1e-12:
            continue
        item = dict(row)
        item["process_type"] = process
        item["metric"] = metric
        item["_wave"] = wave
        item["_raw"] = raw
        item["_delta"] = wave - raw
        item["_delta_ratio"] = (wave - raw) / raw if abs(raw) > 1e-12 else 0.0
        item["regime"] = classify_regime(item)
        out.append(item)
    return out


def _guarded_corrected(raw: float, delta_ratio: float, metric: str) -> tuple[float, str]:
    guard = DEFAULT_RESIDUAL_GUARDS.get(_norm(metric), {})
    wanted = raw * (1.0 + float(delta_ratio))
    min_ratio = guard.get("min_ratio")
    max_ratio = guard.get("max_ratio")
    max_abs_delta = guard.get("max_abs_delta")
    max_rel_delta = guard.get("max_rel_delta")

    low = -math.inf
    high = math.inf
    if min_ratio is not None:
        low = max(low, raw * float(min_ratio))
    if max_ratio is not None:
        high = min(high, raw * float(max_ratio))
    if max_abs_delta is not None:
        low = max(low, raw - float(max_abs_delta))
        high = min(high, raw + float(max_abs_delta))
    if max_rel_delta is not None:
        rel = abs(raw) * float(max_rel_delta)
        low = max(low, raw - rel)
        high = min(high, raw + rel)
    corrected = max(low, min(high, wanted))
    status = "bounded" if abs(corrected - wanted) > 1e-9 else "ok"
    if raw >= 0 and corrected < 0:
        corrected = raw
        status = "blocked_negative"
    return corrected, status


def _evaluate(rows: Sequence[Mapping[str, Any]], delta_ratio: float, metric: str) -> dict[str, Any]:
    raws = [float(r["_raw"]) for r in rows]
    waves = [float(r["_wave"]) for r in rows]
    raw_mae = _mae_pct(raws, waves)
    preds: list[float] = []
    bounded = 0
    for raw in raws:
        pred, status = _guarded_corrected(raw, delta_ratio, metric)
        preds.append(pred)
        if status != "ok":
            bounded += 1
    corr_mae = _mae_pct(preds, waves)
    improvement = None
    if raw_mae is not None and raw_mae > 1e-12 and corr_mae is not None:
        improvement = (raw_mae - corr_mae) / raw_mae * 100.0
    return {
        "n": len(rows),
        "raw_mean_abs_error_pct": _r(raw_mae),
        "corrected_mean_abs_error_pct": _r(corr_mae),
        "improvement_pct": _r(improvement),
        "bounded_prediction_count": bounded,
    }


def _thresholds(overrides: Mapping[str, Any] | None = None) -> dict[str, float | int]:
    out = dict(DEFAULT_THRESHOLDS)
    for k, v in dict(overrides or {}).items():
        if k in out and _to_float(v) is not None:
            out[k] = int(v) if isinstance(out[k], int) else float(v)
    return out


def _fit_group(rows: Sequence[Mapping[str, Any]], *, thresholds: Mapping[str, Any] | None = None) -> dict[str, Any]:
    thr = _thresholds(thresholds)
    process = _norm(rows[0].get("process_type"))
    metric = _norm(rows[0].get("metric"))
    regime = _s(rows[0].get("regime"))
    train = [r for r in rows if _norm(r.get("split")) == "train"]
    holdout = [r for r in rows if _norm(r.get("split")) == "holdout"]
    if not train:
        train = list(rows)
    ratios = [float(r["_delta_ratio"]) for r in train if math.isfinite(float(r["_delta_ratio"]))]
    delta_ratio = median(ratios) if ratios else 0.0
    all_eval = _evaluate(rows, delta_ratio, metric)
    train_eval = _evaluate(train, delta_ratio, metric)
    holdout_eval = _evaluate(holdout, delta_ratio, metric) if holdout else {"n": 0, "raw_mean_abs_error_pct": None, "corrected_mean_abs_error_pct": None, "improvement_pct": None, "bounded_prediction_count": 0}

    flags: list[str] = []
    total_n = len(rows)
    train_n = len(train)
    holdout_n = len(holdout)
    raw_total = _to_float(all_eval.get("raw_mean_abs_error_pct"))
    corr_total = _to_float(all_eval.get("corrected_mean_abs_error_pct"))
    total_imp = _to_float(all_eval.get("improvement_pct"))
    holdout_corr = _to_float(holdout_eval.get("corrected_mean_abs_error_pct"))
    holdout_imp = _to_float(holdout_eval.get("improvement_pct"))

    if total_n < int(thr["min_total_n"]):
        flags.append("total_n_below_gate")
    if train_n < int(thr["min_train_n"]):
        flags.append("train_n_below_gate")
    if raw_total is not None and raw_total <= float(thr["already_aligned_mean_abs_error_pct"]):
        flags.append("already_aligned_skip")
    if metric in {"product_tds", "final_concentrate_tds"} and "already_aligned" in regime:
        flags.append("upstream_wave_quality_alignment_scope")
    if process == "nf":
        flags.append("nf_anchor_count_too_low")
    if total_imp is None or total_imp < float(thr["min_total_improvement_pct"]):
        flags.append("total_improvement_below_gate")
    if corr_total is None or corr_total > float(thr["max_corrected_mean_abs_error_pct"]):
        flags.append("total_corrected_error_above_gate")
    if holdout_n >= int(thr["min_holdout_n_for_promote"]):
        if holdout_imp is None or holdout_imp < float(thr["min_holdout_improvement_pct"]):
            flags.append("holdout_improvement_below_gate")
        if holdout_corr is None or holdout_corr > float(thr["max_corrected_mean_abs_error_pct"]):
            flags.append("holdout_corrected_error_above_gate")
    else:
        flags.append("holdout_n_below_runtime_gate")

    decision = "promote_candidate" if not flags else "review_or_skip"
    model_id = f"v98_{process}_{metric}_{regime}_median_residual_ratio"
    return {
        "schema_version": SCHEMA_VERSION,
        "model_id": model_id,
        "process_type": process,
        "metric": metric,
        "regime": regime,
        "model_type": "median_bounded_residual_ratio",
        "decision": decision,
        "flags": "|".join(flags),
        "total_n": total_n,
        "train_n": train_n,
        "holdout_n": holdout_n,
        "delta_ratio_median": _r(delta_ratio, 9),
        "delta_pct_median": _r(delta_ratio * 100.0, 6),
        "raw_mean_abs_error_pct": all_eval.get("raw_mean_abs_error_pct"),
        "corrected_mean_abs_error_pct": all_eval.get("corrected_mean_abs_error_pct"),
        "improvement_pct": all_eval.get("improvement_pct"),
        "train_raw_mean_abs_error_pct": train_eval.get("raw_mean_abs_error_pct"),
        "train_corrected_mean_abs_error_pct": train_eval.get("corrected_mean_abs_error_pct"),
        "train_improvement_pct": train_eval.get("improvement_pct"),
        "holdout_raw_mean_abs_error_pct": holdout_eval.get("raw_mean_abs_error_pct"),
        "holdout_corrected_mean_abs_error_pct": holdout_eval.get("corrected_mean_abs_error_pct"),
        "holdout_improvement_pct": holdout_eval.get("improvement_pct"),
        "bounded_prediction_count": int(all_eval.get("bounded_prediction_count") or 0),
        "model_payload": {
            "prediction_mode": "bounded_residual_delta",
            "model_type": "median_bounded_residual_ratio",
            "delta_ratio": delta_ratio,
            "residual_guards": DEFAULT_RESIDUAL_GUARDS.get(metric, {}),
            "regime": regime,
            "notes": "V98 predicts raw + bounded residual. It is not an absolute target predictor.",
        },
        "runtime_enabled": False,
    }


def build_scope_residual_fit(rows: Sequence[Mapping[str, Any]], *, thresholds: Mapping[str, Any] | None = None) -> dict[str, Any]:
    usable = _usable_rows(rows)
    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in usable:
        groups[(_norm(row.get("process_type")), _norm(row.get("metric")), _s(row.get("regime")))] .append(row)
    models = [_fit_group(items, thresholds=thresholds) for _, items in sorted(groups.items())]
    promoted = [m for m in models if m.get("decision") == "promote_candidate"]
    rejected = [m for m in models if m.get("decision") != "promote_candidate"]
    layer = {
        "schema_version": LAYER_SCHEMA_VERSION,
        "runtime_enabled_by_default": False,
        "summary": {
            "schema_version": SCHEMA_VERSION,
            "input_row_count": len(rows),
            "usable_row_count": len(usable),
            "scope_group_count": len(groups),
            "model_count": len(models),
            "promote_candidate_count": len(promoted),
            "review_or_skip_count": len(rejected),
            "process_counts": dict(Counter(_norm(r.get("process_type")) for r in usable)),
            "metric_counts": dict(Counter(_norm(r.get("metric")) for r in usable)),
            "regime_counts": dict(Counter(_s(r.get("regime")) for r in usable)),
            "thresholds": _thresholds(thresholds),
        },
        "models": [
            {
                "model_id": m["model_id"],
                "process_type": m["process_type"],
                "metric": m["metric"],
                "regime": m["regime"],
                "model_type": m["model_type"],
                "model_payload": m["model_payload"],
                "runtime_enabled": False,
                "nonnegative_output": True,
                "total_n": m["total_n"],
                "train_n": m["train_n"],
                "holdout_n": m["holdout_n"],
                "corrected_mean_abs_error_pct": m["corrected_mean_abs_error_pct"],
                "holdout_corrected_mean_abs_error_pct": m["holdout_corrected_mean_abs_error_pct"],
            }
            for m in promoted
        ],
        "decisions": models,
    }
    return layer


def apply_v98_residual_model(model: Mapping[str, Any], raw_value: Any) -> dict[str, Any]:
    raw = _to_float(raw_value)
    if raw is None:
        return {"status": "invalid_raw_value", "raw_value": None, "corrected_value": None}
    payload = dict(model.get("model_payload") or model)
    if _s(payload.get("prediction_mode")) != "bounded_residual_delta":
        return {"status": "unsupported_model", "raw_value": raw, "corrected_value": raw}
    delta_ratio = float(payload.get("delta_ratio", 0.0) or 0.0)
    metric = _norm(model.get("metric") or payload.get("metric"))
    corrected, bound_status = _guarded_corrected(raw, delta_ratio, metric)
    return {
        "status": "corrected" if bound_status in {"ok", "bounded"} else bound_status,
        "bound_status": bound_status,
        "raw_value": raw,
        "corrected_value": corrected,
        "delta_ratio": delta_ratio,
    }


def write_markdown_report(layer: Mapping[str, Any], path: str | Path) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    summary = dict(layer.get("summary") or {})
    decisions = list(layer.get("decisions") or [])
    promoted = [d for d in decisions if d.get("decision") == "promote_candidate"]
    review = [d for d in decisions if d.get("decision") != "promote_candidate"]
    lines: list[str] = []
    lines.append("# V98 Scope-Aware Bounded Residual Correction Fit")
    lines.append("")
    lines.append(f"- Schema: `{summary.get('schema_version', '')}`")
    lines.append(f"- Input rows: {summary.get('input_row_count', 0)}")
    lines.append(f"- Usable rows: {summary.get('usable_row_count', 0)}")
    lines.append(f"- Scope groups: {summary.get('scope_group_count', 0)}")
    lines.append(f"- Promote candidates: {summary.get('promote_candidate_count', 0)}")
    lines.append(f"- Review/skip: {summary.get('review_or_skip_count', 0)}")
    lines.append("")
    lines.append("## Promote Candidates")
    lines.append("")
    lines.append("| Process | Metric | Regime | N | Train | Holdout | Raw abs % | Corrected abs % | Improvement % | Delta % |")
    lines.append("|---|---|---|---:|---:|---:|---:|---:|---:|---:|")
    for row in promoted:
        lines.append(
            f"| {row.get('process_type')} | `{row.get('metric')}` | `{row.get('regime')}` | {row.get('total_n')} | {row.get('train_n')} | {row.get('holdout_n')} | {row.get('raw_mean_abs_error_pct')} | {row.get('corrected_mean_abs_error_pct')} | {row.get('improvement_pct')} | {row.get('delta_pct_median')} |"
        )
    lines.append("")
    lines.append("## Review / Skipped")
    lines.append("")
    lines.append("| Process | Metric | Regime | Decision Flags | N | Raw abs % | Corrected abs % |")
    lines.append("|---|---|---|---|---:|---:|---:|")
    for row in review:
        lines.append(
            f"| {row.get('process_type')} | `{row.get('metric')}` | `{row.get('regime')}` | `{row.get('flags')}` | {row.get('total_n')} | {row.get('raw_mean_abs_error_pct')} | {row.get('corrected_mean_abs_error_pct')} |"
        )
    lines.append("")
    lines.append("## Notes")
    lines.append("")
    lines.append("V98 exports runtime-disabled residual candidates only. It deliberately avoids absolute-target prediction and uses process/metric/regime scope labels so already aligned HRRO quality values are not double-corrected.")
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


def write_v98_outputs(layer: Mapping[str, Any], base_output: str | Path) -> dict[str, str]:
    base = Path(base_output)
    outputs = {
        "decisions_csv": str(base.with_name(base.stem + "_v98_scope_residual_decisions.csv")),
        "scope_layer_json": str(base.with_name(base.stem + "_v98_scope_residual_layer.json")),
        "summary_json": str(base.with_name(base.stem + "_v98_scope_residual_summary.json")),
        "markdown": str(base.with_name(base.stem + "_v98_scope_residual_report.md")),
    }
    write_csv_rows(list(layer.get("decisions") or []), outputs["decisions_csv"])
    write_json({
        "schema_version": layer.get("schema_version"),
        "runtime_enabled_by_default": layer.get("runtime_enabled_by_default"),
        "summary": layer.get("summary"),
        "models": layer.get("models") or [],
    }, outputs["scope_layer_json"])
    write_json({"summary": layer.get("summary")}, outputs["summary_json"])
    write_markdown_report(layer, outputs["markdown"])
    return outputs


def fit_file(metric_errors: str | Path, *, output_base: str | Path | None = None, thresholds: Mapping[str, Any] | None = None) -> dict[str, Any]:
    rows = read_metric_rows(metric_errors)
    layer = build_scope_residual_fit(rows, thresholds=thresholds)
    base = Path(output_base) if output_base else Path(metric_errors)
    outputs = write_v98_outputs(layer, base)
    return {"layer": layer, "outputs": outputs, "summary": layer.get("summary")}
