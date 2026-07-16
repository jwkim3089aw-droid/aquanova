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
manifest = wr / "ro" / "v150_ro_stages_stage_cell_point_manifest.json"

for p in [legacy, wrapper, stages]:
    assert p.exists(), p
    py_compile.compile(str(p), doraise=True)
    ast.parse(p.read_text(encoding="utf-8"))

assert manifest.exists(), manifest
data = json.loads(manifest.read_text(encoding="utf-8"))
moved = data["moved_functions"]
assert moved == ["_stage_cell_point"], moved

lt = legacy.read_text(encoding="utf-8")
st = stages.read_text(encoding="utf-8")

compatible_import_markers = [
    "# V150_RO_STAGES_IMPORT_START",
    "# V148_RO_STAGES_IMPORT_START",
    "# V145A_RO_STAGES_IMPORT_START",
    "# V145_RO_STAGES_IMPORT_START",
    "# V140_RO_STAGES_IMPORT_START",
]
assert any(marker in lt for marker in compatible_import_markers), compatible_import_markers
assert "_stage_cell_point" in lt, "_stage_cell_point must still be imported/re-exported by legacy"
assert "# V150_RO_STAGES_STAGE_CELL_POINT_APPLIED" in st
assert "def _stage_cell_point(" not in lt
assert "def _stage_cell_point(" in st

if data.get("uses_wave_automation_error_factory"):
    assert "def WaveAutomationError(" in st

for ref in data.get("bridged_legacy_refs", []):
    assert f"def {ref}(" in st, f"legacy bridge missing for {ref}"
assert "_map_reference_point" in data.get("bridged_legacy_refs", []), data

sys.path.insert(0, str(wr))
import wave_ro_engine  # type: ignore
assert hasattr(wave_ro_engine, "_stage_cell_point")
assert hasattr(wave_ro_engine, "configure_schema_ro_case")

mod = importlib.import_module("ro.stages")
assert hasattr(mod, "_stage_cell_point")
assert hasattr(mod, "_map_reference_point")

print("V150 RO stages stage-cell-point extraction selftest PASS")
print("moved_count=1")
print("uses_wave_automation_error_factory=" + str(data.get("uses_wave_automation_error_factory")))
print("bridged_legacy_refs=" + ",".join(data.get("bridged_legacy_refs", [])))
print("active_import_marker=" + str(data.get("active_import_marker", "")))
