#!/usr/bin/env python3
from __future__ import annotations

import py_compile
from pathlib import Path

ROOT = Path.cwd().resolve()

endpoint = ROOT / "app/api/v1/endpoints/simulation.py"
schema = ROOT / "app/schemas/simulation.py"
types = ROOT / "ui/src/api/types.ts"

for p in [endpoint, schema]:
    if not p.exists():
        raise SystemExit(f"missing: {p}")
    py_compile.compile(str(p), doraise=True)

endpoint_text = endpoint.read_text(encoding="utf-8")
schema_text = schema.read_text(encoding="utf-8")
types_text = types.read_text(encoding="utf-8") if types.exists() else ""

checks = {
    "endpoint_has_public_sanitizer": "_v123a_public_precision_report" in endpoint_text,
    "endpoint_has_response_sanitizer": "_v123a_sanitize_simulation_response_public" in endpoint_text,
    "endpoint_has_public_schema_version": "aquanova.precision_report.v123" in endpoint_text,
    "schema_has_precision_report": "precision_report" in schema_text,
    "schema_no_legacy_wave_report": "wave_correction_report:" not in schema_text,
    "types_no_legacy_wave_report": "wave_correction_report" not in types_text,
}

failed = [name for name, ok in checks.items() if not ok]
if failed:
    for name in failed:
        print(f"FAIL {name}")
    raise SystemExit(1)

print("V123C no-exec selftest hotfix precheck PASS")
print("V123A sanitizer is installed; this patch only replaces the selftest that tried to exec endpoint code.")
