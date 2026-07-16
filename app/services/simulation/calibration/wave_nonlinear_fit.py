"""V91 interpretable nonlinear calibration fitting candidates.

V90 builds a long error table.  V91 turns that table into the first candidate
correction models for WAVE-like calibration:

    corrected_value = f(aquanova_raw_value, recovery, flux, temperature, ...)

The module deliberately avoids pandas, numpy, and scikit-learn.  It implements a
small ridge least-squares solver so it can run in the existing AquaNova venv.
V91 is still a fitting/reporting step; it does not apply corrections inside the
simulation engine.  That is reserved for the next correction-layer patch after
holdout review.
"""
from __future__ import annotations

import csv
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median
from typing import Any, Iterable, Mapping, Sequence

SCHEMA_VERSION = "aquanova.wave_nonlinear_fit.v91"

NUMERIC_FEATURE_CANDIDATES: tuple[str, ...] = (
    "aquanova_raw_value",
    "target_recovery_pct_hint",
    "wave_system_recovery_pct",
    "wave_pass_recovery_pct",
    "wave_pass_average_flux_lmh",
    "wave_system_feed_flow_m3h",
    "wave_system_product_flow_m3h",
    "wave_system_temperature_c",
    "temperature_c_hint",
    "wave_pass_ndp_bar",
    "wave_ccro_pf_feed_ratio_pct",
    "wave_ccro_total_cycles",
    "wave_ccro_system_volume_m3",
    "pass_count_hint",
    "stage_count_hint",
)

BASE_FEATURES: tuple[str, ...] = ("aquanova_raw_value",)
RECOVERY_FLUX_FEATURES: tuple[str, ...] = (
    "aquanova_raw_value",
    "recovery_frac",
    "flux_lmh",
    "aquanova_raw_x_recovery_frac",
    "aquanova_raw_x_flux_lmh",
)
OPERATING_FEATURES: tuple[str, ...] = (
    "aquanova_raw_value",
    "recovery_frac",
    "flux_lmh",
    "temperature_c",
    "pf_feed_ratio_frac",
    "pass_count",
    "stage_count",
    "is_stress_case_num",
    "aquanova_raw_x_recovery_frac",
    "aquanova_raw_x_flux_lmh",
    "aquanova_raw_x_temperature_c",
    "aquanova_raw_x_pf_feed_ratio_frac",
)


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


def engineered_features(row: Mapping[str, Any]) -> dict[str, float]:
    raw = _to_float(row.get("aquanova_raw_value"))
    recovery_pct = (
        _to_float(row.get("target_recovery_pct_hint"))
        or _to_float(row.get("wave_system_recovery_pct"))
        or _to_float(row.get("wave_pass_recovery_pct"))
        or 0.0
    )
    flux = _to_float(row.get("wave_pass_average_flux_lmh")) or 0.0
    temp = _to_float(row.get("temperature_c_hint")) or _to_float(row.get("wave_system_temperature_c")) or 25.0
    pf_ratio_pct = _to_float(row.get("wave_ccro_pf_feed_ratio_pct")) or 0.0
    pass_count = _to_float(row.get("pass_count_hint")) or 1.0
    stage_count = _to_float(row.get("stage_count_hint")) or 1.0
    raw = raw if raw is not None else 0.0
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
        "is_stress_case_num": 1.0 if _boolish(row.get("is_stress_case")) else 0.0,
    }
    out["aquanova_raw_x_recovery_frac"] = raw * recovery_frac
    out["aquanova_raw_x_flux_lmh"] = raw * flux
    out["aquanova_raw_x_temperature_c"] = raw * temp
    out["aquanova_raw_x_pf_feed_ratio_frac"] = raw * pf_ratio_frac
    return out


def usable_fit_rows(rows: Iterable[Mapping[str, Any]], *, include_severe: bool = True) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        wave = _to_float(row.get("wave_value"))
        raw = _to_float(row.get("aquanova_raw_value"))
        if wave is None or raw is None:
            continue
        if not include_severe and _norm(row.get("v90_error_class")) == "severe":
            continue
        if _norm(row.get("v90_error_class")) in {"missing", ""}:
            continue
        item = dict(row)
        item["_wave"] = wave
        item["_raw"] = raw
        item["_features"] = engineered_features(item)
        out.append(item)
    return out


def _mean(values: Sequence[float]) -> float | None:
    vals = [float(v) for v in values if math.isfinite(float(v))]
    return sum(vals) / len(vals) if vals else None


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
        return vals[lo]
    return vals[lo] * (hi - pos) + vals[hi] * (pos - lo)


