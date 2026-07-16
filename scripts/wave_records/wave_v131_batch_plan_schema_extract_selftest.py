#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import ast, json, py_compile, sys, importlib

ROOT = Path(__file__).resolve().parents[2]
wr = ROOT / "scripts" / "wave_records"
legacy = wr / "wave_batch_legacy.py"
plan = wr / "batch" / "plan_schema.py"
manifest = wr / "batch" / "v131_plan_schema_extraction_manifest.json"

for p in [legacy, plan, wr / "wave_batch.py"]:
    assert p.exists(), p
    py_compile.compile(str(p), doraise=True)
    ast.parse(p.read_text(encoding="utf-8"))

data = json.loads(manifest.read_text(encoding="utf-8"))
moved = data["moved_functions"]
assert moved
lt = legacy.read_text(encoding="utf-8")
pt = plan.read_text(encoding="utf-8")
assert "# V131_PLAN_SCHEMA_IMPORT_START" in lt

for name in moved:
    assert f"def {name}(" not in lt, f"{name} still in legacy"
    assert f"def {name}(" in pt, f"{name} missing in plan_schema"

sys.path.insert(0, str(wr))
import wave_batch  # type: ignore
assert hasattr(wave_batch, "run_ro_excel_batch")
for name in moved:
    assert hasattr(wave_batch, name), name

mod = importlib.import_module("batch.plan_schema")
for name in moved:
    assert hasattr(mod, name), name

print("V131 wave_batch plan_schema extraction selftest PASS")
print("moved_count=" + str(len(moved)))
