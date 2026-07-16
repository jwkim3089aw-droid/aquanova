#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import ast
import py_compile
import sys

ROOT = Path(__file__).resolve().parents[2]
wave_records = ROOT / "scripts" / "wave_records"

wrapper = wave_records / "wave_ro_engine.py"
legacy = wave_records / "wave_ro_engine_legacy.py"
pkg = wave_records / "ro"

assert wrapper.exists(), wrapper
assert legacy.exists(), legacy
assert pkg.exists(), pkg
assert (pkg / "__init__.py").exists()
assert (pkg / "README_REFACTOR.md").exists()

for p in [
    wrapper,
    legacy,
    pkg / "__init__.py",
    pkg / "case_config.py",
    pkg / "feedwater.py",
    pkg / "membrane.py",
    pkg / "stages.py",
    pkg / "chemicals.py",
    pkg / "reports.py",
    pkg / "runner.py",
]:
    assert p.exists(), p
    py_compile.compile(str(p), doraise=True)
    ast.parse(p.read_text(encoding="utf-8"))

wt = wrapper.read_text(encoding="utf-8")
lt = legacy.read_text(encoding="utf-8")

assert "Compatibility facade for wave_ro_engine" in wt
assert "runpy.run_path" in wt
assert "wave_ro_engine_legacy.py" in wt

# Known public/high-value symbols from the current blueprint.
assert "configure_schema_ro_case" in lt, "legacy should contain old RO implementation"
assert "_apply_chemical_adjustment" in lt, "legacy should contain old chemical adjustment helper"

wrapper_loc = sum(1 for line in wt.splitlines() if line.strip())
legacy_loc = sum(1 for line in lt.splitlines() if line.strip())
assert wrapper_loc < 80, f"wrapper too large: {wrapper_loc}"
assert legacy_loc > 500, f"legacy unexpectedly small: {legacy_loc}"

sys.path.insert(0, str(wave_records))
import wave_ro_engine  # type: ignore
assert hasattr(wave_ro_engine, "configure_schema_ro_case"), "facade lost configure_schema_ro_case"

print("V135 wave_ro_engine facade split selftest PASS")
print("wave_ro_engine import ok", hasattr(wave_ro_engine, "configure_schema_ro_case"))
