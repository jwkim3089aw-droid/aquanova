#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import py_compile


def resolve_project_root() -> Path:
    here = Path(__file__).resolve().parent
    if (here / "scripts" / "wave_records" / "wave_ccro.py").exists():
        return here
    if (here / "wave_records" / "wave_ccro.py").exists():
        return here.parent
    cwd = Path.cwd().resolve()
    if (cwd / "scripts" / "wave_records" / "wave_ccro.py").exists():
        return cwd
    raise SystemExit("Cannot find AquaNova project root. Run from C:\\Users\\a\\Desktop\\프로젝트\\AquaNova\\code")


ROOT = resolve_project_root()
WAVE_CCRO = ROOT / "scripts" / "wave_records" / "wave_ccro.py"


def main() -> int:
    if not WAVE_CCRO.exists():
        raise SystemExit(f"missing target: {WAVE_CCRO}")

    text = WAVE_CCRO.read_text(encoding="utf-8")
    changed = False

    # V112 fixes the partial V111 state:
    # callers pass pf_feed_ratio_pct/pf_recovery_pct, but
    # _configure_ccro_selected_pass_fields did not accept them.
    if "stage_flow_factor: float,\n    pf_feed_ratio_pct: float | None = None,\n    pf_recovery_pct: float | None = None,\n) -> dict[str, Any]:" not in text:
        old = """    stage_back_pressure_bar: float,
    stage_flow_factor: float,
) -> dict[str, Any]:
"""
        new = """    stage_back_pressure_bar: float,
    stage_flow_factor: float,
    pf_feed_ratio_pct: float | None = None,
    pf_recovery_pct: float | None = None,
) -> dict[str, Any]:
"""
        if old not in text:
            raise SystemExit("pattern_not_found: selected pass signature")
        text = text.replace(old, new, 1)
        changed = True
        print("patched: selected pass signature accepts PF fields")
    else:
        print("already ok: selected pass signature accepts PF fields")

    # Ensure the accepted fields are actually forwarded into the Flow Calculator dialog.
    if "pf_feed_ratio_pct=pf_feed_ratio_pct,\n        pf_recovery_pct=pf_recovery_pct," not in text[text.find("flow_result = _configure_ccro_flow_calculator("): text.find("screenshot(f\"ccro_pass{pass_index}_configured_v55\"")]:
        old = """    flow_result = _configure_ccro_flow_calculator(
        hwnd, monitor, points, recovery_pct, settings, pass_label
    )
"""
        new = """    flow_result = _configure_ccro_flow_calculator(
        hwnd,
        monitor,
        points,
        recovery_pct,
        settings,
        pass_label,
        pf_feed_ratio_pct=pf_feed_ratio_pct,
        pf_recovery_pct=pf_recovery_pct,
    )
"""
        if old not in text:
            raise SystemExit("pattern_not_found: selected pass flow calculator call")
        text = text.replace(old, new, 1)
        changed = True
        print("patched: selected pass forwards PF fields to flow calculator")
    else:
        print("already ok: selected pass forwards PF fields to flow calculator")

    # Add target PF fields to the pass summary for easier diagnostics.
    if '"pf_feed_ratio_pct": pf_feed_ratio_pct' not in text:
        old = """        "flow_factor": flow_factor,
        "element_before_flow_calculator_v86": True,
"""
        new = """        "flow_factor": flow_factor,
        "pf_feed_ratio_pct": pf_feed_ratio_pct,
        "pf_recovery_pct": pf_recovery_pct,
        "element_before_flow_calculator_v86": True,
"""
        if old not in text:
            raise SystemExit("pattern_not_found: selected pass return summary")
        text = text.replace(old, new, 1)
        changed = True
        print("patched: selected pass return summary includes PF fields")
    else:
        print("already ok: selected pass return summary includes PF fields")

    if changed:
        WAVE_CCRO.write_text(text, encoding="utf-8")
        print(f"patched file: {WAVE_CCRO}")

    py_compile.compile(str(WAVE_CCRO), doraise=True)
    print("V112 CCRO selected-pass PF signature hotfix applied")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
