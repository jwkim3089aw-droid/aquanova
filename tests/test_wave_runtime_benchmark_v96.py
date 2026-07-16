from __future__ import annotations

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.simulation.calibration.wave_runtime_benchmark import (
    compare_raw_vs_corrected_reports,
    format_runtime_benchmark_markdown,
    summarize_report,
)


def _report(rows):
    return {"rows": rows}


def test_v96_summarizes_benchmark_report_rows() -> None:
    summary = summarize_report(_report([
        {"key": "x", "status": "PASS", "pct_error": 1.0},
        {"key": "y", "status": "WARN", "pct_error": 9.0},
        {"key": "z", "status": "FAIL", "pct_error": 30.0},
    ]))
    assert summary["row_count"] == 3
    assert summary["bad_count"] == 2
    assert summary["hard_bad_count"] == 1
    assert round(summary["mean_abs_pct_error"], 6) == round((1.0 + 9.0 + 30.0) / 3.0, 6)


def test_v96_gate_detects_improvement() -> None:
    raw = _report([
        {"key": "pressure", "status": "WARN", "pct_error": 40.0},
        {"key": "tds", "status": "PASS", "pct_error": 2.0},
    ])
    corrected = _report([
        {"key": "pressure", "status": "PASS", "pct_error": 6.0},
        {"key": "tds", "status": "PASS", "pct_error": 1.0},
    ])
    summary = compare_raw_vs_corrected_reports(raw, corrected, correction_report={"status": "corrected", "applied_count": 1})
    assert summary["gate_status"] == "pass_improved"
    assert summary["correction_applied_count"] == 1


def test_v96_gate_detects_regression() -> None:
    raw = _report([
        {"key": "pressure", "status": "PASS", "pct_error": 2.0},
    ])
    corrected = _report([
        {"key": "pressure", "status": "FAIL", "pct_error": 80.0},
    ])
    summary = compare_raw_vs_corrected_reports(raw, corrected)
    assert summary["gate_status"] == "review_regression"
    assert "hard_status_regression" in summary["gate_flags"]


def test_v96_markdown_contains_gate_status() -> None:
    summary = compare_raw_vs_corrected_reports(
        _report([{"key": "a", "status": "WARN", "pct_error": 10.0}]),
        _report([{"key": "a", "status": "PASS", "pct_error": 2.0}]),
    )
    md = format_runtime_benchmark_markdown(summary)
    assert "Gate status" in md
    assert "pass_improved" in md
