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
manifest = wr / "batch" / "v134_plan_schema_cluster_extraction_manifest.json"

for p in [legacy, plan_schema, wr / "wave_batch.py"]:
    assert p.exists(), p
    py_compile.compile(str(p), doraise=True)
    ast.parse(p.read_text(encoding="utf-8"))

data = json.loads(manifest.read_text(encoding="utf-8"))
moved = data["moved_functions"]
assert moved, "no moved functions"
assert "_canonical_temperature_mode" in moved, moved
assert "_temperature_variant_suffix" in moved, moved

lt = legacy.read_text(encoding="utf-8")
pt = plan_schema.read_text(encoding="utf-8")

assert "# V131A_PLAN_SCHEMA_IMPORT_START" in lt
assert "# V134_PLAN_SCHEMA_CLUSTER_APPLIED" in pt

for name in moved:
    assert f"def {name}(" not in lt, f"{name} still in legacy"
    assert f"def {name}(" in pt, f"{name} missing from plan_schema"

sys.path.insert(0, str(wr))
import wave_batch  # type: ignore
assert hasattr(wave_batch, "run_ro_excel_batch")
for name in moved:
    assert hasattr(wave_batch, name), f"wave_batch missing {name}"

mod = importlib.import_module("batch.plan_schema")
for name in moved:
    assert hasattr(mod, name), f"plan_schema missing {name}"

print("V134 wave_batch plan_schema cluster extraction selftest PASS")
print("moved_count=" + str(len(moved)))
