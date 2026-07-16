#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLAN_DIR = ROOT / "scripts" / "wave_records"
plans = sorted(PLAN_DIR.glob("AquaNova_WAVE_V104_LG_BW440_SOAR_BRACKET_*.json"))

if not plans:
    print("V108 selftest PASS: no V104 plans found to inspect")
    raise SystemExit(0)

bad = []
pdf_names = []
for path in plans:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != 1:
        bad.append((path.name, "schema_version", data.get("schema_version")))
    for case in data.get("cases") or []:
        elem = str(case.get("ccro_element") or "")
        name = str(case.get("ccro_pdf_name") or case.get("pdf_name") or "")
        if "SOAR 4000i" in elem and "SOAR4000i" not in name:
            bad.append((path.name, case.get("key"), "missing_SOAR4000i_pdf_tag", name))
        if "SOAR 5000i" in elem and "SOAR5000i" not in name:
            bad.append((path.name, case.get("key"), "missing_SOAR5000i_pdf_tag", name))
        if name:
            pdf_names.append(name)

if bad:
    raise SystemExit(f"V108 selftest FAIL: {bad[:10]}")

dupes = sorted({x for x in pdf_names if pdf_names.count(x) > 1})
if dupes:
    raise SystemExit(f"V108 selftest FAIL: duplicate pdf names still present: {dupes[:10]}")

print(f"V108 SOAR PDF naming selftest PASS; inspected_plan_count={len(plans)} pdf_count={len(pdf_names)}")
