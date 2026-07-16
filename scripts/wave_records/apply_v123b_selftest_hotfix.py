#!/usr/bin/env python3
from __future__ import annotations

import py_compile
from pathlib import Path

ROOT = Path.cwd().resolve()

required = [
    ROOT / "app/schemas/simulation.py",
    ROOT / "app/api/v1/endpoints/simulation.py",
]

for path in required:
    if not path.exists():
        raise SystemExit(f"missing: {path}")
    py_compile.compile(str(path), doraise=True)

endpoint = (ROOT / "app/api/v1/endpoints/simulation.py").read_text(encoding="utf-8")
schema = (ROOT / "app/schemas/simulation.py").read_text(encoding="utf-8")

if "_v123a_public_precision_report" not in endpoint:
    raise SystemExit("V123A endpoint sanitizer helper is missing. Run apply_v123a again first.")

if "wave_correction_report:" in schema:
    raise SystemExit("legacy schema field still exists: wave_correction_report")

print("V123B selftest hotfix precheck PASS")
print("V123A sanitizer appears installed; this patch only replaces the broken selftest.")
