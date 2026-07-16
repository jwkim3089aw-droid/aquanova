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
retries = wr / "batch" / "retries.py"
manifest = wr / "batch" / "v132_retries_extraction_manifest.json"

for p in [legacy, retries, wr / "wave_batch.py"]:
    assert p.exists(), p
    py_compile.compile(str(p), doraise=True)
    ast.parse(p.read_text(encoding="utf-8"))

data = json.loads(manifest.read_text(encoding="utf-8"))
moved = data["moved_functions"]
assert moved == ["_classify_constraint_adjusted_recovery"], moved

lt = legacy.read_text(encoding="utf-8")
rt = retries.read_text(encoding="utf-8")
assert "# V132_RETRIES_IMPORT_START" in lt
assert "def _classify_constraint_adjusted_recovery(" not in lt
assert "def _classify_constraint_adjusted_recovery(" in rt

sys.path.insert(0, str(wr))
import wave_batch  # type: ignore
assert hasattr(wave_batch, "run_ro_excel_batch")
assert hasattr(wave_batch, "_classify_constraint_adjusted_recovery")

mod = importlib.import_module("batch.retries")
assert hasattr(mod, "_classify_constraint_adjusted_recovery")

print("V132 wave_batch retries extraction selftest PASS")
print("moved_count=1")
