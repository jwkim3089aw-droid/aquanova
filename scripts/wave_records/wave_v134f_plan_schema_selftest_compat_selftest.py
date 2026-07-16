#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import py_compile

ROOT = Path(__file__).resolve().parents[2]
target = ROOT / "scripts" / "wave_records" / "wave_v134d_batch_plan_schema_self_contained_selftest.py"
assert target.exists(), target
py_compile.compile(str(target), doraise=True)
text = target.read_text(encoding="utf-8")
assert "V134F/V134D-compatible" in text
assert "# V134E WaveAutomationError bridge" in text
print("V134F selftest compatibility hotfix selftest PASS")
