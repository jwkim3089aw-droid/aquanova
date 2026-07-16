#!/usr/bin/env python3
"""Probe installed V94/V95 runtime correction layer on a synthetic result.

This does not run a full AquaNova scenario.  It checks whether the installed
.data layer/config can be loaded and whether explicit opt-in applies corrections
through the V95 engine-facing bridge.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.simulation.wave_corrected_engine import maybe_apply_wave_correction  # noqa: E402


def _synthetic_output() -> dict:
    return {
        "streams": [
            {"label": "Product", "flow_m3h": 1.82, "tds_mgL": 9.3},
            {"label": "Brine", "flow_m3h": 0.20, "tds_mgL": 4040.0},
        ],
        "kpi": {"recovery_pct": 90.0, "flux_lmh": 16.3, "sec_kwhm3": 0.34, "prod_tds": 9.3},
        "stage_metrics": [
            {"stage": 1, "module_type": "HRRO", "p_in_bar": 9.94, "chemistry": {"ccro_cycle": {"pf_feed_ratio_pct": 270.0}}}
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="V95 installed runtime correction probe")
    parser.add_argument("--enable", action="store_true", help="Force explicit runtime opt-in for the probe.")
    parser.add_argument("--print-json", action="store_true")
    args = parser.parse_args()

    corrected, report = maybe_apply_wave_correction(
        _synthetic_output(),
        options={"enable_wave_correction": bool(args.enable)},
    )
    print("V95 runtime probe")
    print("status=" + str(report.get("status")))
    print("applied_count=" + str(report.get("applied_count")))
    if corrected.get("stage_metrics"):
        print("feed_pressure_bar=" + str(corrected["stage_metrics"][0].get("p_in_bar")))
    print("sec_kwhm3=" + str((corrected.get("kpi") or {}).get("sec_kwhm3")))
    if args.print_json:
        print(json.dumps({"report": report, "corrected": corrected}, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
