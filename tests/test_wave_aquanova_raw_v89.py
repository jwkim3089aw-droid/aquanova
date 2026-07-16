from __future__ import annotations

from app.services.simulation.calibration.wave_aquanova_raw_runner import (
    build_surrogate_request_payload,
    fill_pair_rows_with_raw,
    infer_feed_tds_from_wave_pair,
)


def test_v89_infers_feed_tds_from_mass_balance() -> None:
    row = {
        "wave_system_feed_flow_m3h": 2.02,
        "wave_system_product_flow_m3h": 1.818,
        "wave_system_concentrate_flow_m3h": 0.202,
        "wave_system_product_tds_mgL": 9.3,
        "wave_pass_final_concentrate_tds_mgL": 4040.0,
    }
    feed_tds = infer_feed_tds_from_wave_pair(row)
    assert feed_tds is not None
    assert 410.0 < feed_tds < 413.0


def test_v89_builds_hrro_payload_from_ccro_pair() -> None:
    row = {
        "pair_id": "p1",
        "wave_pdf_name": "V84_CCRO_1PASS_SOAR5000i_F100_R90.pdf",
        "process_type": "ccro",
        "membrane_model_hint": "SOAR-5000i",
        "wave_system_feed_flow_m3h": 2.02,
        "wave_system_recovery_pct": 90.0,
        "wave_ccro_pf_feed_ratio_pct": 270.0,
        "wave_ccro_system_volume_m3": 0.09,
    }
    payload = build_surrogate_request_payload(row)
    stage = payload["stages"][0]
    assert stage["module_type"] == "HRRO"
    assert stage["membrane_model"] == "SOAR-5000i"
    assert stage["pf_feed_ratio_pct"] == 270.0
    assert stage["loop_volume_m3"] == 0.09


def test_v89_fills_pair_and_error_columns_without_fuzzy_matching() -> None:
    pair = {
        "pair_id": "p2",
        "wave_target_value_count": 5,
        "wave_pass_feed_pressure_bar": 8.2,
        "wave_system_product_tds_mgL": 9.28,
        "wave_system_specific_energy_kwh_m3": 0.30,
    }
    raw = {
        "Case_ID": "p2",
        "Process": "ccro",
        "Membrane_Model": "SOAR-5000i",
        "Feed_TDS_mgL": 412,
        "Temp_C": 25,
        "Target_Recovery_%": 90,
        "Result_Recovery_%": 90,
        "Feed_Pressure_bar": 9.94,
        "Permeate_TDS_mgL": 9.30,
        "SEC_kwhm3": 0.34,
        "Status": "SUCCESS",
    }
    rows = fill_pair_rows_with_raw([pair], [raw])
    assert rows[0]["pair_status"] == "paired"
    assert round(rows[0]["error_feed_pressure_abs"], 2) == 1.74
    assert round(rows[0]["error_specific_energy_pct"], 2) == 13.33
