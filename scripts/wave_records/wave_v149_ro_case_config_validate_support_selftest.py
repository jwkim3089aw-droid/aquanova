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
case_config = wr / "ro" / "case_config.py"
manifest = wr / "ro" / "v149_ro_case_config_validate_support_manifest.json"

for p in [legacy, wrapper, case_config]:
    assert p.exists(), p
    py_compile.compile(str(p), doraise=True)
    ast.parse(p.read_text(encoding="utf-8"))

assert manifest.exists(), manifest
data = json.loads(manifest.read_text(encoding="utf-8"))
moved = data["moved_functions"]
assert moved == ["_validate_case_automation_support"], moved

lt = legacy.read_text(encoding="utf-8")
ct = case_config.read_text(encoding="utf-8")

assert "# V149_RO_CASE_CONFIG_IMPORT_START" in lt
assert "# V149_RO_CASE_CONFIG_VALIDATE_SUPPORT_APPLIED" in ct
assert "def _validate_case_automation_support(" not in lt
assert "def _validate_case_automation_support(" in ct
assert "_validate_case_automation_support" in lt, "helper must still be imported/re-exported by legacy"

if data.get("uses_wave_automation_error_factory"):
    assert "def WaveAutomationError(" in ct

for ref in data.get("bridged_feedwater_refs", []):
    assert f"def {ref}(" in ct, f"feedwater bridge missing for {ref}"
assert "_has_flow_optimization" in data.get("bridged_feedwater_refs", []), data

sys.path.insert(0, str(wr))
import wave_ro_engine  # type: ignore
assert hasattr(wave_ro_engine, "_validate_case_automation_support")
assert hasattr(wave_ro_engine, "configure_schema_ro_case")

mod = importlib.import_module("ro.case_config")
assert hasattr(mod, "_validate_case_automation_support")
assert hasattr(mod, "_has_flow_optimization")

print("V149 RO case_config validation-support extraction selftest PASS")
print("moved_count=1")
print("uses_wave_automation_error_factory=" + str(data.get("uses_wave_automation_error_factory")))
print("bridged_feedwater_refs=" + ",".join(data.get("bridged_feedwater_refs", [])))
