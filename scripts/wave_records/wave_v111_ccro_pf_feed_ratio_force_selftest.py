#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path


def resolve_project_root() -> Path:
    here = Path(__file__).resolve().parent
    if (here / "scripts" / "wave_records").exists():
        return here
    if here.name == "wave_records" and (here / "wave_ccro.py").exists():
        return here.parents[1]
    cwd = Path.cwd().resolve()
    if (cwd / "scripts" / "wave_records").exists():
        return cwd
    raise SystemExit("Cannot find AquaNova project root. Run from C:\\Users\\a\\Desktop\\프로젝트\\AquaNova\\code")


ROOT = resolve_project_root()
WR = ROOT / "scripts" / "wave_records"

checks = {
    "wave_ccro.py": [
        "pf_feed_ratio_pct: float = 120.0",
        "pf_recovery_pct: float = 20.0",
        "pf_feed_ratio_pct=case.pf_feed_ratio_pct",
        "case.pf_feed_ratio_pct = float(pf_feed_ratio_pct)",
        "target_pf_feed_ratio_pct",
    ],
    "wave_production.py": [
        "pf_feed_ratio_pct=(",
        'raw.get("ccro_pf_feed_ratio_pct")',
        "pf_recovery_pct=(",
        'raw.get("ccro_pf_recovery_pct")',
    ],
    "wave_dialogs.py": [
        "pf_feed_ratio_pct: float | str | None = None",
        "pass_index: int = 1",
        "pf_feed_ratio_pct=pf_feed_ratio_pct",
    ],
    "wave_uia.py": [
        "$pfRatioTarget = {pf_ratio_ps}",
        "txtFeedRatio",
        "txtPFRecovery",
        "pf_results=$pfSetResults",
        "V111: set CCRO PF Cycle values",
    ],
}

missing = []
for filename, needles in checks.items():
    path = WR / filename
    if not path.exists():
        missing.append((filename, "file_missing"))
        continue
    text = path.read_text(encoding="utf-8")
    for needle in needles:
        if needle not in text:
            missing.append((filename, needle))

if missing:
    raise SystemExit(f"V111 selftest FAIL: {missing[:20]}")

print("V111 CCRO PF Feed Ratio force patch selftest PASS")