def _error_pct(pred: float, actual: float) -> float | None:
    if actual == 0:
        return None
    return (pred - actual) / actual * 100.0


def _mae_pct(preds: Sequence[float], ys: Sequence[float]) -> float | None:
    vals: list[float] = []
    for p, y in zip(preds, ys):
        ep = _error_pct(p, y)
        if ep is not None and math.isfinite(ep):
            vals.append(abs(ep))
    return _mean(vals)


def _matrix_solve(a: list[list[float]], b: list[float]) -> list[float] | None:
    n = len(b)
    if n == 0:
        return []
    aug = [list(row) + [b[i]] for i, row in enumerate(a)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(aug[r][col]))
        if abs(aug[pivot][col]) < 1e-12:
            return None
        if pivot != col:
            aug[col], aug[pivot] = aug[pivot], aug[col]
        div = aug[col][col]
        aug[col] = [v / div for v in aug[col]]
        for r in range(n):
            if r == col:
                continue
            factor = aug[r][col]
            if factor == 0:
                continue
            aug[r] = [aug[r][c] - factor * aug[col][c] for c in range(n + 1)]
    return [aug[i][n] for i in range(n)]


def _standardize_training(rows: Sequence[Mapping[str, Any]], feature_names: Sequence[str]) -> dict[str, dict[str, float]]:
    stats: dict[str, dict[str, float]] = {}
    for name in feature_names:
        vals = [float(row["_features"].get(name, 0.0)) for row in rows]
        mu = _mean(vals) or 0.0
        var = _mean([(x - mu) ** 2 for x in vals]) or 0.0
        sd = math.sqrt(var)
        if sd < 1e-9:
            sd = 1.0
        stats[name] = {"mean": mu, "std": sd}
    return stats


def _design_row(row: Mapping[str, Any], feature_names: Sequence[str], stats: Mapping[str, Mapping[str, float]], *, intercept: bool = True) -> list[float]:
    feats = dict(row.get("_features") or engineered_features(row))
    x: list[float] = [1.0] if intercept else []
    for name in feature_names:
        val = float(feats.get(name, 0.0))
        st = stats.get(name, {})
        x.append((val - float(st.get("mean", 0.0))) / float(st.get("std", 1.0) or 1.0))
    return x


def _fit_ridge(rows: Sequence[Mapping[str, Any]], feature_names: Sequence[str], *, ridge_lambda: float = 1e-4, intercept: bool = True) -> dict[str, Any] | None:
    if not rows:
        return None
    stats = _standardize_training(rows, feature_names)
    x_rows = [_design_row(r, feature_names, stats, intercept=intercept) for r in rows]
    y = [float(r["_wave"]) for r in rows]
    p = len(x_rows[0])
    xtx = [[0.0 for _ in range(p)] for _ in range(p)]
    xty = [0.0 for _ in range(p)]
    for x, yy in zip(x_rows, y):
        for i in range(p):
            xty[i] += x[i] * yy
            for j in range(p):
                xtx[i][j] += x[i] * x[j]
    for i in range(p):
        if not (intercept and i == 0):
            xtx[i][i] += ridge_lambda
    beta = _matrix_solve(xtx, xty)
    if beta is None:
        return None
    coef_names = (["intercept"] if intercept else []) + list(feature_names)
    return {
        "feature_names": list(feature_names),
        "intercept": intercept,
        "feature_stats": stats,
        "coefficients": {name: beta[i] for i, name in enumerate(coef_names)},
    }


def _fit_scale_only(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any] | None:
    num = 0.0
    den = 0.0
    for r in rows:
        raw = float(r["_raw"])
        wave = float(r["_wave"])
        num += raw * wave
        den += raw * raw
    if abs(den) < 1e-12:
        return None
    return {"scale_factor": num / den}


def predict_row(model: Mapping[str, Any], row: Mapping[str, Any]) -> float:
    model_type = _s(model.get("model_type"))
    if model_type == "identity":
        return float(row["_raw"])
    if model_type == "scale_only":
        return float(row["_raw"]) * float(model.get("scale_factor", 1.0))
    features = list(model.get("feature_names") or [])
    stats = dict(model.get("feature_stats") or {})
    x = _design_row(row, features, stats, intercept=bool(model.get("intercept", True)))
    coef = dict(model.get("coefficients") or {})
    names = (["intercept"] if model.get("intercept", True) else []) + features
    return sum(float(coef.get(name, 0.0)) * x[i] for i, name in enumerate(names))


