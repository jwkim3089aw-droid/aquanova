#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.simulation.calibration.wave_runtime_benchmark import compare_raw_vs_corrected_reports


def _report(rows):
    return {"rows": rows}


def main() -> int:
    raw = _report([
        {"key": "a", "status": "WARN", "pct_error": 20.0},
        {"key": "b", "status": "PASS", "pct_error": 2.0},
    ])
    improved = _report([
        {"key": "a", "status": "PASS", "pct_error": 4.0},
        {"key": "b", "status": "PASS", "pct_error": 1.0},
    ])
    summary = compare_raw_vs_corrected_reports(raw, improved, correction_report={"status": "corrected", "applied_count": 1})
    assert summary["gate_status"] == "pass_improved", summary
    assert summary["correction_applied_count"] == 1

    regressed = _report([
        {"key": "a", "status": "FAIL", "pct_error": 80.0},
        {"key": "b", "status": "PASS", "pct_error": 2.0},
    ])
    summary2 = compare_raw_vs_corrected_reports(raw, regressed)
    assert summary2["gate_status"] == "review_regression", summary2
    assert "hard_status_regression" in summary2["gate_flags"]
    print("V96 correction benchmark selftest PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
