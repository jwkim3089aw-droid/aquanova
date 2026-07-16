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
case_config = wr / "ro" / "case_config.py"
manifest = wr / "ro" / "v137a_ro_case_config_fmt_dependency_manifest.json"

for p in [legacy, wrapper, case_config]:
    assert p.exists(), p
    py_compile.compile(str(p), doraise=True)
    ast.parse(p.read_text(encoding="utf-8"))

assert manifest.exists(), manifest
data = json.loads(manifest.read_text(encoding="utf-8"))
moved = data["moved_functions"]
assert moved == ["_fmt_value", "_settings_from_ro_case"], moved

lt = legacy.read_text(encoding="utf-8")
ct = case_config.read_text(encoding="utf-8")

assert "# V137A_RO_CASE_CONFIG_IMPORT_START" in lt
assert "# V137A_RO_CASE_CONFIG_FMT_DEP_APPLIED" in ct
for name in moved:
    assert f"def {name}(" not in lt, f"{name} still in legacy"
    assert f"def {name}(" in ct, f"{name} missing from case_config"

sys.path.insert(0, str(wr))
import wave_ro_engine  # type: ignore
assert hasattr(wave_ro_engine, "_fmt_value")
assert hasattr(wave_ro_engine, "_settings_from_ro_case")
assert hasattr(wave_ro_engine, "configure_schema_ro_case")

mod = importlib.import_module("ro.case_config")
assert hasattr(mod, "_fmt_value")
assert hasattr(mod, "_settings_from_ro_case")

# Tiny behavior probe that should not depend on WAVE UI.
class Dummy:
    pass

print("V137A RO case_config fmt dependency extraction selftest PASS")
print("moved_count=2")
