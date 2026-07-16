#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import ast
import importlib
import json
import py_compile
import sys

ROOT = Path(__file__).resolve().parents[2]
wave_records = ROOT / "scripts" / "wave_records"
legacy = wave_records / "wave_batch_legacy.py"
wrapper = wave_records / "wave_batch.py"
plan_schema = wave_records / "batch" / "plan_schema.py"
manifest_path = wave_records / "batch" / "v131a_plan_schema_extraction_manifest.json"

for p in [legacy, wrapper, plan_schema]:
    assert p.exists(), p
    py_compile.compile(str(p), doraise=True)
    ast.parse(p.read_text(encoding="utf-8"))

assert manifest_path.exists(), manifest_path
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
moved = manifest.get("moved_functions", [])
assert moved, "no moved functions in manifest"
assert "_canonical_temperature_mode" in moved or "_settings_from_case" in moved, moved

legacy_text = legacy.read_text(encoding="utf-8")
plan_text = plan_schema.read_text(encoding="utf-8")

assert "# V131A_PLAN_SCHEMA_IMPORT_START" in legacy_text
assert "from batch.plan_schema import" in legacy_text or "from .batch.plan_schema import" in legacy_text

for name in moved:
    assert f"def {name}(" not in legacy_text, f"{name} still defined in legacy"
    assert f"def {name}(" in plan_text, f"{name} missing from plan_schema"

sys.path.insert(0, str(wave_records))
import wave_batch  # type: ignore
assert hasattr(wave_batch, "run_ro_excel_batch"), "wave_batch facade lost run_ro_excel_batch"
for name in moved:
    assert hasattr(wave_batch, name), f"moved helper not re-exported: {name}"

mod = importlib.import_module("batch.plan_schema")
for name in moved:
    assert hasattr(mod, name), f"plan_schema missing {name}"

print("V131A wave_batch plan_schema extraction selftest PASS")
print(f"moved_count={len(moved)}")
