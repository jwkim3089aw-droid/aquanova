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
plan_schema = wr / "batch" / "plan_schema.py"
manifest = wr / "batch" / "v134e_plan_schema_bridge_static_fix_manifest.json"

assert plan_schema.exists(), plan_schema
assert manifest.exists(), manifest

py_compile.compile(str(plan_schema), doraise=True)
tree = ast.parse(plan_schema.read_text(encoding="utf-8"))

top_classes = [n.name for n in tree.body if isinstance(n, ast.ClassDef)]
assert "WaveAutomationError" in top_classes, top_classes

text = plan_schema.read_text(encoding="utf-8")
assert "# V134E WaveAutomationError bridge" in text
assert "# V134D WaveAutomationError bridge" not in text

sys.path.insert(0, str(wr))
mod = importlib.import_module("batch.plan_schema")
assert hasattr(mod, "WaveAutomationError")
try:
    mod._canonical_temperature_mode("bad-mode")
except Exception as e:
    assert e.__class__.__name__ == "WaveAutomationError", type(e)
else:
    raise AssertionError("_canonical_temperature_mode should reject bad-mode")

data = json.loads(manifest.read_text(encoding="utf-8"))
assert data["schema_version"] == "aquanova.refactor.v134e.plan_schema_bridge_static_fix"

print("V134E plan_schema bridge static fix selftest PASS")
