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
manifest = wr / "ro" / "v152_ro_stages_configure_stage_grid_manifest.json"

for p in [legacy, wrapper, stages]:
    assert p.exists(), p
    py_compile.compile(str(p), doraise=True)
    ast.parse(p.read_text(encoding="utf-8"))

assert manifest.exists(), manifest
data = json.loads(manifest.read_text(encoding="utf-8"))
moved = data["moved_functions"]
assert moved == ["_configure_stage_grid"], moved

lt = legacy.read_text(encoding="utf-8")
st = stages.read_text(encoding="utf-8")

compatible_import_markers = [
    "# V152_RO_STAGES_IMPORT_START",
    "# V151_RO_STAGES_IMPORT_START",
    "# V150_RO_STAGES_IMPORT_START",
    "# V148_RO_STAGES_IMPORT_START",
    "# V145A_RO_STAGES_IMPORT_START",
    "# V145_RO_STAGES_IMPORT_START",
    "# V140_RO_STAGES_IMPORT_START",
]
assert any(marker in lt for marker in compatible_import_markers), compatible_import_markers
assert "_configure_stage_grid" in lt, "_configure_stage_grid must still be imported/re-exported by legacy"
assert "# V152_RO_STAGES_CONFIGURE_STAGE_GRID_APPLIED" in st
assert "def _configure_stage_grid(" not in lt
assert "def _configure_stage_grid(" in st

if data.get("uses_wave_automation_error_factory"):
    assert "def WaveAutomationError(" in st

for ref in data.get("bridged_legacy_refs", []):
    assert f"def {ref}(" in st, f"legacy bridge missing for {ref}"

for ref, module in data.get("bridged_ro_refs", {}).items():
    assert f"def {ref}(" in st or ref in st, f"RO bridge/import missing for {ref}->{module}"

for dep in data.get("explicit_import_dependencies", []):
    assert dep in st, f"explicit import dependency missing: {dep}"

sys.path.insert(0, str(wr))
import wave_ro_engine  # type: ignore
assert hasattr(wave_ro_engine, "_configure_stage_grid")
assert hasattr(wave_ro_engine, "configure_schema_ro_case")

mod = importlib.import_module("ro.stages")
assert hasattr(mod, "_configure_stage_grid")

print("V152 RO stages configure-stage-grid extraction selftest PASS")
print("moved_count=1")
print("uses_wave_automation_error_factory=" + str(data.get("uses_wave_automation_error_factory")))
print("bridged_ro_refs=" + ",".join(f"{k}->{v}" for k, v in data.get("bridged_ro_refs", {}).items()))
print("bridged_legacy_refs=" + ",".join(data.get("bridged_legacy_refs", [])))
print("explicit_import_dependencies=" + ",".join(data.get("explicit_import_dependencies", [])))
print("active_import_marker=" + str(data.get("active_import_marker", "")))
