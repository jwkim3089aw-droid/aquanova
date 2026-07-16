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
manifest = wr / "ro" / "v151_ro_stages_add_second_pass_manifest.json"

for p in [legacy, wrapper, stages]:
    assert p.exists(), p
    py_compile.compile(str(p), doraise=True)
    ast.parse(p.read_text(encoding="utf-8"))

assert manifest.exists(), manifest
data = json.loads(manifest.read_text(encoding="utf-8"))
moved = data["moved_functions"]
assert moved == ["_add_second_pass"], moved

lt = legacy.read_text(encoding="utf-8")
st = stages.read_text(encoding="utf-8")

compatible_import_markers = [
    "# V151_RO_STAGES_IMPORT_START",
    "# V150_RO_STAGES_IMPORT_START",
    "# V148_RO_STAGES_IMPORT_START",
    "# V145A_RO_STAGES_IMPORT_START",
    "# V145_RO_STAGES_IMPORT_START",
    "# V140_RO_STAGES_IMPORT_START",
]
assert any(marker in lt for marker in compatible_import_markers), compatible_import_markers
assert "_add_second_pass" in lt, "_add_second_pass must still be imported/re-exported by legacy"
assert "# V151_RO_STAGES_ADD_SECOND_PASS_APPLIED" in st
assert "def _add_second_pass(" not in lt
assert "def _add_second_pass(" in st

if data.get("uses_wave_automation_error_factory"):
    assert "def WaveAutomationError(" in st

bridged = data.get("bridged_ro_refs", {})
for ref, module in bridged.items():
    assert f"def {ref}(" in st or ref in st, f"RO bridge/import missing for {ref}->{module}"

for dep in data.get("explicit_import_dependencies", []):
    assert dep in st, f"explicit import dependency missing: {dep}"

sys.path.insert(0, str(wr))
import wave_ro_engine  # type: ignore
assert hasattr(wave_ro_engine, "_add_second_pass")
assert hasattr(wave_ro_engine, "configure_schema_ro_case")

mod = importlib.import_module("ro.stages")
assert hasattr(mod, "_add_second_pass")

print("V151 RO stages add-second-pass extraction selftest PASS")
print("moved_count=1")
print("uses_wave_automation_error_factory=" + str(data.get("uses_wave_automation_error_factory")))
print("bridged_ro_refs=" + ",".join(f"{k}->{v}" for k, v in data.get("bridged_ro_refs", {}).items()))
print("explicit_import_dependencies=" + ",".join(data.get("explicit_import_dependencies", [])))
print("active_import_marker=" + str(data.get("active_import_marker", "")))
