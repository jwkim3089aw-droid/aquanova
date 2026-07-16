#!/usr/bin/env python3
"""Offline checks for V69 production restart monitor targeting."""
from pathlib import Path

root = Path(__file__).resolve().parent
prod = (root / "wave_production.py").read_text(encoding="utf-8")
cli = (root / "wave_cli.py").read_text(encoding="utf-8")
win = (root / "wave_windows.py").read_text(encoding="utf-8")

assert 'PRODUCTION_AUTOMATION_VERSION = "V69"' in prod
assert 'restart_monitor_index' in prod
assert 'move_window_to_monitor(new_window.hwnd, desired_monitor' in prod
assert 'resolve_monitor_rect_by_index(target_monitor_index' in prod
assert 'target_monitor_rect=restart_target_monitor' in prod
assert '--production-restart-monitor-index' in cli
assert 'restart_monitor_index=args.production_restart_monitor_index' in cli
assert 'def list_monitor_rects()' in win
assert 'def move_window_to_monitor(' in win
assert 'wave_window_moved_to_monitor_v69' in win
print('V69 production monitor targeting selftest passed')
