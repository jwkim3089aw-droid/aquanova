"""V96 runtime WAVE-correction benchmark comparison helpers.

V95 connects the reviewed V92 correction layer to the SimulationEngine as an
explicit opt-in wrapper.  V96 adds the next safety gate: compare a raw AquaNova
benchmark result against the same result after opt-in runtime correction.

The functions here do not enable correction globally.  They only summarize
whether a corrected benchmark improved, stayed neutral, or regressed compared
with the raw result.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

SCHEMA_VERSION = "aquanova.wave_runtime_benchmark.v96"


BAD_STATUSES = {"WARN", "FAIL", "MISSING"}
HARD_BAD_STATUSES = {"FAIL", "MISSING"}


def _as_dict(obj: Any) -> dict[str, Any]:
    if obj is None:
        return {}
    if isinstance(obj, Mapping):
        return dict(obj)
    if hasattr(obj, "model_dump"):
        try:
            return dict(obj.model_dump(mode="python"))
        except TypeError:
            return dict(obj.model_dump())
    if hasattr(obj, "dict"):
        return dict(obj.dict())
    if hasattr(obj, "__dict__"):
        return dict(vars(obj))
    return {}


def _rows(report: Any) -> list[dict[str, Any]]:
    payload = _as_dict(report)
    rows = payload.get("rows")
    if rows is None and hasattr(report, "rows"):
        rows = getattr(report, "rows")
    out: list[dict[str, Any]] = []
    for row in rows or []:
        out.append(_as_dict(row))
    return out


def _to_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        val = float(value)
        return val if math.isfinite(val) else None
    text = str(value).strip().replace(",", "")
    if not text or text.lower() in {"none", "nan", "null"}:
        return None
    try:
        val = float(text)
    except ValueError:
        return None
    return val if math.isfinite(val) else None


def _status_counts(rows: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        status = str(row.get("status") or "").upper() or "UNKNOWN"
        counts[status] = counts.get(status, 0) + 1
    return counts


def _mean_abs_pct(rows: Sequence[Mapping[str, Any]]) -> float | None:
    vals = [_to_float(row.get("pct_error")) for row in rows]
    clean = [abs(v) for v in vals if v is not None]
    if not clean:
        return None
    return sum(clean) / len(clean)


def _max_abs_pct(rows: Sequence[Mapping[str, Any]]) -> float | None:
    vals = [_to_float(row.get("pct_error")) for row in rows]
    clean = [abs(v) for v in vals if v is not None]
    return max(clean) if clean else None


def _bad_count(counts: Mapping[str, int], *, hard_only: bool = False) -> int:
    statuses = HARD_BAD_STATUSES if hard_only else BAD_STATUSES
    return sum(int(counts.get(s, 0)) for s in statuses)


def summarize_report(report: Any) -> dict[str, Any]:
    rows = _rows(report)
    counts = _status_counts(rows)
    return {
        "row_count": len(rows),
        "status_counts": counts,
        "bad_count": _bad_count(counts),
        "hard_bad_count": _bad_count(counts, hard_only=True),
        "mean_abs_pct_error": _mean_abs_pct(rows),
        "max_abs_pct_error": _max_abs_pct(rows),
        "warn_keys": [str(r.get("key")) for r in rows if str(r.get("status")).upper() == "WARN"],
        "fail_keys": [str(r.get("key")) for r in rows if str(r.get("status")).upper() == "FAIL"],
        "missing_keys": [str(r.get("key")) for r in rows if str(r.get("status")).upper() == "MISSING"],
    }


def compare_raw_vs_corrected_reports(
    raw_report: Any,
    corrected_report: Any,
    *,
    correction_report: Mapping[str, Any] | None = None,
    max_regression_pct_points: float = 2.0,
    min_mean_improvement_pct: float = 5.0,
) -> dict[str, Any]:
    """Return a V96 safety summary for one raw/corrected benchmark pair."""
    raw = summarize_report(raw_report)
    corrected = summarize_report(corrected_report)
    raw_mean = _to_float(raw.get("mean_abs_pct_error"))
    corr_mean = _to_float(corrected.get("mean_abs_pct_error"))
    improvement_pct = None
    delta_pp = None
    if raw_mean is not None and corr_mean is not None:
        delta_pp = raw_mean - corr_mean
        improvement_pct = 0.0 if abs(raw_mean) < 1e-12 else (delta_pp / raw_mean) * 100.0

    flags: list[str] = []
    if corrected["hard_bad_count"] > raw["hard_bad_count"]:
        flags.append("hard_status_regression")
    if corrected["bad_count"] > raw["bad_count"]:
        flags.append("warn_fail_missing_count_regression")
    if delta_pp is not None and delta_pp < -abs(float(max_regression_pct_points)):
        flags.append("mean_abs_error_regression")

    if flags:
        gate_status = "review_regression"
    elif improvement_pct is not None and improvement_pct >= float(min_mean_improvement_pct):
        gate_status = "pass_improved"
    else:
        gate_status = "review_neutral"

    return {
        "schema_version": SCHEMA_VERSION,
        "gate_status": gate_status,
        "gate_flags": flags,
        "raw": raw,
        "corrected": corrected,
        "mean_abs_error_delta_pct_points": round(delta_pp, 6) if delta_pp is not None else None,
        "mean_abs_error_improvement_pct": round(improvement_pct, 6) if improvement_pct is not None else None,
        "correction_status": dict(correction_report or {}).get("status", ""),
        "correction_applied_count": int(dict(correction_report or {}).get("applied_count") or 0),
        "correction_report": dict(correction_report or {}),
    }


def write_json(payload: Mapping[str, Any], path: str | Path) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(dict(payload), ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return out


def format_runtime_benchmark_markdown(summary: Mapping[str, Any], *, title: str = "V96 WAVE Runtime Correction Benchmark") -> str:
    raw = dict(summary.get("raw") or {})
    corrected = dict(summary.get("corrected") or {})
    lines = [
        f"# {title}",
        "",
        f"- Schema: `{summary.get('schema_version', SCHEMA_VERSION)}`",
        f"- Gate status: `{summary.get('gate_status')}`",
        f"- Gate flags: `{ '|'.join(summary.get('gate_flags') or []) or 'none' }`",
        f"- Correction status: `{summary.get('correction_status')}`",
        f"- Correction applied count: {summary.get('correction_applied_count')}",
        "",
        "| Metric | Raw | Corrected |",
        "|---|---:|---:|",
        f"| Row count | {raw.get('row_count')} | {corrected.get('row_count')} |",
        f"| Bad count (WARN/FAIL/MISSING) | {raw.get('bad_count')} | {corrected.get('bad_count')} |",
        f"| Hard bad count (FAIL/MISSING) | {raw.get('hard_bad_count')} | {corrected.get('hard_bad_count')} |",
        f"| Mean abs % error | {_fmt(raw.get('mean_abs_pct_error'))} | {_fmt(corrected.get('mean_abs_pct_error'))} |",
        f"| Max abs % error | {_fmt(raw.get('max_abs_pct_error'))} | {_fmt(corrected.get('max_abs_pct_error'))} |",
        "",
        f"Mean abs error delta: `{_fmt(summary.get('mean_abs_error_delta_pct_points'))}` percentage points",
        f"Mean abs error improvement: `{_fmt(summary.get('mean_abs_error_improvement_pct'))}%`",
        "",
        "## Raw status counts",
        "",
        f"`{raw.get('status_counts')}`",
        "",
        "## Corrected status counts",
        "",
        f"`{corrected.get('status_counts')}`",
        "",
        "## Notes",
        "",
        "V96 is a safety gate. It does not enable WAVE correction globally. A `review_regression` status means keep runtime correction opt-in/off and inspect the promoted layer or benchmark context before exposing it to UI/API defaults.",
    ]
    return "\n".join(lines)


def _fmt(value: Any) -> str:
    val = _to_float(value)
    return "—" if val is None else f"{val:.4g}"
