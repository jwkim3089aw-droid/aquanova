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
manifest = wr / "batch" / "v134c_plan_schema_cluster_extraction_manifest.json"

for p in [legacy, plan_schema, wr / "wave_batch.py"]:
    assert p.exists(), p
    py_compile.compile(str(p), doraise=True)
    ast.parse(p.read_text(encoding="utf-8"))

data = json.loads(manifest.read_text(encoding="utf-8"))
moved = data["moved_functions"]

assert "_canonical_temperature_mode" in moved, moved
assert "_temperature_variant_suffix" in moved, moved

lt = legacy.read_text(encoding="utf-8")
pt = plan_schema.read_text(encoding="utf-8")

assert "# V131A_PLAN_SCHEMA_IMPORT_START" in lt
assert "# V134C_PLAN_SCHEMA_CLUSTER_APPLIED" in pt
assert "import copy" in pt
assert "class WaveAutomationError" in pt

for name in moved:
    assert f"def {name}(" not in lt, f"{name} still in legacy"
    assert f"def {name}(" in pt, f"{name} missing from plan_schema"

assert "def _write_two_case_summary(" in lt, "_write_two_case_summary should remain legacy due STATE"
assert "def run_two_ro_cases(" in lt, "run_two_ro_cases should remain legacy"

sys.path.insert(0, str(wr))
import wave_batch  # type: ignore
assert hasattr(wave_batch, "run_ro_excel_batch")
for name in moved:
    assert hasattr(wave_batch, name), f"wave_batch missing {name}"

mod = importlib.import_module("batch.plan_schema")
for name in moved:
    assert hasattr(mod, name), f"plan_schema missing {name}"

# Basic runtime probe for moved functions.
assert mod._temperature_variant_suffix("project") in {"project", ""}
try:
    mod._canonical_temperature_mode("bad-mode")
except Exception as e:
    assert e.__class__.__name__ == "WaveAutomationError", type(e)
else:
    raise AssertionError("_canonical_temperature_mode should reject bad-mode")

print("V134C wave_batch plan_schema self-contained extraction selftest PASS")
print("moved_count=" + str(len(moved)))
