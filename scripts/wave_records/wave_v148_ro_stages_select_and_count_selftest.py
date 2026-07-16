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
stages = wr / "ro" / "stages.py"
manifest = wr / "ro" / "v148_ro_stages_select_and_count_manifest.json"

for p in [legacy, wrapper, stages]:
    assert p.exists(), p
    py_compile.compile(str(p), doraise=True)
    ast.parse(p.read_text(encoding="utf-8"))

assert manifest.exists(), manifest
data = json.loads(manifest.read_text(encoding="utf-8"))
moved = data["moved_functions"]
assert moved == ["_select_pass", "_set_stage_count"], moved

lt = legacy.read_text(encoding="utf-8")
st = stages.read_text(encoding="utf-8")

assert "# V148_RO_STAGES_IMPORT_START" in lt
assert "# V148_RO_STAGES_SELECT_AND_COUNT_APPLIED" in st
for name in moved:
    assert f"def {name}(" not in lt
    assert f"def {name}(" in st
    assert name in lt, f"{name} must still be imported/re-exported by legacy"

if data.get("uses_wave_automation_error_factory"):
    assert "def WaveAutomationError(" in st

for dep in data.get("explicit_import_dependencies", []):
    assert dep in st, f"explicit import dependency missing: {dep}"

sys.path.insert(0, str(wr))
import wave_ro_engine  # type: ignore
for name in moved:
    assert hasattr(wave_ro_engine, name)
assert hasattr(wave_ro_engine, "configure_schema_ro_case")

mod = importlib.import_module("ro.stages")
for name in moved:
    assert hasattr(mod, name)

print("V148 RO stages select/count extraction selftest PASS")
print("moved_count=2")
print("uses_wave_automation_error_factory=" + str(data.get("uses_wave_automation_error_factory")))
print("explicit_import_dependencies=" + ",".join(data.get("explicit_import_dependencies", [])))
