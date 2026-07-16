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
manifest = wr / "ro" / "v161_ro_runner_find_new_dialog_manifest.json"

for p in [legacy, wrapper, runner]:
    assert p.exists(), p
    py_compile.compile(str(p), doraise=True)
    ast.parse(p.read_text(encoding="utf-8"))

assert manifest.exists(), manifest
data = json.loads(manifest.read_text(encoding="utf-8"))
moved = data["moved_functions"]
assert moved == ["_find_new_wave_dialog"], moved

lt = legacy.read_text(encoding="utf-8")
rt = runner.read_text(encoding="utf-8")

compatible_import_markers = [
    "# V161_RO_RUNNER_IMPORT_START",
    "# V147_RO_RUNNER_IMPORT_START",
    "# V135_RO_RUNNER_IMPORT_START",
]
assert any(marker in lt for marker in compatible_import_markers), compatible_import_markers
assert "_find_new_wave_dialog" in lt, "_find_new_wave_dialog must still be imported/re-exported by legacy"
assert "# V161_RO_RUNNER_FIND_NEW_DIALOG_APPLIED" in rt
assert "def _find_new_wave_dialog(" not in lt
assert "def _find_new_wave_dialog(" in rt

imports = set(data.get("explicit_import_dependencies", [])) | set(data.get("safe_direct_import_dependencies", []))
assert "time" in imports, data
assert "import time" in rt or "time" in rt

for ref in ["_get_process_id", "list_visible_windows"]:
    assert ref in rt or ref in data.get("bridged_ro_refs", {}) or ref in data.get("bridged_legacy_refs", []), ref

sys.path.insert(0, str(wr))
import wave_ro_engine  # type: ignore
assert hasattr(wave_ro_engine, "_find_new_wave_dialog")
assert hasattr(wave_ro_engine, "configure_schema_ro_case")

mod = importlib.import_module("ro.runner")
assert hasattr(mod, "_find_new_wave_dialog")

print("V161 RO runner find-new-dialog extraction selftest PASS")
print("moved_count=1")
print("bridged_ro_refs=" + ",".join(f"{k}->{v}" for k, v in data.get("bridged_ro_refs", {}).items()))
print("bridged_legacy_refs=" + ",".join(data.get("bridged_legacy_refs", [])))
print("explicit_import_dependencies=" + ",".join(data.get("explicit_import_dependencies", [])))
print("safe_direct_import_dependencies=" + ",".join(data.get("safe_direct_import_dependencies", [])))
print("active_import_marker=" + str(data.get("active_import_marker", "")))
