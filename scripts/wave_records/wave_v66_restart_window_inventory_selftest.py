#!/usr/bin/env python3
"""Offline V69 checks for restart main-window inventory fallback."""
from pathlib import Path

root = Path(__file__).resolve().parent
prod = (root / "wave_production.py").read_text(encoding="utf-8")
runtime = (root / "wave_runtime.py").read_text(encoding="utf-8")

required = [
    'PRODUCTION_AUTOMATION_VERSION = "V69"',
    'def _enum_wave_windows_raw()',
    'def _raw_wave_window_info',
    'production_wave_wait_inventory_v69',
    'production_wave_main_window_timeout_v69',
    'raw_wave_windows=',
    'timeout_s=120.0',
    '_get_class_name',
]
missing = [marker for marker in required if marker not in prod]
if missing:
    raise SystemExit(f"V69 restart inventory markers missing: {missing}")

if 'rect is None or rect.width < 900 or rect.height < 650' in prod:
    raise SystemExit('V69 must not reject minimized/small WAVE main HWNDs before title/class checks')
if '"automation_version": "V69"' not in runtime:
    raise SystemExit('source manifest automation_version must be V69')

print("V69 restart window inventory selftest PASS")
