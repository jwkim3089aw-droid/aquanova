#!/usr/bin/env python3
"""Offline regression checks for V52 multi-pass PDF parsing."""
from __future__ import annotations

from wave_batch import (
    _classify_constraint_adjusted_recovery,
    _extract_pdf_design_warnings,
    _extract_pdf_solubility_warnings,
    _merge_constraint_warnings,
    _validate_pdf_recoveries,
    expand_cases_for_wave_global_temperature,
    _pdf_flow_factor_per_stage_values,
    _pdf_flow_per_pass_values,
    _pdf_pass_summary_row_values,
)

FIXTURE = """
Pass
Pass 1
Pass 2
Feed Flow per Pass
(m³/h)
99.9
74.9
Permeate Flow per Pass
(m³/h)
75.0
60.0
Pass Recovery
75.1 %
80.1 %
Flow Factor Per Stage
0.85
1.00
Average NDP
(bar)
11.6
13.4
Footnotes:
"""


def main() -> None:
    assert _pdf_pass_summary_row_values(FIXTURE, "Pass Recovery", 2) == [75.1, 80.1]
    assert _pdf_flow_per_pass_values(FIXTURE, "Feed Flow per Pass", 2) == [99.9, 74.9]
    assert _pdf_flow_per_pass_values(FIXTURE, "Permeate Flow per Pass", 2) == [75.0, 60.0]
    assert _pdf_flow_factor_per_stage_values(FIXTURE, 2) == [[0.85], [1.0]]
    derived = [75.0 / 99.9 * 100.0, 60.0 / 74.9 * 100.0]
    assert abs(derived[0] - 75.0750750751) < 1e-8
    assert abs(derived[1] - 80.1068090788) < 1e-8
    from wave_ro_schema import ROCaseConfig

    mixed = ROCaseConfig.from_mapping(
        {
            "Case_ID": "TEMP_MIX",
            "Recommended_PDF_Name": "TEMP_MIX.pdf",
            "WAVE_Library_Selection": "Well Water - Med Hardness",
            "Feed_Flow_m3h": 100,
            "Temperature_Min_C": 10,
            "Temperature_Design_C": 25,
            "Temperature_Max_C": 35,
            "Pass_Count": 2,
            "Pass1_Recovery_pct": 72,
            "Pass1_Temperature_Mode": "Minimum",
            "Pass1_Temperature_C": 10,
            "Pass1_Stage_Count": 1,
            "P1S1_PV": 6,
            "P1S1_Elements_per_PV": 6,
            "P1S1_Membrane": "BW30-400",
            "Pass2_Recovery_pct": 80,
            "Pass2_Temperature_Mode": "Maximum",
            "Pass2_Temperature_C": 35,
            "Pass2_Stage_Count": 1,
            "P2S1_PV": 6,
            "P2S1_Elements_per_PV": 6,
            "P2S1_Membrane": "BW30-400",
        }
    )
    variants, manifest = expand_cases_for_wave_global_temperature([mixed])
    assert [v.case_id for v in variants] == ["TEMP_MIX__MIN_10C", "TEMP_MIX__MAX_35C"]
    assert all(len({p.temperature_c for p in v.passes}) == 1 for v in variants)
    assert manifest[0]["reason"] == "WAVE temperature is global across Pass tabs"

    off_design_fixture = """
Pass
Pass 1
Pass 2
Feed Flow per Pass
(m³/h)
100.0
77.2
Permeate Flow per Pass
(m³/h)
77.3
61.8
Pass Recovery
77.3 %
80.1 %
Average NDP
(bar)
7.9
8.6
Footnotes:
"""
    max_case = variants[1]
    checks, details = _validate_pdf_recoveries(off_design_fixture, max_case)
    assert checks == {"pass1_recovery": True, "pass2_recovery": True}
    assert details["passes"]["pass1_recovery"]["strict_target_match"] is False
    assert details["passes"]["pass2_recovery"]["strict_target_match"] is False

    constrained_fixture = """
Pass
Pass 1
Feed Flow per Pass
(m³/h)
100.0
Permeate Flow per Pass
(m³/h)
78.8
Pass Recovery
78.8 %
Temperature
(°C)
25.0
RO Design Warnings
Design Warning
Limit
Value
Pass
Stage
Element
Product
Permeate Flow Rate > Maximum Limit
(m³/h)
1.43
1.75
1
1
1
BW30XFRLE-400/34
Footnotes:
"""
    constrained_case = ROCaseConfig.from_mapping(
        {
            "Case_ID": "CONSTRAINED",
            "Recommended_PDF_Name": "CONSTRAINED.pdf",
            "WAVE_Library_Selection": "Well Water - Low TDS",
            "Feed_Flow_m3h": 100,
            "Temperature_Design_C": 25,
            "Pass_Count": 1,
            "Pass1_Recovery_pct": 75,
            "Pass1_Temperature_Mode": "Design",
            "Pass1_Temperature_C": 25,
            "Pass1_Stage_Count": 1,
            "P1S1_PV": 6,
            "P1S1_Elements_per_PV": 6,
            "P1S1_Membrane": "BW30XFRLE-400/34",
        }
    )
    constrained_checks, constrained_details = _validate_pdf_recoveries(
        constrained_fixture, constrained_case
    )
    warnings = _extract_pdf_design_warnings(constrained_fixture)
    classification = _classify_constraint_adjusted_recovery(
        [key for key, passed in constrained_checks.items() if not passed],
        constrained_details,
        _merge_constraint_warnings(warnings, {"count": 0, "items": [], "messages": [], "counts_by_message": {}}),
    )
    assert constrained_checks == {"pass1_recovery": False}
    assert warnings["count"] == 1
    assert classification["eligible"] is True
    assert abs(classification["passes"]["pass1_recovery"]["deviation_pct_points"] - 3.8) < 1e-8

    solubility_fixture = """
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
    solubility_checks, solubility_details = _validate_pdf_recoveries(
        solubility_fixture, constrained_case
    )
    solubility = _extract_pdf_solubility_warnings(solubility_fixture)
    merged = _merge_constraint_warnings(
        {"count": 0, "items": [], "messages": [], "counts_by_message": {}},
        solubility,
    )
    solubility_classification = _classify_constraint_adjusted_recovery(
        [key for key, passed in solubility_checks.items() if not passed],
        solubility_details,
        merged,
    )
    assert solubility["count"] == 3
    assert merged["count"] == 3
    assert solubility_classification["eligible"] is True
    assert abs(solubility_classification["passes"]["pass1_recovery"]["deviation_pct_points"] - 10.5) < 1e-8

    print("V52 global-temperature/PDF validation self-test OK")


if __name__ == "__main__":
    main()
