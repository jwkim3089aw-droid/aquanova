"""Offline checks for V69 black WPF placeholder rejection."""
from pathlib import Path

root = Path(__file__).resolve().parent
prod = (root / "wave_production.py").read_text(encoding="utf-8")
runtime = (root / "wave_runtime.py").read_text(encoding="utf-8")

required = [
    'PRODUCTION_AUTOMATION_VERSION = "V69"',
    'production_manifest_v69.json',
    'production_wave_main_window_acquired_v69',
    'production_wave_wait_inventory_v69',
    'production_wave_main_window_timeout_v69',
    'wave_window_moved_to_monitor_v69',
    '_raw_wave_row_is_ready_enough_for_candidate',
    'rect.width < 700 or rect.height < 450',
    'Never accept a title-empty WPF',
    'splash_present',
]
missing = [m for m in required if m not in prod and m not in (root / "wave_windows.py").read_text(encoding="utf-8")]
if missing:
    raise SystemExit(f"V69 black-placeholder guards missing: {missing}")

if 'if class_wave or title_main:\n        return True' in prod:
    raise SystemExit('V69 must not accept title-empty HwndWrapper solely by class')
if 'rect.width < 700 or rect.height < 450' not in prod:
    raise SystemExit('V69 must reject tiny 136x39 startup wrappers')
if 'if candidates and not splash_present:' not in prod:
    raise SystemExit('V69 must not acquire a main candidate while splash is still present')
if '"automation_version": "V69"' not in runtime:
    raise SystemExit('source manifest automation_version must be V69')

print('V69 black placeholder selftest PASS')
