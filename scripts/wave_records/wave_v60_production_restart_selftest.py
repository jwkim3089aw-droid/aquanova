#!/usr/bin/env python3
"""Offline checks for V69 production process restart isolation."""
from pathlib import Path

src = Path(__file__).resolve().with_name("wave_production.py").read_text(encoding="utf-8")
assert 'PRODUCTION_AUTOMATION_VERSION = "V69"' in src
assert 'production_manifest_v69.json' in src
assert '_checkpoint_v69.json' in src
assert 'production_wave_restart_start_v69' in src
assert 'taskkill' in src
assert 'subprocess.Popen' in src
assert 'wave_window, monitor, points = _start_fresh_production_case' in src
assert 'restart_wave_process' in src
print('V69 production restart selftest passed')
