#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import math
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


def _project_root() -> Path:
    cwd = Path.cwd().resolve()
    if (cwd / "scripts" / "wave_records" / "results").exists():
        return cwd
    here = Path(__file__).resolve()
    root = here.parents[2]
    if (root / "scripts" / "wave_records").exists():
        return root
    return cwd


def _latest_file(directory: Path, pattern: str) -> Path:
    files = sorted(directory.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        raise SystemExit(f"No file matching {pattern} under {directory}")
    return files[0]


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for row in rows:
            w.writerow(row)


def _f(value: Any, default: float | None = None) -> float | None:
    try:
        if value is None:
            return default
        s = str(value).strip()
        if not s or s.lower() in {"nan", "none", "null"}:
            return default
        v = float(s)
        return v if math.isfinite(v) else default
    except Exception:
        return default


def _near(value: Any, target: float, tol: float = 0.03) -> bool:
    v = _f(value)
    if v is None:
        return False
    return abs(v - target) <= tol


def _name(row: dict[str, Any]) -> str:
    return str(row.get("wave_pdf_name") or row.get("pdf_name") or "")


def _classify_regime(row: dict[str, Any]) -> str:
    proc = str(row.get("process_type") or row.get("process") or "").lower()
    name = _name(row)

    if proc == "ccro":
        pass_count = _f(row.get("pass_count_hint"))
        if pass_count == 2 or "2PASS" in name.upper() or re.search(r"_P1R\d+", name, re.I):
            return "ccro_2pass"

        # Meeting/LG flux/TDS stress runs are intentionally isolated.
        if "FLUX_P" in name:
            return "ccro_product_flux_push"
        if re.search(r"TDS(?:0450|1000|1500|2000)", name):
            return "ccro_tds_sweep_unverified"
        if re.search(r"_FR(?:270|300)(?:_|\.pdf)", name):
            return "ccro_fr_stress"

        rec = _f(row.get("target_recovery_pct_hint") or row.get("wave_system_recovery_pct"))
        pf = _f(row.get("wave_ccro_pf_feed_ratio_pct"))
        product_flow = _f(row.get("wave_system_product_flow_m3h"))

        if product_flow is not None and rec is not None:
            if abs(product_flow - 1.82) <= 0.08 and abs(rec - 90.0) <= 0.5 and (pf is None or pf <= 150.0):
                return "ccro_small_1p82_r90_already_aligned"

        # WAVE campaign recovery sweep: F100 and varying R values, one-pass.
        if re.search(r"_F100_R(?:75|80|85|90|95)\.pdf", name, re.I) or re.search(r"_R(?:75|80|85|90|95)\.pdf", name, re.I):
            return "ccro_recovery_sweep"

        # WAVE campaign flow sweep: F070/F085/F115/F130 etc.
        if re.search(r"_F(?:070|085|115|130)_R", name, re.I):
            return "ccro_flow_sweep"

        return "ccro_other"

    if proc == "ro":
        stage_count = _f(row.get("stage_count_hint"))
        if (stage_count is not None and stage_count >= 2) or re.search(r"(2Stage|3Stage|4Stage|5Stage|Multistage|MM_)", name, re.I):
            return "ro_multistage"
        if "2P_" in name or "2Pass" in name:
            return "ro_2pass"
        return "ro_standard"

    if proc == "nf":
        return "nf_reference"

    return proc or "unknown"


def _apply_residual(raw: float, model: dict[str, Any]) -> tuple[float, bool, str]:
    payload = model.get("model_payload") or {}
    guards = payload.get("residual_guards") or {}

    delta_ratio = _f(payload.get("delta_ratio"), 0.0) or 0.0
    max_abs_delta = abs(_f(guards.get("max_abs_delta"), float("inf")) or float("inf"))
    max_rel_delta = abs(_f(guards.get("max_rel_delta"), float("inf")) or float("inf"))
    min_ratio = _f(guards.get("min_ratio"), 0.0) or 0.0
    max_ratio = _f(guards.get("max_ratio"), float("inf")) or float("inf")

    proposed = raw * (1.0 + delta_ratio)
    lower = raw * min_ratio
    upper = raw * max_ratio
    bounded = min(max(proposed, lower), upper)

    delta = bounded - raw
    clipped = False
    reason = "ok"

    if math.isfinite(max_rel_delta):
        rel_cap = abs(raw) * max_rel_delta
        if abs(delta) > rel_cap:
            delta = math.copysign(rel_cap, delta)
            clipped = True
            reason = "rel_delta_clipped"
    if math.isfinite(max_abs_delta):
        if abs(delta) > max_abs_delta:
            delta = math.copysign(max_abs_delta, delta)
            clipped = True
            reason = "abs_delta_clipped"

    corrected = raw + delta
    if model.get("nonnegative_output", True) and corrected < 0:
        corrected = 0.0
        clipped = True
        reason = "nonnegative_clipped"

    return corrected, clipped, reason


def _err_pct(pred: float, wave: float) -> float | None:
    if wave == 0:
        return None
    return (pred - wave) / wave * 100.0


def _mae(values: list[float]) -> float | None:
    clean = [abs(v) for v in values if v is not None and math.isfinite(v)]
    return sum(clean) / len(clean) if clean else None


def main() -> int:
    ap = argparse.ArgumentParser(description="V116 shadow validate V98 scope-aware residual layer.")
    ap.add_argument("--metric-errors", default=None, help="V90 clean metric errors CSV.")
    ap.add_argument("--layer", default=None, help="V98 scope residual layer JSON.")
    ap.add_argument("--output-base", default=None, help="Output base path.")
    ap.add_argument("--print-summary", action="store_true")
    args = ap.parse_args()

    root = _project_root()
    default_dir = root / "scripts" / "wave_records" / "results" / "_calibration_v115"
    metric_errors = Path(args.metric_errors).resolve() if args.metric_errors else _latest_file(default_dir, "*_v90_clean_metric_errors.csv")
    layer_path = Path(args.layer).resolve() if args.layer else _latest_file(default_dir, "*_v98_scope_residual_layer.json")
    output_base = Path(args.output_base).resolve() if args.output_base else default_dir / f"wave_v116_shadow_validation_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    rows = _read_csv(metric_errors)
    layer = json.loads(layer_path.read_text(encoding="utf-8"))
    models = layer.get("models") or []

    model_by_key: dict[tuple[str, str, str], dict[str, Any]] = {}
    for model in models:
        key = (str(model.get("process_type", "")).lower(), str(model.get("metric", "")), str(model.get("regime", "")))
        model_by_key[key] = model

    shadow_rows: list[dict[str, Any]] = []
    for row in rows:
        proc = str(row.get("process_type") or "").lower()
        metric = str(row.get("metric") or "")
        regime = _classify_regime(row)
        key = (proc, metric, regime)
        model = model_by_key.get(key)
        if not model:
            continue

        wave = _f(row.get("wave_value"))
        raw = _f(row.get("aquanova_raw_value"))
        raw_err = _f(row.get("error_pct"))
        if wave is None or raw is None:
            continue

        corrected, clipped, clip_reason = _apply_residual(raw, model)
        corr_err = _err_pct(corrected, wave)
        if corr_err is None:
            continue

        raw_abs = abs(raw_err if raw_err is not None else _err_pct(raw, wave) or 0.0)
        corr_abs = abs(corr_err)
        improvement = raw_abs - corr_abs
        improvement_pct = (improvement / raw_abs * 100.0) if raw_abs else 0.0

        out = dict(row)
        out["v116_regime"] = regime
        out["v116_model_id"] = model.get("model_id")
        out["v116_corrected_value"] = round(corrected, 8)
        out["v116_corrected_error_pct"] = round(corr_err, 8)
        out["v116_corrected_abs_error_pct"] = round(corr_abs, 8)
        out["v116_raw_abs_error_pct"] = round(raw_abs, 8)
        out["v116_improvement_abs_pct_points"] = round(improvement, 8)
        out["v116_improvement_pct"] = round(improvement_pct, 8)
        out["v116_clipped"] = bool(clipped)
        out["v116_clip_reason"] = clip_reason
        shadow_rows.append(out)

    group_map: dict[tuple[str, str, str, str], list[dict[str, Any]]] = {}
    for r in shadow_rows:
        key = (
            str(r.get("process_type")),
            str(r.get("metric")),
            str(r.get("v116_regime")),
            str(r.get("v116_model_id")),
        )
        group_map.setdefault(key, []).append(r)

    group_rows: list[dict[str, Any]] = []
    for (proc, metric, regime, model_id), items in sorted(group_map.items()):
        raw_errs = [_f(x.get("v116_raw_abs_error_pct")) for x in items]
        corr_errs = [_f(x.get("v116_corrected_abs_error_pct")) for x in items]
        raw_mae = _mae([x for x in raw_errs if x is not None]) or 0.0
        corr_mae = _mae([x for x in corr_errs if x is not None]) or 0.0
        improvement_pct = ((raw_mae - corr_mae) / raw_mae * 100.0) if raw_mae else 0.0
        holdout_items = [x for x in items if str(x.get("split")) == "holdout"]
        holdout_raw = _mae([_f(x.get("v116_raw_abs_error_pct")) for x in holdout_items if _f(x.get("v116_raw_abs_error_pct")) is not None])
        holdout_corr = _mae([_f(x.get("v116_corrected_abs_error_pct")) for x in holdout_items if _f(x.get("v116_corrected_abs_error_pct")) is not None])
        if holdout_raw is not None and holdout_corr is not None and holdout_raw:
            holdout_improve = (holdout_raw - holdout_corr) / holdout_raw * 100.0
        else:
            holdout_improve = None

        clipped_count = sum(1 for x in items if str(x.get("v116_clipped")).lower() == "true")
        status = "pass"
        flags: list[str] = []
        if len(items) < 5:
            status = "review"
            flags.append("low_n")
        if improvement_pct < 5.0:
            status = "review"
            flags.append("low_improvement")
        if corr_mae > raw_mae:
            status = "fail"
            flags.append("regression")
        if holdout_improve is not None and holdout_improve < -5.0:
            status = "fail"
            flags.append("holdout_regression")
        if corr_mae > 25.0:
            status = "review" if status == "pass" else status
            flags.append("corrected_mae_above_25")

        group_rows.append({
            "schema_version": "aquanova.wave_scope_residual_shadow_validation.v116",
            "process_type": proc,
            "metric": metric,
            "regime": regime,
            "model_id": model_id,
            "shadow_n": len(items),
            "holdout_n": len(holdout_items),
            "raw_mean_abs_error_pct": round(raw_mae, 6),
            "shadow_mean_abs_error_pct": round(corr_mae, 6),
            "improvement_pct": round(improvement_pct, 6),
            "holdout_raw_mean_abs_error_pct": "" if holdout_raw is None else round(holdout_raw, 6),
            "holdout_shadow_mean_abs_error_pct": "" if holdout_corr is None else round(holdout_corr, 6),
            "holdout_improvement_pct": "" if holdout_improve is None else round(holdout_improve, 6),
            "clipped_count": clipped_count,
            "shadow_status": status,
            "flags": ";".join(flags),
            "runtime_enabled": False,
        })

    all_raw_mae = _mae([_f(r.get("v116_raw_abs_error_pct")) for r in shadow_rows if _f(r.get("v116_raw_abs_error_pct")) is not None]) or 0.0
    all_corr_mae = _mae([_f(r.get("v116_corrected_abs_error_pct")) for r in shadow_rows if _f(r.get("v116_corrected_abs_error_pct")) is not None]) or 0.0
    all_improve = ((all_raw_mae - all_corr_mae) / all_raw_mae * 100.0) if all_raw_mae else 0.0

    output_base.parent.mkdir(parents=True, exist_ok=True)
    shadow_csv = output_base.with_name(output_base.name + "_v116_shadow_rows.csv")
    group_csv = output_base.with_name(output_base.name + "_v116_group_summary.csv")
    summary_json = output_base.with_name(output_base.name + "_v116_summary.json")
    report_md = output_base.with_name(output_base.name + "_v116_report.md")

    shadow_fields = list(shadow_rows[0].keys()) if shadow_rows else []
    group_fields = list(group_rows[0].keys()) if group_rows else []
    _write_csv(shadow_csv, shadow_rows, shadow_fields)
    _write_csv(group_csv, group_rows, group_fields)

    summary = {
        "schema_version": "aquanova.wave_scope_residual_shadow_validation.v116",
        "input_metric_errors": str(metric_errors),
        "input_layer": str(layer_path),
        "model_count": len(models),
        "shadow_metric_row_count": len(shadow_rows),
        "scope_group_count": len(group_rows),
        "group_status_counts": dict(Counter(g["shadow_status"] for g in group_rows)),
        "raw_mean_abs_error_pct": round(all_raw_mae, 6),
        "shadow_mean_abs_error_pct": round(all_corr_mae, 6),
        "improvement_pct": round(all_improve, 6),
        "runtime_enabled_by_default": False,
        "next_step": "Review PASS/REVIEW/FAIL groups; do not enable runtime until runtime guard validation is run.",
    }
    summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    md = [
        "# V116 scope residual shadow validation",
        f"- Metric errors: `{metric_errors.name}`",
        f"- Layer: `{layer_path.name}`",
        f"- Shadow metric rows: {len(shadow_rows)}",
        f"- Scope groups: {len(group_rows)}",
        f"- Raw MAE: {summary['raw_mean_abs_error_pct']}%",
        f"- Shadow MAE: {summary['shadow_mean_abs_error_pct']}%",
        f"- Improvement: {summary['improvement_pct']}%",
        "",
        "## Group status counts",
    ]
    for k, v in summary["group_status_counts"].items():
        md.append(f"- {k}: {v}")
    md.append("")
    md.append("## Groups")
    for g in group_rows:
        md.append(
            f"- {g['shadow_status'].upper()} `{g['process_type']}.{g['metric']}.{g['regime']}`: "
            f"{g['raw_mean_abs_error_pct']}% -> {g['shadow_mean_abs_error_pct']}% "
            f"({g['improvement_pct']}% improvement); flags={g['flags'] or '-'}"
        )
    report_md.write_text("\n".join(md) + "\n", encoding="utf-8")

    if args.print_summary:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        print(f"shadow_rows: {shadow_csv}")
        print(f"group_summary: {group_csv}")
        print(f"report: {report_md}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
