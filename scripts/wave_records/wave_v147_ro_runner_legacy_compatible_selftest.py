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
runner = wr / "ro" / "runner.py"
manifest = wr / "ro" / "v147_ro_runner_legacy_compatible_manifest.json"

for p in [legacy, wrapper, runner]:
    assert p.exists(), p
    py_compile.compile(str(p), doraise=True)
    ast.parse(p.read_text(encoding="utf-8"))

assert manifest.exists(), manifest
data = json.loads(manifest.read_text(encoding="utf-8"))
moved = data["moved_functions"]
assert moved == ["_legacy_compatible"], moved

lt = legacy.read_text(encoding="utf-8")
rt = runner.read_text(encoding="utf-8")

assert "# V147_RO_RUNNER_IMPORT_START" in lt
assert "# V147_RO_RUNNER_LEGACY_COMPATIBLE_APPLIED" in rt
assert "def _legacy_compatible(" not in lt
assert "def _legacy_compatible(" in rt

for ref in data.get("bridged_feedwater_refs", []):
    assert f"def {ref}(" in rt, f"feedwater bridge missing for {ref}"
assert "_has_flow_optimization" in data.get("bridged_feedwater_refs", []), data

sys.path.insert(0, str(wr))
import wave_ro_engine  # type: ignore
assert hasattr(wave_ro_engine, "_legacy_compatible")
assert hasattr(wave_ro_engine, "configure_schema_ro_case")

mod = importlib.import_module("ro.runner")
assert hasattr(mod, "_legacy_compatible")
assert hasattr(mod, "_has_flow_optimization")

print("V147 RO runner legacy-compatible extraction selftest PASS")
print("moved_count=1")
print("bridged_feedwater_refs=" + ",".join(data.get("bridged_feedwater_refs", [])))
