#!/usr/bin/env python3
r"""V101 hotfix: make CCRO production plans actually pass vessel/element fields.

Run from project root:
    python .\scripts\apply_v101_ccro_plan_fields_hotfix.py

Why this exists:
V100 meeting plans wrote pilot geometry keys such as pv_per_stage=1 and
ccro_elements_per_pv=3, but older wave_production.py only forwarded element,
pdf, water, feed flow, recovery, pass count, and pass2 recovery into
run_ccro_video_case().  wave_ccro.py then fell back to its conservative default
10 PV x 5 elements, which can make small pilot cases slow/hang in WAVE.

This script patches:
    scripts/wave_records/wave_ccro.py
    scripts/wave_records/wave_production.py

It is idempotent and writes .v101.bak backups before modifying files.
"""
from __future__ import annotations

import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WAVE_DIR = ROOT / "scripts" / "wave_records"
WAVE_CCRO = WAVE_DIR / "wave_ccro.py"
WAVE_PRODUCTION = WAVE_DIR / "wave_production.py"


def _backup(path: Path) -> None:
    backup = path.with_suffix(path.suffix + ".v101.bak")
    if not backup.exists():
        shutil.copy2(path, backup)


def _patch_wave_ccro(text: str) -> tuple[str, bool]:
    changed = False

    if "# V101 PLAN FIELD PASSTHROUGH" not in text:
        # Add new keyword arguments immediately after pass2_recovery_pct.
        old_sig = "    pass2_recovery_pct: float | None = None,\n) -> list[Path]:"
        new_sig = """    pass2_recovery_pct: float | None = None,
    pv_per_stage: int | float | str | None = None,
    elements_per_pv: int | float | str | None = None,
    flow_factor: float | str | None = None,
    pass_back_pressure_bar: float | str | None = None,
    stage_back_pressure_bar: float | str | None = None,
    stage_flow_factor: float | str | None = None,
    pass2_pv_per_stage: int | float | str | None = None,
    pass2_elements_per_pv: int | float | str | None = None,
) -> list[Path]:"""
        if old_sig not in text:
            raise RuntimeError(
                "wave_ccro.py signature pattern not found. The file may have changed; "
                "inspect run_ccro_video_case() manually."
            )
        text = text.replace(old_sig, new_sig)

        marker = "    if pass2_recovery_pct is not None:\n        case.pass2_recovery_pct = float(pass2_recovery_pct)\n"
        insert = marker + """

    # V101 PLAN FIELD PASSTHROUGH
    # Production plans can now override the conservative CCRO defaults
    # (10 PV x 5 elements).  This is critical for pilot-scale meeting tests,
    # where the intended geometry is 1 PV x 3 elements.
    if pv_per_stage is not None:
        case.pv_per_stage = max(1, int(float(pv_per_stage)))
    if elements_per_pv is not None:
        case.elements_per_pv = max(1, int(float(elements_per_pv)))
    if flow_factor is not None:
        case.flow_factor = float(flow_factor)
        case.pass2_flow_factor = float(flow_factor)
        case.pass2_stage_flow_factor = float(flow_factor)
    if pass_back_pressure_bar is not None:
        case.pass_back_pressure_bar = float(pass_back_pressure_bar)
        case.pass2_back_pressure_bar = float(pass_back_pressure_bar)
    if stage_back_pressure_bar is not None:
        case.pass_back_pressure_bar = float(stage_back_pressure_bar)
        case.pass2_stage_back_pressure_bar = float(stage_back_pressure_bar)
    if stage_flow_factor is not None:
        case.flow_factor = float(stage_flow_factor)
        case.pass2_stage_flow_factor = float(stage_flow_factor)
    if pass2_pv_per_stage is not None:
        case.pass2_pv_per_stage = max(1, int(float(pass2_pv_per_stage)))
    if pass2_elements_per_pv is not None:
        case.pass2_elements_per_pv = max(1, int(float(pass2_elements_per_pv)))
"""
        if marker not in text:
            raise RuntimeError(
                "wave_ccro.py assignment insertion point not found. The file may have changed; "
                "inspect run_ccro_video_case() manually."
            )
        text = text.replace(marker, insert)
        changed = True

    return text, changed


def _patch_wave_production(text: str) -> tuple[str, bool]:
    changed = False
    if "# V101 PLAN FIELD PASSTHROUGH" not in text:
        old = "            pass2_recovery_pct=raw.get(\"pass2_recovery_pct\") or raw.get(\"ccro_pass2_recovery\"),\n        )"
        new = """            pass2_recovery_pct=raw.get("pass2_recovery_pct") or raw.get("ccro_pass2_recovery"),
            # V101 PLAN FIELD PASSTHROUGH
            pv_per_stage=(raw.get("pv_per_stage") or raw.get("ccro_pv_per_stage") or raw.get("pvs_per_stage")),
            elements_per_pv=(raw.get("elements_per_pv") or raw.get("ccro_elements_per_pv") or raw.get("elements_per_vessel")),
            flow_factor=(raw.get("flow_factor") or raw.get("ccro_flow_factor") or raw.get("ro_flow_factor")),
            pass_back_pressure_bar=(raw.get("pass_back_pressure_bar") or raw.get("ccro_pass_back_pressure_bar") or raw.get("ro_pass_back_pressure")),
            stage_back_pressure_bar=(raw.get("stage_back_pressure_bar") or raw.get("ccro_stage_back_pressure_bar") or raw.get("stage_back_pressure_row")),
            stage_flow_factor=(raw.get("stage_flow_factor") or raw.get("ccro_stage_flow_factor") or raw.get("stage_flow_factor_row")),
            pass2_pv_per_stage=(raw.get("pass2_pv_per_stage") or raw.get("ccro_pass2_pv_per_stage")),
            pass2_elements_per_pv=(raw.get("pass2_elements_per_pv") or raw.get("ccro_pass2_elements_per_pv")),
        )"""
        if old not in text:
            raise RuntimeError(
                "wave_production.py CCRO return pattern not found. The file may have changed; "
                "inspect the ccro_video branch manually."
            )
        text = text.replace(old, new)
        changed = True
    return text, changed


def main() -> int:
    for path in [WAVE_CCRO, WAVE_PRODUCTION]:
        if not path.exists():
            raise SystemExit(f"필수 파일이 없습니다: {path}")

    for path, patcher in [(WAVE_CCRO, _patch_wave_ccro), (WAVE_PRODUCTION, _patch_wave_production)]:
        original = path.read_text(encoding="utf-8")
        patched, changed = patcher(original)
        if changed:
            _backup(path)
            path.write_text(patched, encoding="utf-8")
            print(f"patched: {path}")
        else:
            print(f"already patched: {path}")

    print("V101 CCRO plan field passthrough hotfix applied")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
