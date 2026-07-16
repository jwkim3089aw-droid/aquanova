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
manifest = wr / "ro" / "v137b_ro_case_config_settings_manifest.json"

for p in [legacy, wrapper, case_config]:
    assert p.exists(), p
    py_compile.compile(str(p), doraise=True)
    ast.parse(p.read_text(encoding="utf-8"))

assert manifest.exists(), manifest
data = json.loads(manifest.read_text(encoding="utf-8"))
assert data["moved_functions"] == ["_settings_from_ro_case"], data

lt = legacy.read_text(encoding="utf-8")
ct = case_config.read_text(encoding="utf-8")

assert "# V137B_RO_CASE_CONFIG_IMPORT_START" in lt
assert "# V137B_RO_CASE_CONFIG_SETTINGS_APPLIED" in ct
assert "def _settings_from_ro_case(" not in lt
assert "def _settings_from_ro_case(" in ct
assert "_fmt_value" in ct, "_fmt_value support missing from case_config"

sys.path.insert(0, str(wr))
import wave_ro_engine  # type: ignore
assert hasattr(wave_ro_engine, "_settings_from_ro_case")
assert hasattr(wave_ro_engine, "configure_schema_ro_case")

mod = importlib.import_module("ro.case_config")
assert hasattr(mod, "_settings_from_ro_case")
assert hasattr(mod, "_fmt_value")

print("V137B RO case_config settings extraction selftest PASS")
print("moved_count=1")
print("copied_support_count=" + str(data.get("copied_support_count", 0)))
