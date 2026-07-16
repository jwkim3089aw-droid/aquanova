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
membrane = wr / "ro" / "membrane.py"
manifest = wr / "ro" / "v160_ro_membrane_verify_stage_grid_membranes_manifest.json"

for p in [legacy, wrapper, membrane]:
    assert p.exists(), p
    py_compile.compile(str(p), doraise=True)
    ast.parse(p.read_text(encoding="utf-8"))

assert manifest.exists(), manifest
data = json.loads(manifest.read_text(encoding="utf-8"))
moved = data["moved_functions"]
assert moved == ["_verify_stage_grid_membranes"], moved

lt = legacy.read_text(encoding="utf-8")
mt = membrane.read_text(encoding="utf-8")

compatible_import_markers = [
    "# V160_RO_MEMBRANE_IMPORT_START",
    "# V157_RO_MEMBRANE_IMPORT_START",
    "# V141_RO_MEMBRANE_IMPORT_START",
]
assert any(marker in lt for marker in compatible_import_markers), compatible_import_markers
assert "_verify_stage_grid_membranes" in lt, "_verify_stage_grid_membranes must still be imported/re-exported by legacy"
assert "# V160_RO_MEMBRANE_VERIFY_STAGE_GRID_MEMBRANES_APPLIED" in mt
assert "def _verify_stage_grid_membranes(" not in lt
assert "def _verify_stage_grid_membranes(" in mt

bridged = data.get("bridged_ro_refs", {})
for ref in ["record_event", "select_combo_exact", "uia_read_combo_candidates"]:
    assert ref in mt or ref in bridged, f"{ref} missing after extraction"

sys.path.insert(0, str(wr))
import wave_ro_engine  # type: ignore
assert hasattr(wave_ro_engine, "_verify_stage_grid_membranes")
assert hasattr(wave_ro_engine, "configure_schema_ro_case")

mod = importlib.import_module("ro.membrane")
assert hasattr(mod, "_verify_stage_grid_membranes")
assert hasattr(mod, "_reconcile_ro_pass_topology")

print("V160 RO membrane verify-stage-grid-membranes extraction selftest PASS")
print("moved_count=1")
print("bridged_ro_refs=" + ",".join(f"{k}->{v}" for k, v in data.get("bridged_ro_refs", {}).items()))
print("explicit_import_dependencies=" + ",".join(data.get("explicit_import_dependencies", [])))
print("safe_direct_import_dependencies=" + ",".join(data.get("safe_direct_import_dependencies", [])))
print("active_import_marker=" + str(data.get("active_import_marker", "")))
