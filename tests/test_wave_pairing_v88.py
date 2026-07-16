from __future__ import annotations

from app.services.simulation.calibration.wave_calibration_pairing import (
    build_pair_rows,
    infer_wave_case_metadata,
    summarize_pair_rows,
)


def test_v88_infers_ccro_case_metadata_and_targets() -> None:
    record = {
        "pdf_name": "V84_STRESS_CCRO_2PASS_SOAR5000i_F100_P1R90_P2R95.pdf",
        "process": "ccro",
        "metrics": {
            "system.recovery_pct": 95.0,
            "system.product_tds_mgL": 10.0,
            "pass.feed_pressure_bar": 12.3,
            "ccro.pf_feed_ratio_pct": 270.0,
        },
    }
    meta = infer_wave_case_metadata(record)
    assert meta["process_type"] == "ccro"
    assert meta["membrane_family_hint"] == "soar"
    assert meta["pass_count_hint"] == 2
    assert meta["target_recovery_pct_hint"] == 95.0
    assert meta["flow_factor_pct_hint"] == 100.0
    assert meta["is_stress_case"] is True

    rows = build_pair_rows([record], feature_splits={record["pdf_name"]: "holdout"})
    assert rows[0]["split"] == "holdout"
    assert rows[0]["wave_pass_feed_pressure_bar"] == 12.3
    assert rows[0]["wave_ccro_pf_feed_ratio_pct"] == 270.0
    assert rows[0]["pair_status"] == "needs_aquanova_raw"


def test_v88_optional_raw_pairing_and_error_columns() -> None:
    record = {
        "pdf_name": "RO_T001_MedHardness_F100_R75_T25_BW30-400.pdf",
        "process": "ro",
        "metrics": {
            "system.recovery_pct": 75.0,
            "system.product_tds_mgL": 4.85,
            "system.specific_energy_kwh_m3": 0.67,
            "system.temperature_c": 25.0,
            "pass.feed_pressure_bar": 13.1,
            "pass.final_concentrate_tds_mgL": 1856.0,
        },
    }
    raw = [{
        "Case_ID": "CASE_001",
        "Water_Type": "RO/NF Well Water",
        "Membrane_Model": "filmtec-bw30-400",
        "Temp_C": "25",
        "Target_Recovery_%": "75",
        "Result_Recovery_%": "75",
        "Feed_Pressure_bar": "14.1",
        "Permeate_TDS_mgL": "5.85",
        "Brine_TDS_mgL": "1900",
        "SEC_kwhm3": "0.70",
        "Status": "SUCCESS",
    }]
    rows = build_pair_rows([record], aquanova_raw_rows=raw)
    row = rows[0]
    assert row["pair_status"] == "paired"
    assert row["aquanova_case_id"] == "CASE_001"
    assert row["error_feed_pressure_abs"] == 1.0
    assert round(row["error_product_tds_abs"], 2) == 1.0
    summary = summarize_pair_rows(rows)
    assert summary["paired_row_count"] == 1
