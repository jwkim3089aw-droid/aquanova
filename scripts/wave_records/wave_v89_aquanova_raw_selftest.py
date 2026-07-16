#!/usr/bin/env python3
"""Small selftest for V89 raw-runner helpers."""
from __future__ import annotations

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.simulation.calibration.wave_aquanova_raw_runner import (  # noqa: E402
    build_surrogate_request_payload,
    fill_pair_rows_with_raw,
    infer_feed_tds_from_wave_pair,
)


def main() -> int:
    row = {
        "pair_id": "pair_selftest",
        "wave_pdf_name": "V84_CCRO_1PASS_SOAR5000i_F100_R90.pdf",
        "process_type": "ccro",
        "membrane_model_hint": "SOAR-5000i",
        "wave_target_value_count": 12,
        "wave_system_feed_flow_m3h": 2.02,
        "wave_system_product_flow_m3h": 1.818,
        "wave_system_concentrate_flow_m3h": 0.202,
        "wave_system_recovery_pct": 90.0,
        "wave_system_product_tds_mgL": 9.3,
        "wave_pass_final_concentrate_tds_mgL": 4040.0,
        "wave_ccro_pf_feed_ratio_pct": 270.0,
        "wave_ccro_pf_recovery_pct": 10.0,
    }
    feed_tds = infer_feed_tds_from_wave_pair(row)
    assert feed_tds is not None and 400.0 < feed_tds < 430.0
    payload = build_surrogate_request_payload(row)
    assert payload["stages"][0]["module_type"] == "HRRO"
    assert payload["stages"][0]["pf_feed_ratio_pct"] == 270.0
    raw = [{
        "Case_ID": "pair_selftest",
        "Process": "ccro",
        "Membrane_Model": "SOAR-5000i",
        "Feed_TDS_mgL": feed_tds,
        "Temp_C": 25,
        "Target_Recovery_%": 90,
        "Result_Recovery_%": 89,
        "Feed_Pressure_bar": 10,
        "Permeate_Flow_m3h": 1.8,
        "Permeate_TDS_mgL": 12,
        "Brine_TDS_mgL": 3900,
        "SEC_kwhm3": 0.4,
        "Warnings": "",
        "Status": "SUCCESS",
    }]
    filled = fill_pair_rows_with_raw([row], raw)
    assert filled[0]["pair_status"] == "paired"
    assert filled[0]["aquanova_feed_pressure_bar"] == 10
    print("V89 AquaNova raw selftest PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
