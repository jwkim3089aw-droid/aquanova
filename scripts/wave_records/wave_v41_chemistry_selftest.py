#!/usr/bin/env python3
"""Offline regression checks for V52 full RO chemistry/special-feature schema."""
from __future__ import annotations

from pathlib import Path

from wave_batch import (
    _classify_constraint_adjusted_recovery,
    _extract_pdf_design_warnings,
    _extract_pdf_solubility_warnings,
    _merge_constraint_warnings,
    _validate_pdf_recoveries,
)
from wave_ro_schema import ROCaseConfig


def main() -> None:
    row = {
        "Case_ID": "SELFTEST_V52_CHEM",
        "Recommended_PDF_Name": "SELFTEST_V52_CHEM.pdf",
        "WAVE_Library_Selection": "Well Water - Med Hardness",
        "Feed_Flow_m3h": 100,
        "Temperature_Min_C": 10,
        "Temperature_Design_C": 25,
        "Temperature_Max_C": 35,
        "Pass_Count": 1,
        "Pass1_Recovery_pct": 75,
        "Pass1_Temperature_Mode": "Design",
        "Pass1_Temperature_C": 25,
        "Pass1_Stage_Count": 1,
        "P1S1_PV": 10,
        "P1S1_Elements_per_PV": 6,
        "P1S1_Membrane": "BW30-400",
        "Antiscalant_Enabled": "Y",
        "Antiscalant_Type": "EXACT WAVE PRODUCT LABEL",
        "Antiscalant_Dose_mgL": 2.5,
        "Dechlorinator_Enabled": "Y",
        "Dechlorinator_Type": "EXACT WAVE PRODUCT LABEL",
        "Dechlorinator_Dose_mgL": 1.1,
        "Chemical_Temperature_Mode": "Specify",
        "Chemical_Temperature_C": 25,
        "Chemical_Recovery_Mode": "Based on RO config",
        "Compaction_Enabled": "Y",
        "Compaction_Mode": "EXACT WAVE MODE LABEL",
        "Compaction_Value": 3,
        "RO_TOC_Rejection_Enabled": "Y",
        "RO_TOC_Rejection_pct": 92,
    }
    case = ROCaseConfig.from_mapping(row)
    assert case.chemical.enabled
    assert case.chemical.antiscalant_type == "EXACT WAVE PRODUCT LABEL"
    assert case.chemical.antiscalant_dose_mg_l == 2.5
    assert case.chemical.dechlorinator_dose_mg_l == 1.1
    assert case.chemical.temperature_mode == "Specify"
    assert case.chemical.recovery_mode == "Based on RO config"
    assert case.special_features.enabled
    assert case.special_features.compaction_value == 3
    assert case.special_features.toc_rejection_pct == 92
    flat = case.to_flat_dict()
    for key in (
        "antiscalant_enabled", "antiscalant_type", "antiscalant_dose_mg_l",
        "dechlorinator_enabled", "dechlorinator_type", "dechlorinator_dose_mg_l",
        "chemical_temperature_mode", "chemical_temperature_c",
        "chemical_recovery_mode", "compaction_enabled", "compaction_mode",
        "compaction_value", "toc_rejection_enabled", "toc_rejection_pct",
    ):
        assert key in flat, key

    source = Path(__file__).with_name("wave_uia.py").read_text(encoding="utf-8")
    for token in (
        "uia_chemical_adjustment_v44", "antiscalant_enabled",
        "dechlorinator_enabled", "chemical_temperature_mode",
        "chemical_recovery_mode", "table_before", "table_after",
        "uia_ro_special_feature_v44",
    ):
        assert token in source, token

    fixture = """
Pass
Pass 1
Feed Flow per Pass
(m³/h)
100.0
Permeate Flow per Pass
(m³/h)
85.4
Pass Recovery
85.5 %
RO Solubility Warnings
Pass 1
Langelier Saturation Index > 0
SiO2 saturation > 100
Anti-scalants may be required. Consult your anti-scalant manufacturer for dosing and maximum allowable system recovery.
Footnotes:
"""
    checks, details = _validate_pdf_recoveries(fixture, case)
    design = _extract_pdf_design_warnings(fixture)
    solubility = _extract_pdf_solubility_warnings(fixture)
    merged = _merge_constraint_warnings(design, solubility)
    classification = _classify_constraint_adjusted_recovery(
        [key for key, passed in checks.items() if not passed], details, merged
    )
    assert solubility["count"] == 3
    assert classification["eligible"]
    assert classification["warning_count"] == 3
    print("V52 full chemistry/special-feature self-test OK")


if __name__ == "__main__":
    main()
