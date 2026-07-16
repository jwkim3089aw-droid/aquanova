#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]

tests = [
    ROOT / "scripts" / "wave_records" / "wave_v140_ro_stages_stage_grid_points_selftest.py",
    ROOT / "scripts" / "wave_records" / "wave_v145a_ro_stages_stabilize_after_flow_commit_selftest.py",
    ROOT / "scripts" / "wave_records" / "wave_v148_ro_stages_select_and_count_selftest.py",
]

for test in tests:
    assert test.exists(), test
    proc = subprocess.run([sys.executable, str(test)], cwd=str(ROOT), text=True, capture_output=True)
    print(proc.stdout, end="")
    if proc.returncode != 0:
        print(proc.stderr, end="")
        raise SystemExit(proc.returncode)

print("V148A RO stages selftest compatibility selftest PASS")
