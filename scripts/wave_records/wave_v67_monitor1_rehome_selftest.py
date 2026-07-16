#!/usr/bin/env python3
"""Offline checks for V69 monitor-agnostic relaunch acquisition."""
from pathlib import Path

root = Path(__file__).resolve().parent
prod = (root / "wave_production.py").read_text(encoding="utf-8")
win = (root / "wave_windows.py").read_text(encoding="utf-8")

required_prod = [
    'PRODUCTION_AUTOMATION_VERSION = "V69"',
    'def _wave_identity_from_title_class_path',
    'acquisition_policy="any_monitor_then_move"',
    'acquired_after_old_gone',
    'title_l.startswith("untitled project")',
    'WAVE relaunches on the Windows primary monitor (display 1)',
    'move_window_to_monitor(new_window.hwnd, desired_monitor, maximize=True)',
    'production_wave_main_window_acquired_v69',
]
missing = [m for m in required_prod if m not in prod]
if missing:
    raise SystemExit(f"V69 monitor-agnostic reacquire markers missing: {missing}")

if 'if "wave.exe" not in path:\n        return False' in prod:
    raise SystemExit("V69 must not reject WAVE main candidates solely because process_path is temporarily empty")

if 'wave_window_moved_to_monitor_v69' not in win:
    raise SystemExit("V69 monitor move marker missing from wave_windows.py")

print("V69 monitor1 rehome selftest PASS")
