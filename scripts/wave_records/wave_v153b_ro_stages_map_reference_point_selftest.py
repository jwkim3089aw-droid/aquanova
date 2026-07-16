#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
test = ROOT / "scripts" / "wave_records" / "wave_v153_ro_stages_map_reference_point_selftest.py"
proc = subprocess.run([sys.executable, str(test)], cwd=str(ROOT), text=True, capture_output=True)
print(proc.stdout, end="")
if proc.returncode != 0:
    print(proc.stderr, end="")
    raise SystemExit(proc.returncode)
print("V153B wrapper selftest PASS")
