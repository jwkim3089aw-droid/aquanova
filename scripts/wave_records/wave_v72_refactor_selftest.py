#!/usr/bin/env python3
"""Offline checks for the V72 structural refactor."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from wave_calibration_data import CALIBRATION_ORDER, CONTROL_FALLBACK_OFFSETS, DEFAULT_POINTS
from wave_common import CALIBRATION_ORDER as COMMON_CALIBRATION_ORDER
from wave_common import CONTROL_FALLBACK_OFFSETS as COMMON_CONTROL_FALLBACK_OFFSETS
from wave_common import DEFAULT_POINTS as COMMON_DEFAULT_POINTS
from wave_plan_library import build_standard_expansion_plans, write_plan_files
from wave_v70_plan_export import build_plans as build_v70_plans
from wave_v71_plan_export import build_plans as build_v71_plans
from wave_v72_plan_export import build_plans as build_v72_plans


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    _assert(DEFAULT_POINTS is COMMON_DEFAULT_POINTS, "wave_common must re-export DEFAULT_POINTS from wave_calibration_data")
    _assert(CONTROL_FALLBACK_OFFSETS is COMMON_CONTROL_FALLBACK_OFFSETS, "wave_common must re-export fallback offsets")
    _assert(CALIBRATION_ORDER is COMMON_CALIBRATION_ORDER, "wave_common must re-export calibration order")
    for required_key in ("ro_icon", "uf_icon", "ccro_icon", "export_to_pdf"):
        _assert(required_key in DEFAULT_POINTS, f"missing calibration point: {required_key}")

    v70 = build_v70_plans()
    v71 = build_v71_plans()
    v72 = build_v72_plans()
    _assert(len(v70) == 3 and len(v71) == 3 and len(v72) == 3, "each plan kit must emit three plans")
    _assert(any("V70_production_plan_03_mixed_8.json" in name for name in v70), "V70 filename compatibility lost")
    _assert(any("V71_production_plan_03_mixed_8_restart_safe.json" in name for name in v71), "V71 filename compatibility lost")
    _assert(any("V72_production_plan_03_mixed_8_restart_safe.json" in name for name in v72), "V72 plan 03 missing")
    for label, plans in (("V70", v70), ("V71", v71), ("V72", v72)):
        for filename, payload in plans.items():
            _assert(payload.get("schema_version") == 1, f"{filename}: schema_version mismatch")
            _assert(payload.get("fresh_project_per_item") is True, f"{filename}: not restart-safe")
            defaults = payload.get("defaults")
            _assert(isinstance(defaults, dict), f"{filename}: defaults missing")
            _assert(defaults.get("fresh_project_per_item") is True, f"{filename}: default isolation missing")
            cases = payload.get("cases")
            _assert(isinstance(cases, list) and cases, f"{filename}: cases missing")
            if "plan_03" in filename or "production_plan_03" in filename:
                _assert(len(cases) == 5, f"{filename}: plan 03 source case count changed")

    with tempfile.TemporaryDirectory() as tmp:
        paths = write_plan_files(v72, Path(tmp))
        _assert(len(paths) == 3, "write_plan_files did not write three V72 plans")
        loaded = json.loads(paths[-1].read_text(encoding="utf-8"))
        _assert(loaded["plan_kit_version"] == "V72", "written V72 metadata mismatch")

    print("V72 structural refactor selftest PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
