#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
planner = ROOT / "scripts" / "wave_records" / "aquanova_v146_ro_bridge_candidate_plan.py"
out = ROOT / ".refactor_blueprint" / "v146_ro_bridge_candidates"

assert planner.exists(), planner

proc = subprocess.run([sys.executable, str(planner)], cwd=str(ROOT), text=True, capture_output=True)
print(proc.stdout, end="")
if proc.returncode != 0:
    print(proc.stderr, end="")
    raise SystemExit(proc.returncode)

summary = out / "RO_BRIDGE_AWARE_EXTRACTION_PLAN.md"
csv_path = out / "ro_bridge_candidates.csv"
json_path = out / "ro_bridge_candidates.json"

assert summary.exists(), summary
assert csv_path.exists(), csv_path
assert json_path.exists(), json_path

text = summary.read_text(encoding="utf-8", errors="ignore")
assert "V146 RO bridge-aware extraction planner" in text
assert "Recommended bridge-aware candidates" in text
assert "Blocked by unknown globals" in text

print("V146 RO bridge-aware extraction planner selftest PASS")
