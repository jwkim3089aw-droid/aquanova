#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import math
import re
from collections import Counter, defaultdict
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
        out = float(s)
        return out if math.isfinite(out) else default
    except Exception:
        return default


def _name(row: dict[str, Any]) -> str:
    return str(row.get("wave_pdf_name") or row.get("pdf_name") or "")


def _classify_regime(row: dict[str, Any]) -> str:
    proc = str(row.get("process_type") or row.get("process") or "").lower()
    name = _name(row)

    if proc == "ccro":
        pass_count = _f(row.get("pass_count_hint"))
        if pass_count == 2 or "2PASS" in name.upper() or re.search(r"_P1R\d+", name, re.I):
            return "ccro_2pass"

        # Meeting/LG derived stress regions are isolated from standard runtime use.
        if "FLUX_P" in name:
            return "ccro_product_flux_push"
        if re.search(r"TDS(?:0450|1000|1500|2000)", name):
            return "ccro_tds_sweep_unverified"
        if re.search(r"_FR(?:270|300)(?:_|\.pdf)", name):
            return "ccro_fr_stress"

        product_flow = _f(row.get("wave_system_product_flow_m3h"))
        rec = _f(row.get("target_recovery_pct_hint") or row.get("wave_system_recovery_pct"))
        pf = _f(row.get("wave_ccro_pf_feed_ratio_pct"))
        if product_flow is not None and rec is not None:
            if abs(product_flow - 1.82) <= 0.08 and abs(rec - 90.0) <= 0.5 and (pf is None or pf <= 150.0):
                return "ccro_small_1p82_r90_already_aligned"

        if re.search(r"_F100_R(?:75|80|85|90|95)\.pdf", name, re.I) or re.search(r"_R(?:75|80|85|90|95)\.pdf", name, re.I):
            return "ccro_recovery_sweep"
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
    if proc == "uf":
        return "uf_reference"
    return proc or "unknown"


def _apply_residual(raw: float, model: dict[str, Any]) -> tuple[float, bool, str]:
    payload = model.get("model_payload") or {}
    delta_ratio = _f(payload.get("delta_ratio"), 0.0) or 0.0
    guards = payload.get("residual_guards") or {}

    proposed = raw * (1.0 + delta_ratio)
    min_ratio = _f(guards.get("min_ratio"), 0.0) or 0.0
    max_ratio = _f(guards.get("max_ratio"), float("inf")) or float("inf")
    max_rel_delta = abs(_f(guards.get("max_rel_delta"), float("inf")) or float("inf"))
    max_abs_delta = abs(_f(guards.get("max_abs_delta"), float("inf")) or float("inf"))

    bounded = min(max(proposed, raw * min_ratio), raw * max_ratio)
    delta = bounded - raw
    clipped = False
    reason = "bounded_residual_delta"

    if math.isfinite(max_rel_delta):
        cap = abs(raw) * max_rel_delta
        if abs(delta) > cap:
            delta = math.copysign(cap, delta)
            clipped = True
            reason = "rel_delta_clipped"
    if math.isfinite(max_abs_delta):
        if abs(delta) > max_abs_delta:
            delta = math.copysign(max_abs_delta, delta)
            clipped = True
            reason = "abs_delta_clipped"

    corrected = raw + delta
    if bool(model.get("nonnegative_output", True)) and corrected < 0:
        corrected = 0.0
        clipped = True
        reason = "nonnegative_clipped"

    return corrected, clipped, reason


def _err_pct(pred: float, wave: float) -> float | None:
    if wave == 0:
        return None
    return (pred - wave) / wave * 100.0


def _mae(values: list[float | None]) -> float | None:
    clean = [abs(v) for v in values if v is not None and math.isfinite(v)]
    return sum(clean) / len(clean) if clean else None


