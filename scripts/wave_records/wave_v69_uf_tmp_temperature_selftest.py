#!/usr/bin/env python3
"""Offline V69 checks for UF TMP temperature validation when max row is omitted."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import wave_uf
from wave_uf import UFVideoCase, validate_exported_uf_pdf


def main() -> int:
    sample_text = """
    UF Summary Report
    Ultrafiltration SFP-2660
    Gross Feed = 100.0 m3/h
    Online = 1 Standby = 0 Redundant = 0
    Per Train = 24 Total = 24
    UF System Recovery (%) 99.48
    TMP
    (bar)
    1.06 @ 10.0 °C
    0.92 @ 15.0 °C
    Utility Water
    Forward Flush:
    Pretreated water
    Backwash:
    UF filtrate water
    CEB Water Source:
    UF filtrate water
    CIP Water Source:
    UF filtrate water
    """

    original_extract = wave_uf._extract_pdf_text
    try:
        wave_uf._extract_pdf_text = lambda path: (sample_text, "selftest")
        with tempfile.TemporaryDirectory() as td:
            result = validate_exported_uf_pdf(Path(td) / "dummy.pdf", UFVideoCase())
    finally:
        wave_uf._extract_pdf_text = original_extract

    assert result["classification"] == "validated", json.dumps(result, indent=2)
    assert result["checks"]["temperature"] is True, result
    assert "temperature" not in result["warnings"], result
    assert result["evidence"]["temperature"] == "uf_tmp_temperature_curve", result
    src = Path(__file__).with_name("wave_uf.py").read_text(encoding="utf-8")
    assert "at least the design temperature and one adjacent" in src
    print("V69 UF TMP temperature selftest PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
