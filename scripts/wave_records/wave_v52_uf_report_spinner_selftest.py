#!/usr/bin/env python3
"""Offline checks for V52 UF ReportLoadingSpinner reconciliation."""
from __future__ import annotations

from pathlib import Path

source = Path(__file__).with_name("wave_uf.py").read_text(encoding="utf-8")

assert "def _is_report_spinner_dialog" in source
assert "def _wait_for_uf_report_spinner" in source
assert "ReportLoadingSpinner" in source
assert "calculating report" in source.lower()
assert "uf_report_spinner_waited_v52" in source
assert 'context="uf_summary_report_tab"' in source
assert "timeout_s: float = 75.0" in source
assert "uf_constraint_value_error_closed" in source
assert "UFVideoCase" in source and "SFP2660" in source

print("V52 UF report-spinner reconciliation selftest PASS")
