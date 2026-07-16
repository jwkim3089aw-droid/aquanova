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
manifest_path = wave_records / "batch" / "v130a_artifacts_leaf_extraction_manifest.json"

for p in [legacy, wrapper, artifacts]:
    assert p.exists(), p
    py_compile.compile(str(p), doraise=True)
    ast.parse(p.read_text(encoding="utf-8"))

assert manifest_path.exists(), manifest_path
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
moved = manifest.get("moved_functions", [])
assert len(moved) >= 8, f"too few moved functions: {moved}"
assert "_parse_pdf_summary_number" in moved, "basic helper should be extracted"
assert "_pdf_detect_pass_count" in moved, "leaf helper should be extracted"

legacy_text = legacy.read_text(encoding="utf-8")
artifacts_text = artifacts.read_text(encoding="utf-8")

assert "# V130A_ARTIFACTS_IMPORT_START" in legacy_text
assert "from batch.artifacts import" in legacy_text or "from .batch.artifacts import" in legacy_text

for name in moved:
    assert f"def {name}(" not in legacy_text, f"{name} still defined in legacy"
    assert f"def {name}(" in artifacts_text, f"{name} missing from artifacts"

# Higher-level functions should remain in legacy for now.
assert "def validate_exported_pdf_case(" in legacy_text
assert "def _validate_pdf_recoveries(" in legacy_text
assert "def _extract_pdf_design_warnings(" in legacy_text

sys.path.insert(0, str(wave_records))
import wave_batch  # type: ignore
assert hasattr(wave_batch, "run_ro_excel_batch"), "wave_batch facade lost run_ro_excel_batch"
assert hasattr(wave_batch, "_parse_pdf_summary_number"), "moved helper not re-exported through legacy/facade"

art = importlib.import_module("batch.artifacts")
assert hasattr(art, "_parse_pdf_summary_number")
assert callable(getattr(art, "_parse_pdf_summary_number"))

print("V130A wave_batch artifact leaf extraction selftest PASS")
print(f"moved_count={len(moved)}")
