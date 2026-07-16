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
manifest = wr / "ro" / "v154_ro_case_config_settings_from_case_manifest.json"

for p in [legacy, wrapper, case_config]:
    assert p.exists(), p
    py_compile.compile(str(p), doraise=True)
    ast.parse(p.read_text(encoding="utf-8"))

assert manifest.exists(), manifest
data = json.loads(manifest.read_text(encoding="utf-8"))
moved = data["moved_functions"]
assert moved == ["_settings_from_ro_case"], moved

lt = legacy.read_text(encoding="utf-8")
ct = case_config.read_text(encoding="utf-8")

compatible_import_markers = [
    "# V154_RO_CASE_CONFIG_IMPORT_START",
    "# V149_RO_CASE_CONFIG_IMPORT_START",
    "# V143A_RO_CASE_CONFIG_IMPORT_START",
    "# V143_RO_CASE_CONFIG_IMPORT_START",
    "# V142_RO_CASE_CONFIG_IMPORT_START",
]
assert any(marker in lt for marker in compatible_import_markers), compatible_import_markers
assert "_settings_from_ro_case" in lt, "_settings_from_ro_case must still be imported/re-exported by legacy"
assert "# V154_RO_CASE_CONFIG_SETTINGS_FROM_CASE_APPLIED" in ct
assert "def _settings_from_ro_case(" not in lt
assert "def _settings_from_ro_case(" in ct

bridges = set(data.get("bridged_legacy_refs", []))
assert "_fmt_value" in bridges, data
assert "def _fmt_value(" in ct
assert "getattr(_legacy, '_fmt_value')" in ct

sys.path.insert(0, str(wr))
import wave_ro_engine  # type: ignore
assert hasattr(wave_ro_engine, "_settings_from_ro_case")
assert hasattr(wave_ro_engine, "configure_schema_ro_case")

mod = importlib.import_module("ro.case_config")
assert hasattr(mod, "_settings_from_ro_case")
assert hasattr(mod, "_fmt_value")

print("V154 RO case_config settings-from-case extraction selftest PASS")
print("moved_count=1")
print("bridged_legacy_refs=" + ",".join(data.get("bridged_legacy_refs", [])))
print("active_import_marker=" + str(data.get("active_import_marker", "")))
