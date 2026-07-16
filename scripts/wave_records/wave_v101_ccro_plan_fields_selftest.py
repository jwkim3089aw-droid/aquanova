#!/usr/bin/env python3
r"""Selftest for V101 CCRO plan field passthrough hotfix.

Run from project root:
    python .\scripts\wave_records\wave_v101_ccro_plan_fields_selftest.py
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WAVE_DIR = ROOT / "scripts" / "wave_records"


def _require(path: Path, needles: list[str]) -> None:
    if not path.exists():
        raise AssertionError(f"missing file: {path}")
    text = path.read_text(encoding="utf-8")
    for needle in needles:
        if needle not in text:
            raise AssertionError(f"missing marker in {path.name}: {needle}")


def main() -> int:
    _require(
        WAVE_DIR / "wave_ccro.py",
        [
            "# V101 PLAN FIELD PASSTHROUGH",
            "pv_per_stage: int | float | str | None = None",
            "case.pv_per_stage = max(1, int(float(pv_per_stage)))",
            "case.elements_per_pv = max(1, int(float(elements_per_pv)))",
        ],
    )
    _require(
        WAVE_DIR / "wave_production.py",
        [
            "# V101 PLAN FIELD PASSTHROUGH",
            "raw.get(\"ccro_pv_per_stage\")",
            "raw.get(\"ccro_elements_per_pv\")",
        ],
    )

    v100_plan = WAVE_DIR / "AquaNova_WAVE_V100_260709_01_fr_pump_energy_sweep.json"
    if v100_plan.exists():
        data = json.loads(v100_plan.read_text(encoding="utf-8"))
        first = data.get("cases", [{}])[0]
        pv = first.get("pv_per_stage") or first.get("ccro_pv_per_stage")
        els = first.get("elements_per_pv") or first.get("ccro_elements_per_pv")
        if str(pv) not in {"1", "1.0"} or str(els) not in {"3", "3.0"}:
            raise AssertionError(
                f"V100 first plan does not look like pilot geometry: pv={pv!r}, elements={els!r}"
            )
        print(f"V100 pilot geometry present in plan: pv_per_stage={pv}, elements_per_pv={els}")

    print("V101 CCRO plan field passthrough selftest PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
