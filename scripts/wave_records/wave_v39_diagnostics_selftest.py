#!/usr/bin/env python3
"""Offline regression checks for V52 diagnostics and stable temperature policy."""
from __future__ import annotations

from wave_batch import expand_cases_for_wave_global_temperature
from wave_ro_schema import ROCaseConfig, ROPassConfig, ROStageConfig


def make_case(*, modes: tuple[str, str]) -> ROCaseConfig:
    return ROCaseConfig(
        case_id="SELFTEST_V52",
        pdf_name="SELFTEST_V52.pdf",
        water_profile="Well Water - Low Hardness",
        feed_flow_m3h=100.0,
        feed_temperature_c=25.0,
        feed_temperature_min_c=10.0,
        feed_temperature_max_c=35.0,
        passes=[
            ROPassConfig(
                recovery_pct=74.0,
                stage_count=1,
                temperature_mode=modes[0],
                temperature_c=25.0,
                stages=[ROStageConfig(pv=10, elements_per_pv=6, membrane="BW30XHR PRO-440")],
            ),
            ROPassConfig(
                recovery_pct=84.0,
                stage_count=2,
                flow_factor=1.0,
                temperature_mode=modes[1],
                temperature_c=25.0,
                stages=[
                    ROStageConfig(pv=4, elements_per_pv=6, membrane="BW30HR-440"),
                    ROStageConfig(pv=2, elements_per_pv=6, membrane="BW30 PRO-400"),
                ],
            ),
        ],
    )


for modes in (("Design", "Specify"), ("Specify", "Specify")):
    expanded, manifest = expand_cases_for_wave_global_temperature([make_case(modes=modes)])
    assert len(expanded) == 1
    assert all(p.temperature_mode == "Design" for p in expanded[0].passes)
    decision = manifest[0]["mode_decisions"][0]
    assert decision["selected_mode"] == "Design"
    assert "topology reset" in decision["reason"]

from wave_diagnostics import capture_ro_state, diff_ro_states, write_convergence_failure_report  # noqa: E402,F401
from wave_uia import uia_snapshot_ro_state  # noqa: E402,F401

# PowerShell variables are case-insensitive.  $PID is automatic/read-only, so
# assigning $pid broke every V39 targeted snapshot with VariableNotWritable.
from pathlib import Path  # noqa: E402
_uia_source = (Path(__file__).with_name("wave_uia.py")).read_text(encoding="utf-8")
assert "$pid = $window.Current.ProcessId" not in _uia_source
assert "$pid=" not in _uia_source.casefold()
assert "$wavePid = $window.Current.ProcessId" in _uia_source

print("V52 diagnostics/stable-temperature self-test OK")
