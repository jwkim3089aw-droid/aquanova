"""V92 WAVE calibration correction-layer promotion and runtime helpers.

V91 fits candidate correction surfaces. V92 adds a stricter holdout gate and
exports only safe, interpretable models into a portable correction-layer JSON.

This module is intentionally independent of pandas/numpy/scikit-learn and can
also be used by the AquaNova runtime later:

    corrected = apply_correction(layer, "ccro", "feed_pressure", raw, context)

V92 is still conservative. It creates a correction layer artifact and runtime
helper, but it does not automatically wire calibration into the main simulation
engine. That runtime integration should happen only after the promoted layer is
reviewed against holdout and expanded WAVE anchors.
"""
from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

SCHEMA_VERSION = "aquanova.wave_correction_layer.v92"

DEFAULT_PROMOTION_THRESHOLDS: dict[str, float | int] = {
    "min_train_n": 8,
    "min_holdout_n": 3,
    "min_holdout_improvement_pct": 20.0,
    "max_holdout_corrected_mean_abs_error_pct": 25.0,
    "max_train_corrected_mean_abs_error_pct": 25.0,
}

# Metrics that are calibration targets rather than exact conservation outputs.
# Recovery is usually a control target and should not be corrected by a learned
# surface unless a later patch explicitly models recovery control.
PROMOTABLE_METRICS: set[str] = {
    "feed_pressure",
    "product_tds",
    "final_concentrate_tds",
    "specific_energy",
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
    return _s(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _r(value: Any, digits: int = 6) -> float | None:
    f = _to_float(value)
    return round(f, digits) if f is not None else None


def _first_float(mapping: Mapping[str, Any], keys: Sequence[str], default: float | None = None) -> float | None:
    for key in keys:
        val = _to_float(mapping.get(key))
        if val is not None:
            return val
    return default


def _feature_context(raw_value: float, context: Mapping[str, Any] | None = None) -> dict[str, float]:
    ctx = dict(context or {})
    raw = float(raw_value)
    recovery_pct = _first_float(ctx, (
        "target_recovery_pct_hint",
        "target_recovery_pct",
        "recovery_pct",
        "wave_system_recovery_pct",
        "wave_pass_recovery_pct",
        "actual_recovery_pct",
    ), 0.0) or 0.0
    flux = _first_float(ctx, (
        "wave_pass_average_flux_lmh",
        "average_flux_lmh",
        "flux_lmh",
    ), 0.0) or 0.0
    temp = _first_float(ctx, (
        "temperature_c_hint",
        "temperature_c",
        "wave_system_temperature_c",
    ), 25.0) or 25.0
    pf_ratio_pct = _first_float(ctx, (
        "wave_ccro_pf_feed_ratio_pct",
        "pf_feed_ratio_pct",
        "pf_feed_ratio",
    ), 0.0) or 0.0
    pass_count = _first_float(ctx, ("pass_count_hint", "pass_count"), 1.0) or 1.0
    stage_count = _first_float(ctx, ("stage_count_hint", "stage_count"), 1.0) or 1.0
    recovery_frac = recovery_pct / 100.0 if recovery_pct > 1.5 else recovery_pct
    pf_ratio_frac = pf_ratio_pct / 100.0 if pf_ratio_pct > 5.0 else pf_ratio_pct
    out = {
        "aquanova_raw_value": raw,
        "recovery_frac": recovery_frac,
        "flux_lmh": flux,
        "temperature_c": temp,
        "pf_feed_ratio_frac": pf_ratio_frac,
        "pass_count": pass_count,
        "stage_count": stage_count,
        "is_stress_case_num": 1.0 if _boolish(ctx.get("is_stress_case")) else 0.0,
    }
    out["aquanova_raw_x_recovery_frac"] = raw * recovery_frac
    out["aquanova_raw_x_flux_lmh"] = raw * flux
    out["aquanova_raw_x_temperature_c"] = raw * temp
    out["aquanova_raw_x_pf_feed_ratio_frac"] = raw * pf_ratio_frac
    return out


def _predict_model(model_payload: Mapping[str, Any], raw_value: float, context: Mapping[str, Any] | None = None) -> float:
    model_type = _s(model_payload.get("model_type"))
    raw = float(raw_value)
    if model_type == "identity":
        return raw
    if model_type == "scale_only":
        return raw * float(model_payload.get("scale_factor", 1.0))
    features = _feature_context(raw, context)
    feature_names = list(model_payload.get("feature_names") or [])
    stats = dict(model_payload.get("feature_stats") or {})
    coeff = dict(model_payload.get("coefficients") or {})
    pred = float(coeff.get("intercept", 0.0)) if bool(model_payload.get("intercept", True)) else 0.0
    for name in feature_names:
        val = float(features.get(name, 0.0))
        st = dict(stats.get(name) or {})
        mean = float(st.get("mean", 0.0))
        std = float(st.get("std", 1.0) or 1.0)
        pred += float(coeff.get(name, 0.0)) * ((val - mean) / std)
    return pred


def read_recommended_models(path: str | Path) -> list[dict[str, Any]]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(payload, Mapping) and isinstance(payload.get("models"), list):
        return [dict(x) for x in payload["models"] if isinstance(x, Mapping)]
    if isinstance(payload, list):
        return [dict(x) for x in payload if isinstance(x, Mapping)]
    raise ValueError(f"Unsupported V91 recommended model payload: {path}")


def _thresholds(overrides: Mapping[str, Any] | None = None) -> dict[str, float | int]:
    out = dict(DEFAULT_PROMOTION_THRESHOLDS)
    for key, value in dict(overrides or {}).items():
        if key in out:
            base = out[key]
            out[key] = int(value) if isinstance(base, int) else float(value)
    return out


def promotion_decision(model: Mapping[str, Any], *, thresholds: Mapping[str, Any] | None = None) -> dict[str, Any]:
    thr = _thresholds(thresholds)
    process = _norm(model.get("process_type")) or "unknown"
    metric = _norm(model.get("metric")) or "unknown"
    model_type = _s(model.get("model_type"))
    flags: list[str] = []

    if metric not in PROMOTABLE_METRICS:
        flags.append("metric_not_promotable")
    if _s(model.get("promotion_status")) != "promote_candidate":
        flags.append("v91_not_promote_candidate")
    if _s(model.get("promotion_flags")):
        flags.append("v91_review_flags")
    if model_type == "identity":
        flags.append("identity_model_not_runtime_correction")

    train_n = int(_to_float(model.get("train_n")) or 0)
    holdout_n = int(_to_float(model.get("holdout_n")) or 0)
    train_corr = _to_float(model.get("train_corrected_mean_abs_error_pct"))
    holdout_corr = _to_float(model.get("holdout_corrected_mean_abs_error_pct"))
    holdout_imp = _to_float(model.get("holdout_improvement_pct"))

    if train_n < int(thr["min_train_n"]):
        flags.append("train_n_below_gate")
    if holdout_n < int(thr["min_holdout_n"]):
        flags.append("holdout_n_below_gate")
    if holdout_imp is None or holdout_imp < float(thr["min_holdout_improvement_pct"]):
        flags.append("holdout_improvement_below_gate")
    if holdout_corr is None or holdout_corr > float(thr["max_holdout_corrected_mean_abs_error_pct"]):
        flags.append("holdout_error_above_gate")
    if train_corr is None or train_corr > float(thr["max_train_corrected_mean_abs_error_pct"]):
        flags.append("train_error_above_gate")

    status = "promoted" if not flags else "rejected"
    model_id = f"v92_{process}_{metric}_{model_type}"
    return {
        "model_id": model_id,
        "process_type": process,
        "metric": metric,
        "model_type": model_type,
        "decision": status,
        "rejection_flags": "|".join(flags),
        "train_n": train_n,
        "holdout_n": holdout_n,
        "train_corrected_mean_abs_error_pct": _r(train_corr),
        "holdout_corrected_mean_abs_error_pct": _r(holdout_corr),
        "holdout_improvement_pct": _r(holdout_imp),
        "v91_promotion_status": model.get("promotion_status", ""),
        "v91_promotion_flags": model.get("promotion_flags", ""),
        "model_payload": model.get("model_payload") or {},
    }


def build_v92_layer(models: Sequence[Mapping[str, Any]], *, thresholds: Mapping[str, Any] | None = None, enable_runtime_by_default: bool = False) -> dict[str, Any]:
    thr = _thresholds(thresholds)
    decisions = [promotion_decision(m, thresholds=thr) for m in models]
    promoted = [d for d in decisions if d.get("decision") == "promoted"]
    rejected = [d for d in decisions if d.get("decision") != "promoted"]
    layer_models: list[dict[str, Any]] = []
    for d in promoted:
        layer_models.append({
            "model_id": d["model_id"],
            "process_type": d["process_type"],
            "metric": d["metric"],
            "model_type": d["model_type"],
            "model_payload": d["model_payload"],
            "train_n": d["train_n"],
            "holdout_n": d["holdout_n"],
            "train_corrected_mean_abs_error_pct": d["train_corrected_mean_abs_error_pct"],
            "holdout_corrected_mean_abs_error_pct": d["holdout_corrected_mean_abs_error_pct"],
            "holdout_improvement_pct": d["holdout_improvement_pct"],
            "nonnegative_output": True,
            "runtime_enabled": bool(enable_runtime_by_default),
        })
    summary = {
        "schema_version": SCHEMA_VERSION,
        "input_model_count": len(models),
        "promoted_model_count": len(promoted),
        "rejected_model_count": len(rejected),
        "runtime_enabled_by_default": bool(enable_runtime_by_default),
        "thresholds": thr,
        "promoted_by_process_metric": [f"{m['process_type']}.{m['metric']}" for m in layer_models],
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "summary": summary,
        "thresholds": thr,
        "runtime_enabled_by_default": bool(enable_runtime_by_default),
        "models": layer_models,
        "decisions": decisions,
    }


def _find_model(layer: Mapping[str, Any], process_type: str, metric: str) -> Mapping[str, Any] | None:
    process = _norm(process_type)
    metric_n = _norm(metric)
    for model in layer.get("models") or []:
        if _norm(model.get("process_type")) == process and _norm(model.get("metric")) == metric_n:
            return model
    return None


def apply_correction(
    layer: Mapping[str, Any],
    process_type: str,
    metric: str,
    aquanova_raw_value: Any,
    context: Mapping[str, Any] | None = None,
    *,
    force: bool = False,
) -> dict[str, Any]:
    """Apply a promoted correction model to one AquaNova raw value.

    By default, V92 models are exported in shadow/off mode. Pass ``force=True``
    or set each model's ``runtime_enabled`` to true after review to apply it.
    """
    raw = _to_float(aquanova_raw_value)
    if raw is None:
        return {"status": "invalid_raw_value", "corrected_value": None, "raw_value": None, "model_id": ""}
    model = _find_model(layer, process_type, metric)
    if model is None:
        return {"status": "no_model", "corrected_value": raw, "raw_value": raw, "model_id": ""}
    if not force and not bool(model.get("runtime_enabled")):
        return {"status": "shadow_only", "corrected_value": raw, "raw_value": raw, "model_id": model.get("model_id", "")}
    pred = _predict_model(dict(model.get("model_payload") or {}), raw, context)
    if bool(model.get("nonnegative_output", True)) and pred < 0 and raw >= 0:
        return {"status": "blocked_negative_prediction", "corrected_value": raw, "raw_value": raw, "model_id": model.get("model_id", "")}
    return {
        "status": "corrected",
        "corrected_value": pred,
        "raw_value": raw,
        "model_id": model.get("model_id", ""),
        "process_type": _norm(process_type),
        "metric": _norm(metric),
    }


def write_csv_rows(rows: Sequence[Mapping[str, Any]], path: str | Path, fieldnames: Sequence[str] | None = None) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        keys: list[str] = []
        seen: set[str] = set()
        for row in rows:
            for key in row:
                if key == "model_payload":
                    continue
                if key not in seen:
                    keys.append(key)
                    seen.add(key)
        fieldnames = keys
    with out.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(fieldnames), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            r = dict(row)
            r.pop("model_payload", None)
            writer.writerow(r)
    return out


def write_json(payload: Mapping[str, Any], path: str | Path) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return out


def write_markdown_report(layer: Mapping[str, Any], path: str | Path) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    summary = dict(layer.get("summary") or {})
    decisions = list(layer.get("decisions") or [])
    promoted = [d for d in decisions if d.get("decision") == "promoted"]
    rejected = [d for d in decisions if d.get("decision") != "promoted"]
    lines: list[str] = []
    lines.append("# V92 WAVE Calibration Correction Layer Promotion")
    lines.append("")
    lines.append(f"- Schema: `{summary.get('schema_version', '')}`")
    lines.append(f"- Input V91 models: {summary.get('input_model_count', 0)}")
    lines.append(f"- Promoted models: {summary.get('promoted_model_count', 0)}")
    lines.append(f"- Rejected models: {summary.get('rejected_model_count', 0)}")
    lines.append(f"- Runtime enabled by default: {summary.get('runtime_enabled_by_default', False)}")
    lines.append("")
    lines.append("## Promoted Models")
    lines.append("")
    lines.append("| Process | Metric | Model | Train N | Holdout N | Train corrected abs % | Holdout corrected abs % | Holdout improve % |")
    lines.append("|---|---|---|---:|---:|---:|---:|---:|")
    for row in promoted:
        lines.append(
            "| {process_type} | `{metric}` | `{model_type}` | {train_n} | {holdout_n} | {train_corrected_mean_abs_error_pct} | {holdout_corrected_mean_abs_error_pct} | {holdout_improvement_pct} |".format(**row)
        )
    lines.append("")
    lines.append("## Rejected / Review Required")
    lines.append("")
    lines.append("| Process | Metric | Model | Decision | Flags | Train N | Holdout N | Holdout corrected abs % | Holdout improve % |")
    lines.append("|---|---|---|---|---|---:|---:|---:|---:|")
    for row in rejected:
        lines.append(
            "| {process_type} | `{metric}` | `{model_type}` | {decision} | `{rejection_flags}` | {train_n} | {holdout_n} | {holdout_corrected_mean_abs_error_pct} | {holdout_improvement_pct} |".format(**row)
        )
    lines.append("")
    lines.append("## Notes")
    lines.append("")
    lines.append("V92 exports a promoted correction-layer artifact, but keeps runtime application disabled by default. The next safe step is to run a shadow validation pass, then explicitly enable selected corrections inside the simulation engine.")
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


def write_v92_outputs(layer: Mapping[str, Any], base_output: str | Path) -> dict[str, str]:
    base = Path(base_output)
    outputs = {
        "decisions_csv": str(base.with_name(base.stem + "_v92_promotion_decisions.csv")),
        "correction_layer_json": str(base.with_name(base.stem + "_v92_correction_layer.json")),
        "summary_json": str(base.with_name(base.stem + "_v92_summary.json")),
        "markdown": str(base.with_name(base.stem + "_v92_promotion_report.md")),
    }
    write_csv_rows(list(layer.get("decisions") or []), outputs["decisions_csv"])
    write_json({
        "schema_version": SCHEMA_VERSION,
        "summary": layer.get("summary"),
        "thresholds": layer.get("thresholds"),
        "runtime_enabled_by_default": layer.get("runtime_enabled_by_default"),
        "models": layer.get("models") or [],
    }, outputs["correction_layer_json"])
    write_json({"summary": layer.get("summary")}, outputs["summary_json"])
    write_markdown_report(layer, outputs["markdown"])
    return outputs
