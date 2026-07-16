#!/usr/bin/env python3
"""V74 hotfix selftest for production-plan RO validator import.

V73 split wave_production_plan.py away from wave_production.py but forgot to
import the RO automation support validator used when expanding ro_excel items.
This lightweight test catches that specific regression without launching WAVE.
"""
from __future__ import annotations

import wave_production_plan
import wave_ro_engine


def main() -> int:
    assert hasattr(wave_production_plan, "_validate_case_automation_support"), (
        "wave_production_plan must import _validate_case_automation_support"
    )
    assert (
        wave_production_plan._validate_case_automation_support
        is wave_ro_engine._validate_case_automation_support
    )
    assert callable(wave_production_plan._validate_case_automation_support)
    print("V74 production plan RO validator import selftest PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
