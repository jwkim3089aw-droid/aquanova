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
feedwater = wr / "ro" / "feedwater.py"
manifest = wr / "ro" / "v138_ro_feedwater_has_flow_optimization_manifest.json"

for p in [legacy, wrapper, feedwater]:
    assert p.exists(), p
    py_compile.compile(str(p), doraise=True)
    ast.parse(p.read_text(encoding="utf-8"))

assert manifest.exists(), manifest
data = json.loads(manifest.read_text(encoding="utf-8"))
moved = data["moved_functions"]
assert moved == ["_has_flow_optimization"], moved

lt = legacy.read_text(encoding="utf-8")
ft = feedwater.read_text(encoding="utf-8")

assert "# V138_RO_FEEDWATER_IMPORT_START" in lt
assert "# V138_RO_FEEDWATER_HAS_FLOW_OPTIMIZATION_APPLIED" in ft
assert "def _has_flow_optimization(" not in lt
assert "def _has_flow_optimization(" in ft

sys.path.insert(0, str(wr))
import wave_ro_engine  # type: ignore
assert hasattr(wave_ro_engine, "_has_flow_optimization")
assert hasattr(wave_ro_engine, "configure_schema_ro_case")

mod = importlib.import_module("ro.feedwater")
assert hasattr(mod, "_has_flow_optimization")

print("V138 RO feedwater leaf extraction selftest PASS")
print("moved_count=1")
