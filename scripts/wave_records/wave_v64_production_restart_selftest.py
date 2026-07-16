#!/usr/bin/env python3
"""Offline checks for V69 production restart/UF validation changes."""
from pathlib import Path

root = Path(__file__).resolve().parent
prod = (root / "wave_production.py").read_text(encoding="utf-8")
uf = (root / "wave_uf.py").read_text(encoding="utf-8")

required_prod = [
    'PRODUCTION_AUTOMATION_VERSION = "V69"',
    'production_manifest_v69.json',
    '_wait_for_restarted_wave_main_window',
    '_is_wave_splash_window',
    'production_wave_main_window_acquired_v69',
    'checkpoint_v69.json',
]
missing = [m for m in required_prod if m not in prod]
if missing:
    raise SystemExit(f"V69 production restart markers missing: {missing}")

required_uf = [
    'water_profile',
    'hard_fields = (',
    'UF V69 combines PDF evidence with the applied input path',
    'uf_pdf_validation_v69',
]
for marker in required_uf:
    if marker not in uf:
        raise SystemExit(f"UF V69 marker missing: {marker}")

hard_block = uf.split('hard_fields = (', 1)[1].split(')', 1)[0]
if 'water_profile' in hard_block:
    raise SystemExit('water_profile must not be a hard UF PDF failure in V69')

print("V69 production restart selftest PASS")
