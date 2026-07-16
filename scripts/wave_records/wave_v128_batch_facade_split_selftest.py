#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import py_compile
import ast

ROOT = Path(__file__).resolve().parents[2]
wave_records = ROOT / "scripts" / "wave_records"

wrapper = wave_records / "wave_batch.py"
legacy = wave_records / "wave_batch_legacy.py"
pkg = wave_records / "batch"

assert wrapper.exists(), wrapper
assert legacy.exists(), legacy
assert pkg.exists(), pkg
assert (pkg / "__init__.py").exists()
assert (pkg / "README_REFACTOR.md").exists()

for p in [
    wrapper,
    legacy,
    pkg / "__init__.py",
    pkg / "plan_schema.py",
    pkg / "resume.py",
    pkg / "artifacts.py",
    pkg / "retries.py",
    pkg / "runner.py",
]:
    assert p.exists(), p
    py_compile.compile(str(p), doraise=True)

wt = wrapper.read_text(encoding="utf-8")
lt = legacy.read_text(encoding="utf-8")

assert "Compatibility facade for wave_batch" in wt
assert "runpy.run_path" in wt
assert "wave_batch_legacy.py" in wt
assert "run_ro_excel_batch" in lt, "legacy should contain old batch implementation"
assert "validate_exported_pdf_case" in lt, "legacy should contain old artifact validation helper"

wrapper_loc = sum(1 for line in wt.splitlines() if line.strip())
legacy_loc = sum(1 for line in lt.splitlines() if line.strip())
assert wrapper_loc < 80, f"wrapper too large: {wrapper_loc}"
assert legacy_loc > 500, f"legacy unexpectedly small: {legacy_loc}"

ast.parse(wt)
ast.parse(lt)

print("V128 wave_batch facade split selftest PASS")
