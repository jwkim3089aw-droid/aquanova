#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]

tests = [
    ROOT / "scripts" / "wave_records" / "wave_v142_ro_case_config_capture_state_selftest.py",
    ROOT / "scripts" / "wave_records" / "wave_v143a_ro_case_config_verify_inputs_selftest.py",
    ROOT / "scripts" / "wave_records" / "wave_v149_ro_case_config_validate_support_selftest.py",
]

for test in tests:
    assert test.exists(), test
    proc = subprocess.run([sys.executable, str(test)], cwd=str(ROOT), text=True, capture_output=True)
    print(proc.stdout, end="")
    if proc.returncode != 0:
        print(proc.stderr, end="")
        raise SystemExit(proc.returncode)

print("V149A RO case_config selftest compatibility selftest PASS")
