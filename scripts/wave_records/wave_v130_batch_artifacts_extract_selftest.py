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
artifacts = wave_records / "batch" / "artifacts.py"
manifest_path = wave_records / "batch" / "v130_artifacts_extraction_manifest.json"

for p in [legacy, wrapper, artifacts]:
    assert p.exists(), p
    py_compile.compile(str(p), doraise=True)
    ast.parse(p.read_text(encoding="utf-8"))

assert manifest_path.exists(), manifest_path
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
moved = manifest.get("moved_functions", [])
assert moved, "no moved functions in manifest"
assert "_parse_pdf_summary_number" in moved, "basic helper should be extracted"

legacy_text = legacy.read_text(encoding="utf-8")
artifacts_text = artifacts.read_text(encoding="utf-8")

assert "# V130_ARTIFACTS_IMPORT_START" in legacy_text
assert "from batch.artifacts import" in legacy_text or "from .batch.artifacts import" in legacy_text

for name in moved:
    assert f"def {name}(" not in legacy_text, f"{name} still defined in legacy"
    assert f"def {name}(" in artifacts_text, f"{name} missing from artifacts"

sys.path.insert(0, str(wave_records))
import wave_batch  # type: ignore
assert hasattr(wave_batch, "run_ro_excel_batch"), "wave_batch facade lost run_ro_excel_batch"
assert hasattr(wave_batch, "_parse_pdf_summary_number"), "moved helper not re-exported through legacy/facade"

art = importlib.import_module("batch.artifacts")
assert hasattr(art, "_parse_pdf_summary_number")
assert callable(getattr(art, "_parse_pdf_summary_number"))

print("V130 wave_batch artifacts extraction selftest PASS")
print(f"moved_count={len(moved)}")
