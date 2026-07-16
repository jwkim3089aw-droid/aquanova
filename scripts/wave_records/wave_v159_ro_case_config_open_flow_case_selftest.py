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
manifest = wr / "ro" / "v159_ro_case_config_open_flow_case_manifest.json"

for p in [legacy, wrapper, case_config]:
    assert p.exists(), p
    py_compile.compile(str(p), doraise=True)
    ast.parse(p.read_text(encoding="utf-8"))

assert manifest.exists(), manifest
data = json.loads(manifest.read_text(encoding="utf-8"))
moved = data["moved_functions"]
assert moved == ["open_and_configure_ro_flow_case"], moved

lt = legacy.read_text(encoding="utf-8")
ct = case_config.read_text(encoding="utf-8")

compatible_import_markers = [
    "# V159_RO_CASE_CONFIG_IMPORT_START",
    "# V155_RO_CASE_CONFIG_IMPORT_START",
    "# V154_RO_CASE_CONFIG_IMPORT_START",
    "# V149_RO_CASE_CONFIG_IMPORT_START",
    "# V143A_RO_CASE_CONFIG_IMPORT_START",
    "# V143_RO_CASE_CONFIG_IMPORT_START",
    "# V142_RO_CASE_CONFIG_IMPORT_START",
]
assert any(marker in lt for marker in compatible_import_markers), compatible_import_markers
assert "open_and_configure_ro_flow_case" in lt, "open_and_configure_ro_flow_case must still be imported/re-exported by legacy"
assert "# V159_RO_CASE_CONFIG_OPEN_FLOW_CASE_APPLIED" in ct
assert "def open_and_configure_ro_flow_case(" not in lt
assert "def open_and_configure_ro_flow_case(" in ct

imports = set(data.get("explicit_import_dependencies", [])) | set(data.get("safe_direct_import_dependencies", []))
assert "logging" in imports, data
assert "import logging" in ct or "logging" in ct

bridged = data.get("bridged_ro_refs", {})
required_ro_refs = {
    "_find_flow_calculator_dialog",
    "_wait_window_closed",
    "focus_wave",
    "open_and_configure_ro_flow",
    "uia_configure_flow_calculator_recoveries",
}
missing = sorted(ref for ref in required_ro_refs if ref not in bridged and ref not in ct)
assert not missing, {"missing": missing, "bridged": bridged}

assert "logging" not in bridged, "logging should be a direct import, not an RO bridge"

sys.path.insert(0, str(wr))
import wave_ro_engine  # type: ignore
assert hasattr(wave_ro_engine, "open_and_configure_ro_flow_case")
assert hasattr(wave_ro_engine, "configure_schema_ro_case")

mod = importlib.import_module("ro.case_config")
assert hasattr(mod, "open_and_configure_ro_flow_case")

print("V159 RO case_config open-flow-case extraction selftest PASS")
print("moved_count=1")
print("bridged_ro_refs=" + ",".join(f"{k}->{v}" for k, v in data.get("bridged_ro_refs", {}).items()))
print("explicit_import_dependencies=" + ",".join(data.get("explicit_import_dependencies", [])))
print("safe_direct_import_dependencies=" + ",".join(data.get("safe_direct_import_dependencies", [])))
print("active_import_marker=" + str(data.get("active_import_marker", "")))
