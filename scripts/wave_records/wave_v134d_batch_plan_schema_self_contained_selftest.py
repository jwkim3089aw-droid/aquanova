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
legacy = wr / "wave_batch_legacy.py"
plan_schema = wr / "batch" / "plan_schema.py"
manifest_d = wr / "batch" / "v134d_plan_schema_self_contained_manifest.json"
manifest_e = wr / "batch" / "v134e_plan_schema_bridge_static_fix_manifest.json"

for p in [legacy, plan_schema, wr / "wave_batch.py"]:
    assert p.exists(), p
    py_compile.compile(str(p), doraise=True)
    ast.parse(p.read_text(encoding="utf-8"))

lt = legacy.read_text(encoding="utf-8")
pt = plan_schema.read_text(encoding="utf-8")

# V134D originally installed the extraction. V134E then normalized the bridge.
assert "# V131A_PLAN_SCHEMA_IMPORT_START" in lt
assert (
    "# V134D_PLAN_SCHEMA_SELF_CONTAINED_APPLIED" in pt
    or "# V134C_PLAN_SCHEMA_CLUSTER_APPLIED" in pt
), "plan_schema extraction marker missing"
assert (
    "# V134E WaveAutomationError bridge" in pt
    or "# V134D WaveAutomationError bridge" in pt
), "WaveAutomationError bridge marker missing"
assert "import copy" in pt
assert "class WaveAutomationError" in pt

if manifest_d.exists():
    data = json.loads(manifest_d.read_text(encoding="utf-8"))
    moved = data.get("moved_functions", [])
else:
    moved = [
        "_canonical_temperature_mode",
        "_temperature_variant_suffix",
        "_clone_case_for_global_temperature",
        "expand_cases_for_wave_global_temperature",
    ]

for name in [
    "_canonical_temperature_mode",
    "_temperature_variant_suffix",
    "_clone_case_for_global_temperature",
    "expand_cases_for_wave_global_temperature",
]:
    assert name in moved, moved
    assert f"def {name}(" not in lt, f"{name} still in legacy"
    assert f"def {name}(" in pt, f"{name} missing from plan_schema"

assert "def _write_two_case_summary(" in lt, "_write_two_case_summary should remain legacy"
assert "def run_two_ro_cases(" in lt, "run_two_ro_cases should remain legacy"

sys.path.insert(0, str(wr))
import wave_batch  # type: ignore
assert hasattr(wave_batch, "run_ro_excel_batch")
assert hasattr(wave_batch, "WaveAutomationError")
for name in moved:
    assert hasattr(wave_batch, name), f"wave_batch missing {name}"

mod = importlib.import_module("batch.plan_schema")
for name in moved:
    assert hasattr(mod, name), f"plan_schema missing {name}"
assert hasattr(mod, "WaveAutomationError")

try:
    mod._canonical_temperature_mode("bad-mode")
except Exception as e:
    assert e.__class__.__name__ == "WaveAutomationError", type(e)
else:
    raise AssertionError("_canonical_temperature_mode should reject bad-mode")

if manifest_e.exists():
    json.loads(manifest_e.read_text(encoding="utf-8"))

print("V134F/V134D-compatible plan_schema self-contained selftest PASS")
print("moved_count=" + str(len(moved)))
