#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
GENERATOR = SCRIPTS / "wave_lg_bw440_soar_bracket_campaign.py"
PLAN_DIR = SCRIPTS / "wave_records"

if not GENERATOR.exists():
    raise SystemExit(f"missing generator: {GENERATOR}")

text = GENERATOR.read_text(encoding="utf-8")
if 'new_plan["schema_version"] = 1' not in text and '"schema_version": 1' not in text:
    raise SystemExit("V104 generator still does not set production schema_version=1")

plans = sorted(PLAN_DIR.glob("AquaNova_WAVE_V104_LG_BW440_SOAR_BRACKET_*.json"))
if not plans:
    print("V106 selftest PASS: generator patched; no existing V104 plans to inspect")
    raise SystemExit(0)

bad = []
for path in plans:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != 1:
        bad.append((path.name, data.get("schema_version")))
    cases = data.get("cases") or []
    for case in cases:
        if case.get("ccro_pv_per_stage") != 1:
            bad.append((path.name, "ccro_pv_per_stage", case.get("ccro_pv_per_stage")))
        if case.get("ccro_elements_per_pv") not in (3, 4):
            bad.append((path.name, "ccro_elements_per_pv", case.get("ccro_elements_per_pv")))

if bad:
    raise SystemExit(f"V106 selftest FAIL: {bad[:10]}")

print(f"V106 V104 schema selftest PASS; inspected_plan_count={len(plans)}")
