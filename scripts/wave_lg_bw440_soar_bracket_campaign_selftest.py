#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
V102 = HERE / "wave_lg_bw440_pilot_campaign.py"
V104 = HERE / "wave_lg_bw440_soar_bracket_campaign.py"

if not V102.exists():
    print("V104 SOAR bracket selftest SKIP: V102 generator is not installed yet.")
    print("Apply V102 first, then rerun this selftest.")
    raise SystemExit(0)

spec = importlib.util.spec_from_file_location("wave_lg_bw440_soar_bracket_campaign", V104)
if spec is None or spec.loader is None:
    raise SystemExit("cannot load V104 generator")
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)

v102 = module._load_v102()
plans = module._combine_plans(v102, ["FilmTec™ SOAR 400i", "FilmTec™ SOAR 500i"])
cases = [case for plan in plans.values() for case in plan.get("cases", [])]

assert plans, "no plans generated"
assert cases, "no cases generated"
assert any(case["ccro_element"] == "FilmTec™ SOAR 400i" for case in cases)
assert any(case["ccro_element"] == "FilmTec™ SOAR 500i" for case in cases)
assert all(case["actual_membrane"]["model"] == "LG BW 440 R G2" for case in cases)
assert all(case["ccro_pv_per_stage"] == 1 for case in cases)
assert any(case["ccro_elements_per_pv"] == 3 for case in cases)
assert any(case["ccro_elements_per_pv"] == 4 for case in cases)
assert not any(case.get("ccro_pv_per_stage") == 10 or case.get("ccro_elements_per_pv") == 5 for case in cases)

print("V104 LG BW440 SOAR bracket campaign selftest PASS")
