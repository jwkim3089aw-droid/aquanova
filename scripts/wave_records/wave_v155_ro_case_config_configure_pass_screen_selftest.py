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
manifest = wr / "ro" / "v155_ro_case_config_configure_pass_screen_manifest.json"

for p in [legacy, wrapper, case_config]:
    assert p.exists(), p
    py_compile.compile(str(p), doraise=True)
    ast.parse(p.read_text(encoding="utf-8"))

assert manifest.exists(), manifest
data = json.loads(manifest.read_text(encoding="utf-8"))
moved = data["moved_functions"]
assert moved == ["_configure_pass_screen"], moved

lt = legacy.read_text(encoding="utf-8")
ct = case_config.read_text(encoding="utf-8")

compatible_import_markers = [
    "# V155_RO_CASE_CONFIG_IMPORT_START",
    "# V154_RO_CASE_CONFIG_IMPORT_START",
    "# V149_RO_CASE_CONFIG_IMPORT_START",
    "# V143A_RO_CASE_CONFIG_IMPORT_START",
    "# V143_RO_CASE_CONFIG_IMPORT_START",
    "# V142_RO_CASE_CONFIG_IMPORT_START",
]
assert any(marker in lt for marker in compatible_import_markers), compatible_import_markers
assert "_configure_pass_screen" in lt, "_configure_pass_screen must still be imported/re-exported by legacy"
assert "# V155_RO_CASE_CONFIG_CONFIGURE_PASS_SCREEN_APPLIED" in ct
assert "def _configure_pass_screen(" not in lt
assert "def _configure_pass_screen(" in ct

bridged = data.get("bridged_ro_refs", {})
assert "_configure_stage_grid" in bridged, data
assert "set_and_verify_ro_temperature_mode" in bridged, data
for ref, module in bridged.items():
    assert f"def {ref}(" in ct or ref in ct, f"RO bridge/import missing for {ref}->{module}"

assert "_settings_from_ro_case" in ct
assert "_fmt_value" in ct

sys.path.insert(0, str(wr))
import wave_ro_engine  # type: ignore
assert hasattr(wave_ro_engine, "_configure_pass_screen")
assert hasattr(wave_ro_engine, "configure_schema_ro_case")

mod = importlib.import_module("ro.case_config")
assert hasattr(mod, "_configure_pass_screen")
assert hasattr(mod, "_settings_from_ro_case")

print("V155 RO case_config configure-pass-screen extraction selftest PASS")
print("moved_count=1")
print("bridged_ro_refs=" + ",".join(f"{k}->{v}" for k, v in data.get("bridged_ro_refs", {}).items()))
print("explicit_import_dependencies=" + ",".join(data.get("explicit_import_dependencies", [])))
print("active_import_marker=" + str(data.get("active_import_marker", "")))
