#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WR = ROOT / "scripts" / "wave_records"

checks = {
    "wave_ccro.py": [
        "pf_feed_ratio_pct: float = 120.0",
        "pf_recovery_pct: float = 20.0",
        "pf_feed_ratio_pct=case.pf_feed_ratio_pct",
        "pf_recovery_pct=case.pf_recovery_pct",
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
        "$pfRatioTarget",
        "txtFeedRatio",
        "txtPFRecovery",
        "pf_results=$pfSetResults",
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
    raise SystemExit(f"V110 selftest FAIL: {missing[:20]}")

print("V110 CCRO PF Feed Ratio passthrough selftest PASS")
