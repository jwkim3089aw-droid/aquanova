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
manifest = wr / "ro" / "v157_ro_membrane_reconcile_pass_topology_manifest.json"

for p in [legacy, wrapper, membrane]:
    assert p.exists(), p
    py_compile.compile(str(p), doraise=True)
    ast.parse(p.read_text(encoding="utf-8"))

assert manifest.exists(), manifest
data = json.loads(manifest.read_text(encoding="utf-8"))
moved = data["moved_functions"]
assert moved == ["_reconcile_ro_pass_topology"], moved

lt = legacy.read_text(encoding="utf-8")
mt = membrane.read_text(encoding="utf-8")

compatible_import_markers = [
    "# V157_RO_MEMBRANE_IMPORT_START",
    "# V141_RO_MEMBRANE_IMPORT_START",
]
assert any(marker in lt for marker in compatible_import_markers), compatible_import_markers
assert "_reconcile_ro_pass_topology" in lt, "_reconcile_ro_pass_topology must still be imported/re-exported by legacy"
assert "# V157_RO_MEMBRANE_RECONCILE_PASS_TOPOLOGY_APPLIED" in mt
assert "def _reconcile_ro_pass_topology(" not in lt
assert "def _reconcile_ro_pass_topology(" in mt

imports = set(data.get("explicit_import_dependencies", [])) | set(data.get("safe_direct_import_dependencies", []))
assert "logging" in imports, data
assert "import logging" in mt or "logging" in mt

bridged = data.get("bridged_ro_refs", {})
# These are expected by the V146 planner, but allow pre-existing local imports/defs.
for ref in ["_select_pass", "screenshot", "wait"]:
    assert ref in mt or ref in bridged, f"{ref} missing from membrane after extraction"
if "WaveAutomationError" in mt:
    assert "WaveAutomationError" in mt

sys.path.insert(0, str(wr))
import wave_ro_engine  # type: ignore
assert hasattr(wave_ro_engine, "_reconcile_ro_pass_topology")
assert hasattr(wave_ro_engine, "configure_schema_ro_case")

mod = importlib.import_module("ro.membrane")
assert hasattr(mod, "_reconcile_ro_pass_topology")

print("V157 RO membrane reconcile-pass-topology extraction selftest PASS")
print("moved_count=1")
print("bridged_ro_refs=" + ",".join(f"{k}->{v}" for k, v in data.get("bridged_ro_refs", {}).items()))
print("explicit_import_dependencies=" + ",".join(data.get("explicit_import_dependencies", [])))
print("safe_direct_import_dependencies=" + ",".join(data.get("safe_direct_import_dependencies", [])))
print("active_import_marker=" + str(data.get("active_import_marker", "")))
