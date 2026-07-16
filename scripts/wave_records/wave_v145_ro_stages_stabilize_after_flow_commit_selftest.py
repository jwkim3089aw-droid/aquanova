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
manifest = wr / "ro" / "v145_ro_stages_stabilize_after_flow_commit_manifest.json"

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

assert "# V145_RO_STAGES_IMPORT_START" in lt
assert "# V145_RO_STAGES_STABILIZE_AFTER_FLOW_COMMIT_APPLIED" in st
assert "def _stabilize_after_flow_commit(" not in lt
assert "def _stabilize_after_flow_commit(" in st

for ref in data.get("bridged_legacy_refs", []):
    assert f"def {ref}(" in st, f"bridge missing for {ref}"

sys.path.insert(0, str(wr))
import wave_ro_engine  # type: ignore
assert hasattr(wave_ro_engine, "_stabilize_after_flow_commit")
assert hasattr(wave_ro_engine, "configure_schema_ro_case")

mod = importlib.import_module("ro.stages")
assert hasattr(mod, "_stabilize_after_flow_commit")

print("V145 RO stages stabilize-after-flow extraction selftest PASS")
print("moved_count=1")
print("bridged_legacy_refs=" + ",".join(data.get("bridged_legacy_refs", [])))