def _evaluate_model(model: Mapping[str, Any], rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {
            "n": 0,
            "raw_mean_abs_error_pct": None,
            "corrected_mean_abs_error_pct": None,
            "improvement_pct": None,
            "corrected_p90_abs_error_pct": None,
            "negative_prediction_count": 0,
        }
    raw_preds = [float(r["_raw"]) for r in rows]
    preds = [predict_row(model, r) for r in rows]
    ys = [float(r["_wave"]) for r in rows]
    raw_errs: list[float] = []
    corr_errs: list[float] = []
    neg_count = 0
    for raw, pred, y in zip(raw_preds, preds, ys):
        if pred < 0 and y >= 0:
            neg_count += 1
        ep_raw = _error_pct(raw, y)
        ep_corr = _error_pct(pred, y)
        if ep_raw is not None:
            raw_errs.append(abs(ep_raw))
        if ep_corr is not None:
            corr_errs.append(abs(ep_corr))
    raw_mean = _mean(raw_errs)
    corr_mean = _mean(corr_errs)
    improvement = None
    if raw_mean is not None and raw_mean > 1e-12 and corr_mean is not None:
        improvement = (raw_mean - corr_mean) / raw_mean * 100.0
    return {
        "n": len(rows),
        "raw_mean_abs_error_pct": _r(raw_mean),
        "corrected_mean_abs_error_pct": _r(corr_mean),
        "improvement_pct": _r(improvement),
        "corrected_median_abs_error_pct": _r(median(corr_errs)) if corr_errs else None,
        "corrected_p90_abs_error_pct": _r(_quantile(corr_errs, 0.90)),
        "corrected_max_abs_error_pct": _r(max(corr_errs)) if corr_errs else None,
        "negative_prediction_count": neg_count,
    }


def _candidate_defs(train_n: int) -> list[tuple[str, tuple[str, ...], str]]:
    out: list[tuple[str, tuple[str, ...], str]] = [("identity", tuple(), "no correction"), ("scale_only", tuple(), "raw*k")]
    if train_n >= 3:
        out.append(("affine_raw", BASE_FEATURES, "intercept + raw"))
    if train_n >= 10:
        out.append(("nonlinear_recovery_flux", RECOVERY_FLUX_FEATURES, "raw/recovery/flux interactions"))
    if train_n >= 18:
        out.append(("nonlinear_operating", OPERATING_FEATURES, "operating interactions"))
    return out


def fit_group_candidates(rows: Sequence[Mapping[str, Any]], *, process_type: str, metric: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    train = [r for r in rows if _norm(r.get("split")) == "train"]
    holdout = [r for r in rows if _norm(r.get("split")) == "holdout"]
    if len(train) < 2:
        train = list(rows)
        holdout = []
    candidates: list[dict[str, Any]] = []
    predictions: list[dict[str, Any]] = []
    for model_type, feature_names, description in _candidate_defs(len(train)):
        if model_type == "identity":
            model: dict[str, Any] = {
                "model_type": model_type,
                "description": description,
                "feature_names": [],
                "intercept": False,
            }
        elif model_type == "scale_only":
            fitted = _fit_scale_only(train)
            if fitted is None:
                continue
            model: dict[str, Any] = {
                "model_type": model_type,
                "description": description,
                "feature_names": [],
                "scale_factor": fitted["scale_factor"],
                "intercept": False,
            }
        else:
            fitted = _fit_ridge(train, feature_names, ridge_lambda=1e-3, intercept=True)
            if fitted is None:
                continue
            model = {
                "model_type": model_type,
                "description": description,
                **fitted,
            }
        train_eval = _evaluate_model(model, train)
        holdout_eval = _evaluate_model(model, holdout)
        complexity = 1 + len(feature_names)
        score = (train_eval.get("corrected_mean_abs_error_pct") or 999999.0) + 0.25 * complexity
        if holdout_eval.get("n", 0):
            # Holdout is not used as the only decision maker, but clearly unsafe
            # holdout behavior should push the candidate down.
            raw_h = holdout_eval.get("raw_mean_abs_error_pct")
            corr_h = holdout_eval.get("corrected_mean_abs_error_pct")
            if raw_h is not None and corr_h is not None and corr_h > raw_h * 1.25:
                score += (corr_h - raw_h) * 0.5
        if train_eval.get("negative_prediction_count", 0) or holdout_eval.get("negative_prediction_count", 0):
            score += 1000.0
        candidate = {
            "process_type": process_type,
            "metric": metric,
            "model_type": model_type,
            "description": description,
            "train_n": train_eval["n"],
            "holdout_n": holdout_eval["n"],
            "selection_score": _r(score),
            "train_raw_mean_abs_error_pct": train_eval.get("raw_mean_abs_error_pct"),
            "train_corrected_mean_abs_error_pct": train_eval.get("corrected_mean_abs_error_pct"),
            "train_improvement_pct": train_eval.get("improvement_pct"),
            "holdout_raw_mean_abs_error_pct": holdout_eval.get("raw_mean_abs_error_pct"),
            "holdout_corrected_mean_abs_error_pct": holdout_eval.get("corrected_mean_abs_error_pct"),
            "holdout_improvement_pct": holdout_eval.get("improvement_pct"),
            "holdout_corrected_p90_abs_error_pct": holdout_eval.get("corrected_p90_abs_error_pct"),
            "negative_prediction_count": int(train_eval.get("negative_prediction_count", 0)) + int(holdout_eval.get("negative_prediction_count", 0)),
            "feature_names": "|".join(model.get("feature_names") or []),
            "model_payload_json": json.dumps(model, ensure_ascii=False, sort_keys=True),
            "recommended": False,
            "promotion_status": "unselected",
            "promotion_flags": "",
        }
        candidates.append(candidate)
        for split_name, split_rows in (("train", train), ("holdout", holdout)):
            for r in split_rows:
                pred = predict_row(model, r)
                wave = float(r["_wave"])
                raw = float(r["_raw"])
                predictions.append({
                    "process_type": process_type,
                    "metric": metric,
                    "model_type": model_type,
                    "split": split_name,
                    "pair_id": r.get("pair_id", ""),
                    "wave_pdf_name": r.get("wave_pdf_name", ""),
                    "wave_value": _r(wave, 8),
                    "aquanova_raw_value": _r(raw, 8),
                    "corrected_value": _r(pred, 8),
                    "raw_error_pct": _r(_error_pct(raw, wave), 8),
                    "corrected_error_pct": _r(_error_pct(pred, wave), 8),
                    "v90_error_class": r.get("v90_error_class", ""),
                })
    if candidates:
        candidates.sort(key=lambda c: float(c.get("selection_score") or 999999.0))
        best = candidates[0]
        flags: list[str] = []
        if int(best.get("train_n") or 0) < 8:
            flags.append("insufficient_anchor_count")
        hi = best.get("holdout_improvement_pct")
        if hi is not None and float(hi) < 0:
            flags.append("holdout_regression")
        if best.get("model_type") == "identity":
            flags.append("no_correction_needed_or_safer")
        if int(best.get("negative_prediction_count") or 0) > 0:
            flags.append("negative_prediction_risk")
        best["recommended"] = True
        best["promotion_flags"] = "|".join(flags)
        best["promotion_status"] = "promote_candidate" if not flags else "review_required"
    return candidates, predictions


def build_v91_fit(rows: Sequence[Mapping[str, Any]], *, include_severe: bool = True) -> dict[str, Any]:
    usable = usable_fit_rows(rows, include_severe=include_severe)
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in usable:
        groups[(_norm(row.get("process_type")) or "unknown", _norm(row.get("metric")) or "unknown")].append(row)
    all_candidates: list[dict[str, Any]] = []
    all_predictions: list[dict[str, Any]] = []
    recommended: list[dict[str, Any]] = []
    skipped_groups: list[dict[str, Any]] = []
    for (process, metric), items in sorted(groups.items()):
        if len(items) < 2:
            skipped_groups.append({"process_type": process, "metric": metric, "reason": "too_few_rows", "row_count": len(items)})
            continue
        candidates, predictions = fit_group_candidates(items, process_type=process, metric=metric)
        if not candidates:
            skipped_groups.append({"process_type": process, "metric": metric, "reason": "no_candidate_fit", "row_count": len(items)})
            continue
        all_candidates.extend(candidates)
        all_predictions.extend(predictions)
        best = next((c for c in candidates if c.get("recommended") is True), candidates[0])
        payload = json.loads(best.get("model_payload_json") or "{}")
        recommended.append({
            "process_type": process,
            "metric": metric,
            "model_type": best.get("model_type"),
            "train_n": best.get("train_n"),
            "holdout_n": best.get("holdout_n"),
            "train_raw_mean_abs_error_pct": best.get("train_raw_mean_abs_error_pct"),
            "train_corrected_mean_abs_error_pct": best.get("train_corrected_mean_abs_error_pct"),
            "train_improvement_pct": best.get("train_improvement_pct"),
            "holdout_raw_mean_abs_error_pct": best.get("holdout_raw_mean_abs_error_pct"),
            "holdout_corrected_mean_abs_error_pct": best.get("holdout_corrected_mean_abs_error_pct"),
            "holdout_improvement_pct": best.get("holdout_improvement_pct"),
            "feature_names": best.get("feature_names"),
            "promotion_status": best.get("promotion_status"),
            "promotion_flags": best.get("promotion_flags"),
            "model_payload": payload,
        })
    summary = {
        "schema_version": SCHEMA_VERSION,
        "input_row_count": len(rows),
        "usable_fit_row_count": len(usable),
        "include_severe": bool(include_severe),
        "group_count": len(groups),
        "fitted_group_count": len(recommended),
        "candidate_count": len(all_candidates),
        "prediction_row_count": len(all_predictions),
        "skipped_group_count": len(skipped_groups),
        "process_counts": dict(Counter(_norm(r.get("process_type")) or "unknown" for r in usable)),
        "metric_counts": dict(Counter(_norm(r.get("metric")) or "unknown" for r in usable)),
    }
    return {
        "summary": summary,
        "candidate_rows": all_candidates,
        "prediction_rows": all_predictions,
        "recommended_models": recommended,
        "skipped_groups": skipped_groups,
    }


def write_markdown_report(payload: Mapping[str, Any], path: str | Path) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    summary = dict(payload.get("summary") or {})
    recommended = list(payload.get("recommended_models") or [])
    skipped = list(payload.get("skipped_groups") or [])
    lines: list[str] = []
    lines.append("# V91 Nonlinear Calibration Candidate Fit")
    lines.append("")
    lines.append(f"- Schema: `{summary.get('schema_version', '')}`")
    lines.append(f"- Input metric rows: {summary.get('input_row_count', 0)}")
    lines.append(f"- Usable fitting rows: {summary.get('usable_fit_row_count', 0)}")
    lines.append(f"- Fitted process/metric groups: {summary.get('fitted_group_count', 0)}")
    lines.append(f"- Candidate models: {summary.get('candidate_count', 0)}")
    lines.append(f"- Include severe rows: {summary.get('include_severe', False)}")
    lines.append("")
    lines.append("## Recommended Candidate by Process/Metric")
    lines.append("")
    lines.append("| Process | Metric | Model | Status | Flags | Train N | Holdout N | Train Raw Abs % | Train Corrected Abs % | Train Improve % | Holdout Raw Abs % | Holdout Corrected Abs % | Holdout Improve % | Features |")
    lines.append("|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|")
    for row in recommended:
        lines.append(
            "| {process_type} | `{metric}` | `{model_type}` | {promotion_status} | `{promotion_flags}` | {train_n} | {holdout_n} | {train_raw_mean_abs_error_pct} | {train_corrected_mean_abs_error_pct} | {train_improvement_pct} | {holdout_raw_mean_abs_error_pct} | {holdout_corrected_mean_abs_error_pct} | {holdout_improvement_pct} | `{feature_names}` |".format(**row)
        )
    if skipped:
        lines.append("")
        lines.append("## Skipped Groups")
        lines.append("")
        lines.append("| Process | Metric | Rows | Reason |")
        lines.append("|---|---|---:|---|")
        for row in skipped:
            lines.append("| {process_type} | `{metric}` | {row_count} | {reason} |".format(**row))
    lines.append("")
    lines.append("## Notes")
    lines.append("")
    lines.append("V91 fits candidate correction surfaces only. It does not yet enable these corrections in the AquaNova runtime. Review holdout behavior before promoting any model into a correction layer.")
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


def write_v91_outputs(payload: Mapping[str, Any], base_output: str | Path) -> dict[str, str]:
    base = Path(base_output)
    outputs = {
        "candidates_csv": str(base.with_name(base.stem + "_v91_model_candidates.csv")),
        "predictions_csv": str(base.with_name(base.stem + "_v91_prediction_rows.csv")),
        "recommended_json": str(base.with_name(base.stem + "_v91_recommended_models.json")),
        "summary_json": str(base.with_name(base.stem + "_v91_summary.json")),
        "markdown": str(base.with_name(base.stem + "_v91_fit_report.md")),
    }
    write_csv_rows(list(payload.get("candidate_rows") or []), outputs["candidates_csv"])
    write_csv_rows(list(payload.get("prediction_rows") or []), outputs["predictions_csv"])
    write_json({"schema_version": SCHEMA_VERSION, "models": payload.get("recommended_models") or []}, outputs["recommended_json"])
    write_json({"summary": payload.get("summary"), "skipped_groups": payload.get("skipped_groups")}, outputs["summary_json"])
    write_markdown_report(payload, outputs["markdown"])
    return outputs
