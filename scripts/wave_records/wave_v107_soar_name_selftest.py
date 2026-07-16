#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
GENERATOR = SCRIPTS / "wave_lg_bw440_soar_bracket_campaign.py"
PLAN_DIR = SCRIPTS / "wave_records"

if GENERATOR.exists():
    text = GENERATOR.read_text(encoding="utf-8")
    bad = ["FilmTec™ SOAR 400i", "FilmTec™ SOAR 500i", "SOAR400i", "SOAR500i"]
    found = [x for x in bad if x in text]
    if found:
        raise SystemExit(f"V107 selftest FAIL: old SOAR names still in generator: {found}")
    if "FilmTec™ SOAR 4000i" not in text or "FilmTec™ SOAR 5000i" not in text:
        raise SystemExit("V107 selftest FAIL: expected SOAR 4000i/5000i not found in generator")
else:
    print(f"generator_missing_warning: {GENERATOR}")

plans = sorted(PLAN_DIR.glob("AquaNova_WAVE_V104_LG_BW440_SOAR_BRACKET_*.json"))
bad_plans = []
seen_elements = set()

for path in plans:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != 1:
        bad_plans.append((path.name, "schema_version", data.get("schema_version")))
    blob = json.dumps(data, ensure_ascii=False)
    for old in ("FilmTec™ SOAR 400i", "FilmTec™ SOAR 500i", "SOAR400i", "SOAR500i"):
        if old in blob:
            bad_plans.append((path.name, "old_name", old))
    for case in data.get("cases") or []:
        if case.get("ccro_element"):
            seen_elements.add(case["ccro_element"])
        if case.get("ccro_pv_per_stage") != 1:
            bad_plans.append((path.name, "ccro_pv_per_stage", case.get("ccro_pv_per_stage")))
        if case.get("ccro_elements_per_pv") not in (3, 4):
            bad_plans.append((path.name, "ccro_elements_per_pv", case.get("ccro_elements_per_pv")))

if bad_plans:
    raise SystemExit(f"V107 selftest FAIL: {bad_plans[:10]}")

if plans and not {"FilmTec™ SOAR 4000i", "FilmTec™ SOAR 5000i"}.issubset(seen_elements):
    raise SystemExit(f"V107 selftest FAIL: expected both SOAR 4000i and 5000i in plans, saw {sorted(seen_elements)}")

print(f"V107 SOAR 4000/5000 name selftest PASS; inspected_plan_count={len(plans)}")
