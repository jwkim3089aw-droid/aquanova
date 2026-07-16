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
manifest = wr / "ro" / "v158_ro_stages_restore_topologies_manifest.json"

for p in [legacy, wrapper, stages]:
    assert p.exists(), p
    py_compile.compile(str(p), doraise=True)
    ast.parse(p.read_text(encoding="utf-8"))

assert manifest.exists(), manifest
data = json.loads(manifest.read_text(encoding="utf-8"))
moved = data["moved_functions"]
assert moved == ["_restore_stage_topologies_after_flow_commit"], moved

lt = legacy.read_text(encoding="utf-8")
st = stages.read_text(encoding="utf-8")

compatible_import_markers = [
    "# V158_RO_STAGES_IMPORT_START",
    "# V153_RO_STAGES_IMPORT_START",
    "# V152_RO_STAGES_IMPORT_START",
    "# V151_RO_STAGES_IMPORT_START",
    "# V150_RO_STAGES_IMPORT_START",
    "# V148_RO_STAGES_IMPORT_START",
    "# V145A_RO_STAGES_IMPORT_START",
    "# V145_RO_STAGES_IMPORT_START",
    "# V140_RO_STAGES_IMPORT_START",
]
assert any(marker in lt for marker in compatible_import_markers), compatible_import_markers
assert "_restore_stage_topologies_after_flow_commit" in lt, "_restore_stage_topologies_after_flow_commit must still be imported/re-exported by legacy"
assert "# V158_RO_STAGES_RESTORE_TOPOLOGIES_APPLIED" in st
assert "def _restore_stage_topologies_after_flow_commit(" not in lt
assert "def _restore_stage_topologies_after_flow_commit(" in st

imports = set(data.get("explicit_import_dependencies", [])) | set(data.get("safe_direct_import_dependencies", []))
assert "logging" in imports, data
assert "import logging" in st or "logging" in st

bridged = data.get("bridged_ro_refs", {})
assert "_capture_case_ro_state" in bridged or "_capture_case_ro_state" in st, data

# The old V145A selftest should still be satisfied because a def remains in ro.stages,
# but the implementation is now real rather than the earlier legacy bridge.
assert "getattr(_legacy, '_restore_stage_topologies_after_flow_commit')" not in st

sys.path.insert(0, str(wr))
import wave_ro_engine  # type: ignore
assert hasattr(wave_ro_engine, "_restore_stage_topologies_after_flow_commit")
assert hasattr(wave_ro_engine, "_stabilize_after_flow_commit")
assert hasattr(wave_ro_engine, "configure_schema_ro_case")

mod = importlib.import_module("ro.stages")
assert hasattr(mod, "_restore_stage_topologies_after_flow_commit")
assert hasattr(mod, "_stabilize_after_flow_commit")

print("V158 RO stages restore-topologies extraction selftest PASS")
print("moved_count=1")
print("bridged_ro_refs=" + ",".join(f"{k}->{v}" for k, v in data.get("bridged_ro_refs", {}).items()))
print("explicit_import_dependencies=" + ",".join(data.get("explicit_import_dependencies", [])))
print("safe_direct_import_dependencies=" + ",".join(data.get("safe_direct_import_dependencies", [])))
print("active_import_marker=" + str(data.get("active_import_marker", "")))
