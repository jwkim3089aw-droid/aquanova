#!/usr/bin/env python3
# V142A_CAPTURE_STATE_SELFTEST_COMPAT_APPLIED
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
manifest = wr / "ro" / "v142_ro_case_config_capture_state_manifest.json"

for p in [legacy, wrapper, case_config]:
    assert p.exists(), p
    py_compile.compile(str(p), doraise=True)
    ast.parse(p.read_text(encoding="utf-8"))

assert manifest.exists(), manifest
data = json.loads(manifest.read_text(encoding="utf-8"))
moved = data["moved_functions"]
assert moved == ["_capture_case_ro_state"], moved

lt = legacy.read_text(encoding="utf-8")
ct = case_config.read_text(encoding="utf-8")

# V143/V143A may replace the case_config import block marker while preserving
# the actual _capture_case_ro_state re-export. Accept newer compatible markers.
compatible_import_markers = [
    "# V142_RO_CASE_CONFIG_IMPORT_START",
    "# V143_RO_CASE_CONFIG_IMPORT_START",
    "# V143A_RO_CASE_CONFIG_IMPORT_START",
]
assert any(marker in lt for marker in compatible_import_markers), compatible_import_markers
assert "_capture_case_ro_state" in lt, "_capture_case_ro_state must still be imported/re-exported by legacy"
assert "# V142_RO_CASE_CONFIG_CAPTURE_STATE_APPLIED" in ct
assert "def _capture_case_ro_state(" not in lt
assert "def _capture_case_ro_state(" in ct

if "_ro_diagnostic_points" in data.get("known_ro_dependencies", []):
    assert "from ro.membrane import _ro_diagnostic_points" in ct or "from .membrane import _ro_diagnostic_points" in ct
if "capture_ro_state" in data.get("explicit_import_dependencies", []):
    assert "capture_ro_state" in ct

sys.path.insert(0, str(wr))
import wave_ro_engine  # type: ignore
assert hasattr(wave_ro_engine, "_capture_case_ro_state")
assert hasattr(wave_ro_engine, "configure_schema_ro_case")

mod = importlib.import_module("ro.case_config")
assert hasattr(mod, "_capture_case_ro_state")

print("V142A capture-state selftest compatibility selftest PASS")
print("moved_count=1")
print("known_ro_dependencies=" + ",".join(data.get("known_ro_dependencies", [])))
print("explicit_import_dependencies=" + ",".join(data.get("explicit_import_dependencies", [])))
