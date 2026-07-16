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
manifest = wr / "ro" / "v141_ro_membrane_diagnostic_points_manifest.json"

for p in [legacy, wrapper, membrane]:
    assert p.exists(), p
    py_compile.compile(str(p), doraise=True)
    ast.parse(p.read_text(encoding="utf-8"))

assert manifest.exists(), manifest
data = json.loads(manifest.read_text(encoding="utf-8"))
moved = data["moved_functions"]
assert moved == ["_ro_diagnostic_points"], moved

lt = legacy.read_text(encoding="utf-8")
mt = membrane.read_text(encoding="utf-8")

assert "# V141_RO_MEMBRANE_IMPORT_START" in lt
assert "# V141_RO_MEMBRANE_DIAGNOSTIC_POINTS_APPLIED" in mt
assert "def _ro_diagnostic_points(" not in lt
assert "def _ro_diagnostic_points(" in mt

if "_stage_grid_points" in data.get("known_ro_dependencies", []):
    assert "from ro.stages import _stage_grid_points" in mt or "from .stages import _stage_grid_points" in mt

sys.path.insert(0, str(wr))
import wave_ro_engine  # type: ignore
assert hasattr(wave_ro_engine, "_ro_diagnostic_points")
assert hasattr(wave_ro_engine, "configure_schema_ro_case")

mod = importlib.import_module("ro.membrane")
assert hasattr(mod, "_ro_diagnostic_points")

print("V141 RO membrane diagnostic extraction selftest PASS")
print("moved_count=1")
print("known_ro_dependencies=" + ",".join(data.get("known_ro_dependencies", [])))
