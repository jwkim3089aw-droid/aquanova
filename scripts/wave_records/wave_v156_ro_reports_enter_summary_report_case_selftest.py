#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import ast
import importlib
import json
import py_compile
import sys

ROOT = Path(__file__).resolve().parents[2]
wr = ROOT / "scripts" / "wave_records"
legacy = wr / "wave_ro_engine_legacy.py"
wrapper = wr / "wave_ro_engine.py"
reports = wr / "ro" / "reports.py"
manifest = wr / "ro" / "v156_ro_reports_enter_summary_report_case_manifest.json"

for p in [legacy, wrapper, reports]:
    assert p.exists(), p
    py_compile.compile(str(p), doraise=True)
    ast.parse(p.read_text(encoding="utf-8"))

assert manifest.exists(), manifest
data = json.loads(manifest.read_text(encoding="utf-8"))
moved = data["moved_functions"]
assert moved == ["enter_summary_report_case"], moved

lt = legacy.read_text(encoding="utf-8")
rt = reports.read_text(encoding="utf-8")

compatible_import_markers = [
    "# V156_RO_REPORTS_IMPORT_START",
    "# V135_RO_REPORTS_IMPORT_START",
]
assert any(marker in lt for marker in compatible_import_markers), compatible_import_markers
assert "enter_summary_report_case" in lt, "enter_summary_report_case must still be imported/re-exported by legacy"
assert "# V156_RO_REPORTS_ENTER_SUMMARY_REPORT_CASE_APPLIED" in rt
assert "def enter_summary_report_case(" not in lt
assert "def enter_summary_report_case(" in rt

bridged = data.get("bridged_ro_refs", {})
required_ro_refs = {
    "WaveAutomationError",
    "_capture_wave_image",
    "_find_flow_calculator_dialog",
    "_fmt_value",
    "_image_change_ratio",
    "_stabilize_after_flow_commit",
    "_wait_window_closed",
    "click",
    "configure_flow_calculator_dialog",
    "record_event",
    "resolve_wave_blocking_dialogs",
    "screenshot",
    "wait",
}
missing = sorted(required_ro_refs - set(bridged))
assert not missing, {"missing_ro_bridges": missing, "bridged_ro_refs": bridged}

legacy_bridges = set(data.get("bridged_legacy_refs", []))
assert "_repair_missing_element_type_dialog" in legacy_bridges, data
assert "def _repair_missing_element_type_dialog(" in rt
assert "getattr(_legacy, '_repair_missing_element_type_dialog')" in rt

deps = set(data.get("explicit_import_dependencies", []))
assert {"focus_wave", "uia_configure_flow_calculator_recoveries"} <= deps, data

sys.path.insert(0, str(wr))
import wave_ro_engine  # type: ignore
assert hasattr(wave_ro_engine, "enter_summary_report_case")
assert hasattr(wave_ro_engine, "configure_schema_ro_case")

mod = importlib.import_module("ro.reports")
assert hasattr(mod, "enter_summary_report_case")

print("V156 RO reports enter-summary-report-case extraction selftest PASS")
print("moved_count=1")
print("bridged_ro_refs=" + ",".join(f"{k}->{v}" for k, v in data.get("bridged_ro_refs", {}).items()))
print("explicit_import_dependencies=" + ",".join(data.get("explicit_import_dependencies", [])))
print("bridged_legacy_refs=" + ",".join(data.get("bridged_legacy_refs", [])))
print("active_import_marker=" + str(data.get("active_import_marker", "")))
