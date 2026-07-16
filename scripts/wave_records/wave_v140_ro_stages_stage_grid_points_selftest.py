#!/usr/bin/env python3
# V148A_STAGE_GRID_POINTS_SELFTEST_COMPAT_APPLIED
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
manifest = wr / "ro" / "v140_ro_stages_stage_grid_points_manifest.json"

for p in [legacy, wrapper, stages]:
    assert p.exists(), p
    py_compile.compile(str(p), doraise=True)
    ast.parse(p.read_text(encoding="utf-8"))

assert manifest.exists(), manifest
data = json.loads(manifest.read_text(encoding="utf-8"))
moved = data["moved_functions"]
assert moved == ["_stage_grid_points"], moved

lt = legacy.read_text(encoding="utf-8")
st = stages.read_text(encoding="utf-8")

compatible_import_markers = [
    "# V140_RO_STAGES_IMPORT_START",
    "# V145_RO_STAGES_IMPORT_START",
    "# V145A_RO_STAGES_IMPORT_START",
    "# V148_RO_STAGES_IMPORT_START",
]
assert any(marker in lt for marker in compatible_import_markers), compatible_import_markers
assert "_stage_grid_points" in lt, "_stage_grid_points must still be imported/re-exported by legacy"
assert "# V140_RO_STAGES_STAGE_GRID_POINTS_APPLIED" in st
assert "def _stage_grid_points(" not in lt
assert "def _stage_grid_points(" in st

for ref in data.get("bridged_legacy_refs", []):
    assert f"def {ref}(" in st, f"bridge missing for {ref}"

sys.path.insert(0, str(wr))
import wave_ro_engine  # type: ignore
assert hasattr(wave_ro_engine, "_stage_grid_points")
assert hasattr(wave_ro_engine, "configure_schema_ro_case")

mod = importlib.import_module("ro.stages")
assert hasattr(mod, "_stage_grid_points")

print("V148A/V140-compatible RO stages stage-grid-points selftest PASS")
print("moved_count=1")
print("bridged_legacy_refs=" + ",".join(data.get("bridged_legacy_refs", [])))
