#!/usr/bin/env python3
# V149A_VERIFY_INPUTS_SELFTEST_COMPAT_APPLIED
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
manifest = wr / "ro" / "v143a_ro_case_config_verify_inputs_manifest.json"

for p in [legacy, wrapper, case_config]:
    assert p.exists(), p
    py_compile.compile(str(p), doraise=True)
    ast.parse(p.read_text(encoding="utf-8"))

assert manifest.exists(), manifest
data = json.loads(manifest.read_text(encoding="utf-8"))
moved = data["moved_functions"]
assert moved == ["_verify_case_operating_inputs"], moved

lt = legacy.read_text(encoding="utf-8")
ct = case_config.read_text(encoding="utf-8")

compatible_import_markers = [
    "# V143A_RO_CASE_CONFIG_IMPORT_START",
    "# V149_RO_CASE_CONFIG_IMPORT_START",
]
assert any(marker in lt for marker in compatible_import_markers), compatible_import_markers
assert "_verify_case_operating_inputs" in lt, "_verify_case_operating_inputs must still be imported/re-exported by legacy"
assert "# V143A_RO_CASE_CONFIG_VERIFY_INPUTS_APPLIED" in ct
assert "def _verify_case_operating_inputs(" not in lt
assert "def _verify_case_operating_inputs(" in ct

for ref in data.get("bridged_legacy_refs", []):
    assert f"def {ref}(" in ct, f"legacy bridge missing for {ref}"

for dep in data.get("explicit_import_dependencies", []):
    assert dep in ct, f"explicit import dependency missing: {dep}"

sys.path.insert(0, str(wr))
import wave_ro_engine  # type: ignore
assert hasattr(wave_ro_engine, "_verify_case_operating_inputs")
assert hasattr(wave_ro_engine, "configure_schema_ro_case")

mod = importlib.import_module("ro.case_config")
assert hasattr(mod, "_verify_case_operating_inputs")

print("V149A/V143A-compatible RO case_config verify-inputs selftest PASS")
print("moved_count=1")
print("bridged_legacy_refs=" + ",".join(data.get("bridged_legacy_refs", [])))
print("explicit_import_dependencies=" + ",".join(data.get("explicit_import_dependencies", [])))
