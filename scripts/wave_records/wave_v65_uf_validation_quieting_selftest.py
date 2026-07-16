#!/usr/bin/env python3
"""Offline V69 checks for UF warning quieting and production marker updates."""
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
    TMP
    (bar)
    1.06 @ 10.0 °C
    0.92 @ 15.0 °C
    0.80 @ 20.0 °C
    UF System Recovery (%) 95.0
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
    assert not result["hard_errors"], result
    assert "water_profile" not in result["warnings"], result
    assert "temperature" not in result["warnings"], result
    assert result["checks"]["water_profile"] is True, result
    assert result["checks"]["temperature"] is True, result
    assert result["evidence"]["water_profile"] == "input_path_requested_profile_pdf_omits_field", result
    assert result["evidence"]["temperature"] == "uf_tmp_temperature_curve", result

    prod = Path(__file__).with_name("wave_production.py").read_text(encoding="utf-8")
    runtime = Path(__file__).with_name("wave_runtime.py").read_text(encoding="utf-8")
    ro_ui = Path(__file__).with_name("wave_ro_ui.py").read_text(encoding="utf-8")
    assert 'PRODUCTION_AUTOMATION_VERSION = "V69"' in prod
    assert '"automation_version": "V69"' in runtime
    assert "provisional_pdf_deferred" in ro_ui
    assert "uf_pdf_validation_v69" in Path(__file__).with_name("wave_uf.py").read_text(encoding="utf-8")
    print("V69 UF validation quieting selftest PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
