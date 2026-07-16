#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import py_compile


def resolve_project_root() -> Path:
    here = Path(__file__).resolve().parent
    if (here / "scripts" / "wave_records" / "wave_ccro.py").exists():
        return here
    if here.name == "wave_records" and (here / "wave_ccro.py").exists():
        return here.parents[1]
    cwd = Path.cwd().resolve()
    if (cwd / "scripts" / "wave_records" / "wave_ccro.py").exists():
        return cwd
    raise SystemExit("Cannot find AquaNova project root. Run from C:\\Users\\a\\Desktop\\프로젝트\\AquaNova\\code")


ROOT = resolve_project_root()
WAVE_CCRO = ROOT / "scripts" / "wave_records" / "wave_ccro.py"
text = WAVE_CCRO.read_text(encoding="utf-8")

required = [
    "stage_flow_factor: float,\n    pf_feed_ratio_pct: float | None = None,\n    pf_recovery_pct: float | None = None,\n) -> dict[str, Any]:",
    "pf_feed_ratio_pct=pf_feed_ratio_pct,\n        pf_recovery_pct=pf_recovery_pct,",
    '"pf_feed_ratio_pct": pf_feed_ratio_pct',
    "case.pf_feed_ratio_pct = float(pf_feed_ratio_pct)",
    "pf_feed_ratio_pct=case.pf_feed_ratio_pct",
]
missing = [x for x in required if x not in text]
if missing:
    raise SystemExit(f"V112 selftest FAIL: missing patterns: {missing}")

py_compile.compile(str(WAVE_CCRO), doraise=True)
print("V112 CCRO selected-pass PF signature selftest PASS")