def _runtime_guard(metric: str, raw: float, corrected: float, regime: str) -> str | None:
    if corrected < 0:
        return "negative_corrected_value"
    if raw != 0:
        ratio = corrected / raw
        global_min = 0.20 if metric == "specific_energy" else 0.35
        global_max = 2.20
        if ratio < global_min:
            return f"ratio_below_guard:{ratio:.6g}<{global_min}"
        if ratio > global_max:
            return f"ratio_above_guard:{ratio:.6g}>{global_max}"
    if regime == "ccro_small_1p82_r90_already_aligned" and metric in {"product_tds", "final_concentrate_tds"}:
        return "already_wave_aligned_metric"
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description="V119 wide validation of V117 pass-only residual layer on V90 metric rows.")
    ap.add_argument("--metric-errors", default=None, help="V90 clean metric errors CSV.")
    ap.add_argument("--layer", default=None, help="V117 pass-only layer JSON.")
    ap.add_argument("--output-base", default=None, help="Output base path.")
    ap.add_argument("--print-summary", action="store_true")
    args = ap.parse_args()

    root = _project_root()
    default_dir = root / "scripts" / "wave_records" / "results" / "_calibration_v115"
    metric_errors = Path(args.metric_errors).resolve() if args.metric_errors else _latest_file(default_dir, "*_v90_clean_metric_errors.csv")
    layer_path = Path(args.layer).resolve() if args.layer else _latest_file(default_dir, "*v117_pass_only_scope_residual_layer.json")
    output_base = Path(args.output_base).resolve() if args.output_base else default_dir / f"wave_v119_wide_layer_validation_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    rows = _read_csv(metric_errors)
    layer = json.loads(layer_path.read_text(encoding="utf-8"))
    models = layer.get("models") or []
    model_by_key = {
        (str(m.get("process_type", "")).lower(), str(m.get("metric", "")), str(m.get("regime", ""))): m
        for m in models
        if isinstance(m, dict)
    }

    validation_rows: list[dict[str, Any]] = []
    for row in rows:
        proc = str(row.get("process_type") or "").lower()
        metric = str(row.get("metric") or "")
        regime = _classify_regime(row)
        key = (proc, metric, regime)
        model = model_by_key.get(key)

        wave = _f(row.get("wave_value"))
        raw = _f(row.get("aquanova_raw_value"))
        raw_err = _f(row.get("error_pct"))
        if wave is None or raw is None:
            continue

        out = dict(row)
        out["v119_regime"] = regime
        out["v119_model_id"] = model.get("model_id") if model else ""
        out["v119_runtime_status"] = "no_model"
        out["v119_corrected_value"] = raw
        out["v119_corrected_error_pct"] = raw_err
        out["v119_corrected_abs_error_pct"] = abs(raw_err) if raw_err is not None else ""
        out["v119_raw_abs_error_pct"] = abs(raw_err) if raw_err is not None else ""
        out["v119_guard_reason"] = ""
        out["v119_clipped"] = False
        out["v119_clip_reason"] = ""

        if model is not None:
            proposed, clipped, clip_reason = _apply_residual(raw, model)
            guard = _runtime_guard(metric, raw, proposed, regime)
            if guard:
                out["v119_runtime_status"] = "blocked_runtime_guard"
                out["v119_guard_reason"] = guard
                out["v119_blocked_corrected_value"] = proposed
            else:
                corr_err = _err_pct(proposed, wave)
                if corr_err is not None:
                    out["v119_runtime_status"] = "applied"
                    out["v119_corrected_value"] = proposed
                    out["v119_corrected_error_pct"] = corr_err
                    out["v119_corrected_abs_error_pct"] = abs(corr_err)
                    out["v119_clipped"] = bool(clipped)
                    out["v119_clip_reason"] = clip_reason
                else:
                    out["v119_runtime_status"] = "not_applicable_zero_wave"
                    out["v119_guard_reason"] = "wave_value_zero"

        validation_rows.append(out)

    # Applied-only group summaries.
    group_map: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for r in validation_rows:
        if r.get("v119_runtime_status") != "applied":
            continue
        group_map[(
            str(r.get("process_type")),
            str(r.get("metric")),
            str(r.get("v119_regime")),
            str(r.get("v119_model_id")),
        )].append(r)

    group_rows: list[dict[str, Any]] = []
    for (proc, metric, regime, model_id), items in sorted(group_map.items()):
        raw_vals = [_f(x.get("v119_raw_abs_error_pct")) for x in items]
        corr_vals = [_f(x.get("v119_corrected_abs_error_pct")) for x in items]
        raw_mae = _mae(raw_vals) or 0.0
        corr_mae = _mae(corr_vals) or 0.0
        improve = ((raw_mae - corr_mae) / raw_mae * 100.0) if raw_mae else 0.0

        holdout = [x for x in items if str(x.get("split")) == "holdout"]
        h_raw = _mae([_f(x.get("v119_raw_abs_error_pct")) for x in holdout])
        h_corr = _mae([_f(x.get("v119_corrected_abs_error_pct")) for x in holdout])
        h_improve = ((h_raw - h_corr) / h_raw * 100.0) if h_raw else None

        status = "pass"
        flags: list[str] = []
        if corr_mae > raw_mae:
            status = "fail"
            flags.append("regression")
        if h_improve is not None and h_improve < -5.0:
            status = "fail"
            flags.append("holdout_regression")
        if corr_mae > 25.0:
            status = "review" if status == "pass" else status
            flags.append("corrected_mae_above_25")
        if improve < 5.0:
            status = "review" if status == "pass" else status
            flags.append("low_improvement")

        group_rows.append({
            "schema_version": "aquanova.wave_wide_layer_validation.v119",
            "process_type": proc,
            "metric": metric,
            "regime": regime,
            "model_id": model_id,
            "applied_n": len(items),
            "holdout_n": len(holdout),
            "raw_mean_abs_error_pct": round(raw_mae, 6),
            "corrected_mean_abs_error_pct": round(corr_mae, 6),
            "improvement_pct": round(improve, 6),
            "holdout_raw_mean_abs_error_pct": "" if h_raw is None else round(h_raw, 6),
            "holdout_corrected_mean_abs_error_pct": "" if h_corr is None else round(h_corr, 6),
            "holdout_improvement_pct": "" if h_improve is None else round(h_improve, 6),
            "status": status,
            "flags": ";".join(flags),
        })

    applied = [r for r in validation_rows if r.get("v119_runtime_status") == "applied"]
    no_model = [r for r in validation_rows if r.get("v119_runtime_status") == "no_model"]
    blocked = [r for r in validation_rows if r.get("v119_runtime_status") == "blocked_runtime_guard"]

    raw_mae_all = _mae([_f(r.get("v119_raw_abs_error_pct")) for r in applied]) or 0.0
    corr_mae_all = _mae([_f(r.get("v119_corrected_abs_error_pct")) for r in applied]) or 0.0
    improve_all = ((raw_mae_all - corr_mae_all) / raw_mae_all * 100.0) if raw_mae_all else 0.0

    status_counts = Counter(g["status"] for g in group_rows)
    gate_status = "pass_improved"
    gate_flags: list[str] = []
    if status_counts.get("fail", 0):
        gate_status = "review_or_fail"
        gate_flags.append("one_or_more_groups_failed")
    elif status_counts.get("review", 0):
        gate_status = "review"
        gate_flags.append("one_or_more_groups_review")
    if applied and corr_mae_all > raw_mae_all:
        gate_status = "review_regression"
        gate_flags.append("overall_regression")

    output_base.parent.mkdir(parents=True, exist_ok=True)
    validation_csv = output_base.with_name(output_base.name + "_v119_validation_rows.csv")
    group_csv = output_base.with_name(output_base.name + "_v119_group_summary.csv")
    summary_json = output_base.with_name(output_base.name + "_v119_summary.json")
    report_md = output_base.with_name(output_base.name + "_v119_report.md")

    _write_csv(validation_csv, validation_rows, list(validation_rows[0].keys()) if validation_rows else [])
    _write_csv(group_csv, group_rows, list(group_rows[0].keys()) if group_rows else [])

    summary = {
        "schema_version": "aquanova.wave_wide_layer_validation.v119",
        "input_metric_errors": str(metric_errors),
        "input_layer": str(layer_path),
        "metric_row_count": len(validation_rows),
        "model_count": len(models),
        "applied_row_count": len(applied),
        "no_model_row_count": len(no_model),
        "blocked_row_count": len(blocked),
        "runtime_status_counts": dict(Counter(r["v119_runtime_status"] for r in validation_rows)),
        "group_count": len(group_rows),
        "group_status_counts": dict(status_counts),
        "applied_raw_mean_abs_error_pct": round(raw_mae_all, 6),
        "applied_corrected_mean_abs_error_pct": round(corr_mae_all, 6),
        "applied_improvement_pct": round(improve_all, 6),
        "gate_status": gate_status,
        "gate_flags": gate_flags,
        "runtime_enabled_by_default": False,
        "next_step": "If pass_improved, keep runtime opt-in and run more process-specific engine benchmarks before UI default exposure.",
    }
    summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    md = [
        "# V119 wide layer validation",
        "",
        f"- Metric rows: {len(validation_rows)}",
        f"- Models: {len(models)}",
        f"- Applied rows: {len(applied)}",
        f"- No-model rows: {len(no_model)}",
        f"- Blocked rows: {len(blocked)}",
        f"- Applied raw MAE: {summary['applied_raw_mean_abs_error_pct']}%",
        f"- Applied corrected MAE: {summary['applied_corrected_mean_abs_error_pct']}%",
        f"- Applied improvement: {summary['applied_improvement_pct']}%",
        f"- Gate status: `{gate_status}`",
        f"- Gate flags: `{', '.join(gate_flags) if gate_flags else 'none'}`",
        "",
        "## Runtime status counts",
    ]
    for k, v in summary["runtime_status_counts"].items():
        md.append(f"- {k}: {v}")
    md.append("")
    md.append("## Group summaries")
    for g in group_rows:
        md.append(
            f"- {g['status'].upper()} `{g['process_type']}.{g['metric']}.{g['regime']}`: "
            f"{g['raw_mean_abs_error_pct']}% -> {g['corrected_mean_abs_error_pct']}% "
            f"({g['improvement_pct']}%); flags={g['flags'] or '-'}"
        )
    report_md.write_text("\n".join(md) + "\n", encoding="utf-8")

    if args.print_summary:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        print(f"validation_rows: {validation_csv}")
        print(f"group_summary: {group_csv}")
        print(f"report: {report_md}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
