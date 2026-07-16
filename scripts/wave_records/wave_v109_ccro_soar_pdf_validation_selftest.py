#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / "scripts" / "wave_records" / "wave_ccro.py"

text = TARGET.read_text(encoding="utf-8")
required = [
    "V109: WAVE/PyMuPDF can extract FilmTec",
    "normalized_element_text",
    "element_type_ok",
    '"element_type": element_type_ok',
]
missing = [x for x in required if x not in text]
if missing:
    raise SystemExit(f"V109 selftest FAIL: missing {missing}")

print("V109 CCRO SOAR PDF validation selftest PASS")
