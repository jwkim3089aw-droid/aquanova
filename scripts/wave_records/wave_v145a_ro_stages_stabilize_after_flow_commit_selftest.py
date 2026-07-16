#!/usr/bin/env python3
# V148A_STABILIZE_SELFTEST_COMPAT_APPLIED
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
manifest = wr / "ro" / "v145a_ro_stages_stabilize_after_flow_commit_manifest.json"

for p in [legacy, wrapper, stages]:
    assert p.exists(), p
    py_compile.compile(str(p), doraise=True)
    ast.parse(p.read_text(encoding="utf-8"))

assert manifest.exists(), manifest
data = json.loads(manifest.read_text(encoding="utf-8"))
moved = data["moved_functions"]
assert moved == ["_stabilize_after_flow_commit"], moved

lt = legacy.read_text(encoding="utf-8")
st = stages.read_text(encoding="utf-8")

compatible_import_markers = [
    "# V145A_RO_STAGES_IMPORT_START",
    "# V148_RO_STAGES_IMPORT_START",
]
assert any(marker in lt for marker in compatible_import_markers), compatible_import_markers
assert "_stabilize_after_flow_commit" in lt, "_stabilize_after_flow_commit must still be imported/re-exported by legacy"
assert "# V145A_RO_STAGES_STABILIZE_AFTER_FLOW_COMMIT_APPLIED" in st
assert "def _stabilize_after_flow_commit(" not in lt
assert "def _stabilize_after_flow_commit(" in st

for ref in data.get("bridged_case_config_refs", []):
    assert f"def {ref}(" in st, f"case_config bridge missing for {ref}"
assert "_verify_case_operating_inputs" in data.get("bridged_case_config_refs", []), data

for ref in data.get("bridged_legacy_refs", []):
    assert f"def {ref}(" in st, f"legacy bridge missing for {ref}"

sys.path.insert(0, str(wr))
import wave_ro_engine  # type: ignore
assert hasattr(wave_ro_engine, "_stabilize_after_flow_commit")
assert hasattr(wave_ro_engine, "configure_schema_ro_case")

mod = importlib.import_module("ro.stages")
assert hasattr(mod, "_stabilize_after_flow_commit")
assert hasattr(mod, "_verify_case_operating_inputs")

print("V148A/V145A-compatible RO stages stabilize-after-flow selftest PASS")
print("moved_count=1")
print("bridged_case_config_refs=" + ",".join(data.get("bridged_case_config_refs", [])))
print("bridged_legacy_refs=" + ",".join(data.get("bridged_legacy_refs", [])))
