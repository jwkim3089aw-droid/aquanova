#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
MOD = HERE / "wave_lg_bw440_pilot_campaign.py"

spec = importlib.util.spec_from_file_location("wave_lg_bw440_pilot_campaign", MOD)
if spec is None or spec.loader is None:
    raise SystemExit("cannot load wave_lg_bw440_pilot_campaign.py")
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)

plans = module._build_plans("LG BW 440 R G2")
assert len(plans) == 4, len(plans)
all_cases = [case for plan in plans.values() for case in plan["cases"]]
assert len(all_cases) == 19, len(all_cases)
assert all(case["kind"] == "ccro_video" for case in all_cases)
assert all(case["ccro_pv_per_stage"] == 1 for case in all_cases)
assert any(case["elements_per_pv"] == 3 for case in all_cases)
assert any(case["elements_per_pv"] == 4 for case in all_cases)
assert all(case["actual_membrane"]["model"] == "LG BW 440 R G2" for case in all_cases)
assert all(case["actual_membrane"]["active_area_m2"] == 41 for case in all_cases)
# Guard against the V100/V101 problem: no plan case should fall back to 10 x 5.
assert not any(case.get("pv_per_stage") == 10 or case.get("elements_per_pv") == 5 for case in all_cases)
rows = module._handcalc_rows()
assert len(rows) == 8
fr150_3e = [r for r in rows if r["installed_elements"] == 3 and r["pf_feed_ratio_pct"] == 150.0][0]
assert abs(fr150_3e["estimated_flux_lmh"] - 14.7967) < 0.01
assert abs(fr150_3e["q_pf_feed_m3h"] - 2.73) < 0.001
print("V102 LG BW440 pilot campaign selftest PASS")
