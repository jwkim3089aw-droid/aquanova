#!/usr/bin/env python3
"""Machine-readable RO UI inventory from the user's 2026-07-01 WAVE video."""
from __future__ import annotations

from pathlib import Path
from typing import Any
import json

CATALOG_SCHEMA_VERSION = 4


# Exact names visibly observed in the user-supplied WAVE membrane dropdown.
# These are test candidates, not a universal compatibility guarantee for every feed.
OBSERVED_TEST_MEMBRANES: tuple[str, ...] = (
    "BW30-400",
    "BW30 PRO-400",
    "BW30XHR PRO-440",
    "BW30HR-440",
    "BW30XFRLE-400/34",
    "BW30-365",
    "BW30 PRO-365",
    "LC HR-4040",
    "LC HF-4040",
    "LC LE-4040",
)

OBSERVED_RESTRICTED_MEMBRANE_LABELS: tuple[str, ...] = (
    "BW30FR-400/34 (to be discontinued 2022)",
    "BW30FR-400/34i (to be discontinued 2022)",
    "BW30FR-400/34i (China only)",
    "LE-400 (obsolete)",
    "LE-440 (obsolete)",
    "LE-440i (obsolete)",
    "XFRLE-400/34 (obsolete)",
    "XFRLE-400/34i (obsolete)",
    "BW30-365 IG (obsolete)",
    "BW30-400-IG (obsolete)",
)


def _r(category: str, screen: str, label: str, control: str, options: str = "", unit: str = "", dependency: str = "", automation: str = "catalogued", code_key: str = "", notes: str = "") -> dict[str, Any]:
    return {
        "category": category,
        "screen": screen,
        "wave_label": label,
        "control_type": control,
        "observed_options": options,
        "unit": unit,
        "activation_dependency": dependency,
        "automation_status": automation,
        "code_key": code_key,
        "notes": notes,
    }


RO_UI_CATALOG: list[dict[str, Any]] = [
    _r("Project", "Configuration ribbon", "Add Case", "Button", automation="catalogued"),
    _r("Project", "Configuration ribbon", "Manage", "Button", automation="catalogued"),
    _r("Chemistry", "Configuration ribbon", "Add Chemicals/Degas", "Button", automation="experimental", code_key="chemical"),
    _r("Chemistry", "Configuration ribbon", "Adjust Final pH", "Button", automation="catalogued"),
    _r("RO special", "Configuration ribbon", "Compaction", "Button", automation="experimental", code_key="special.compaction"),
    _r("RO special", "Configuration ribbon", "RO TOC Rejection", "Button", automation="experimental", code_key="special.toc_rejection_pct"),
    _r("Feed temperature", "Feed Setup", "Minimum Temperature", "Numeric edit", unit="°C", automation="new", code_key="feed_temperature_min_c", notes="V25 supports independent Minimum/Design/Maximum with invariant-preserving edit order."),
    _r("Feed temperature", "Feed Setup", "Design Temperature", "Numeric edit", unit="°C", automation="stable", code_key="feed_temperature_design_c"),
    _r("Feed temperature", "Feed Setup", "Maximum Temperature", "Numeric edit", unit="°C", automation="new", code_key="feed_temperature_max_c"),
    _r("Pass topology", "Reverse Osmosis", "Add Pass", "Link/Button", options="Pass 2", automation="experimental", code_key="pass_count", notes="Two-pass path requires --allow-experimental-ro until a full unattended run is validated."),
    _r("Pass topology", "Reverse Osmosis", "Pass 1 / Pass 2", "Selector", options="1-2 passes observed", automation="new", code_key="passes"),
    _r("Pass topology", "Reverse Osmosis", "Number of Stages", "Radio group", options="1|2|3|4|5", automation="new", code_key="stage_count"),
    _r("Pass operating", "Reverse Osmosis", "Flow Factor", "Numeric edit", unit="-", automation="new", code_key="flow_factor"),
    _r("Pass operating", "Reverse Osmosis", "Temperature", "ComboBox", options="Minimum|Design|Maximum|Specify", dependency="Specify enables numeric temperature", automation="stable", code_key="temperature_mode"),
    _r("Pass operating", "Reverse Osmosis", "Temperature value", "Numeric edit", unit="°C", dependency="Temperature=Specify", automation="stable", code_key="temperature_c"),
    _r("Pass operating", "Reverse Osmosis", "Pass Permeate Back Pressure", "Numeric edit", unit="bar", automation="new", code_key="permeate_back_pressure_bar"),
    _r("Flows", "Reverse Osmosis", "Feed Flow", "Command/readout", unit="m³/h", dependency="opens Reverse Osmosis Flow Calculator", automation="stable", code_key="feed_flow_m3h"),
    _r("Flows", "Reverse Osmosis", "Recovery", "Command/readout", unit="%", dependency="opens Reverse Osmosis Flow Calculator", automation="stable", code_key="recovery_pct"),
    _r("Flows", "Reverse Osmosis", "Permeate Flow", "Readout", unit="m³/h"),
    _r("Flows", "Reverse Osmosis", "Flux", "Readout", unit="LMH"),
    _r("Flows", "Reverse Osmosis", "Conc. Recycle Flow", "Readout", unit="m³/h"),
    _r("Flows", "Reverse Osmosis", "Bypass Flow", "Readout", unit="m³/h"),
    _r("Stage configuration", "Reverse Osmosis", "# PV per stage", "Stage-table numeric edit", automation="new", code_key="stage.pv"),
    _r("Stage configuration", "Reverse Osmosis", "# Els per PV", "Stage-table numeric edit", automation="new", code_key="stage.elements_per_pv"),
    _r("Stage configuration", "Reverse Osmosis", "Element Type Specs", "Stage-table ComboBox", automation="new", code_key="stage.membrane", notes="Exact-name and PDF verification required; obsolete/discontinued/China-only variants appear in same list."),
    _r("Stage result/control", "Reverse Osmosis", "Total Els per Stage", "Readout"),
    _r("Stage result/control", "Reverse Osmosis", "Pre-stage ΔP", "Readout", unit="bar"),
    _r("Stage result/control", "Reverse Osmosis", "Stage Back Press", "Stage-table numeric edit", unit="bar", automation="new", code_key="stage.stage_back_pressure_bar"),
    _r("Stage result/control", "Reverse Osmosis", "Boost Press", "Stage-table numeric edit/readout", unit="bar", dependency="availability depends on stage topology", automation="experimental", code_key="stage.boost_pressure_bar", notes="Availability depends on stage topology; V25 verifies the numeric field when readable."),
    _r("Stage result/control", "Reverse Osmosis", "Feed Press", "Readout", unit="bar"),
    _r("Stage result/control", "Reverse Osmosis", "% Conc to Feed", "Readout", unit="%"),
    _r("Stage result/control", "Reverse Osmosis", "Flow Factor", "Stage-table numeric edit/readout", automation="new", code_key="stage.flow_factor"),
    _r("Flow calculator", "Reverse Osmosis Flow Calculator", "RO System Feed Flow Rate", "Radio + numeric", options="Automatic observed", unit="m³/h", automation="stable"),
    _r("Flow calculator", "Reverse Osmosis Flow Calculator", "System Feed/Product/Concentrate Flow", "Readout", unit="m³/h"),
    _r("Flow calculator", "Reverse Osmosis Flow Calculator", "System Recovery", "Readout", unit="%"),
    _r("Flow calculator", "Reverse Osmosis Flow Calculator", "Pass Net Feed Flow", "Readout", unit="m³/h"),
    _r("Flow calculator", "Reverse Osmosis Flow Calculator", "Pass Recovery", "Numeric edit", unit="%", automation="stable", code_key="pass.recovery_pct"),
    _r("Flow calculator", "Reverse Osmosis Flow Calculator", "Conc. Recycle to head of", "ComboBox", options="Pass 1|Pass 2 where applicable", automation="experimental", code_key="pass.recycle_target_pass"),
    _r("Flow calculator", "Reverse Osmosis Flow Calculator", "Conc. Recycle", "Numeric edit", unit="% / m³/h", automation="experimental", code_key="pass.recycle_pct"),
    _r("Flow calculator", "Reverse Osmosis Flow Calculator", "Pass Size Optimization - Bypass", "Radio + numeric", unit="% / m³/h", automation="experimental", code_key="pass.bypass_pct"),
    _r("Flow calculator", "Reverse Osmosis Flow Calculator", "Pass Size Optimization - Permeate Split", "Radio + numeric", unit="% / m³/h", automation="experimental", code_key="pass.permeate_split_pct"),
    _r("Flow calculator", "Reverse Osmosis Flow Calculator", "Pass Size Optimization - None", "Radio", automation="stable"),
    _r("Flow calculator", "Reverse Osmosis Flow Calculator", "Concentrate Recycle Split", "Numeric edits", options="to Pass1|to Pass2", unit="% / m³/h", automation="experimental", code_key="pass.recycle_split_*"),
    _r("Chemical", "Chemical Adjustment", "↓ pH", "Mode button", automation="experimental", code_key="chemical.acid_enabled"),
    _r("Chemical", "Chemical Adjustment", "Acid Type", "ComboBox", options="HCl (32)|H2SO4 (98)", automation="experimental", code_key="chemical.acid_type"),
    _r("Chemical", "Chemical Adjustment", "Acid target pH", "Numeric edit", unit="pH", automation="experimental", code_key="chemical.acid_target_ph"),
    _r("Chemical", "Chemical Adjustment", "Acid LSI", "Readout", unit="-"),
    _r("Degas", "Chemical Adjustment", "Degas", "Mode button", automation="experimental", code_key="chemical.degas_enabled"),
    _r("Degas", "Chemical Adjustment", "CO2% Removal", "Radio + numeric", unit="%", automation="experimental", code_key="chemical.degas_mode/value"),
    _r("Degas", "Chemical Adjustment", "CO2 Partial Pressure", "Radio + numeric", unit="µatm", automation="experimental", code_key="chemical.degas_mode/value"),
    _r("Degas", "Chemical Adjustment", "CO2 Concentration", "Radio + numeric", unit="mg/L", automation="experimental", code_key="chemical.degas_mode/value"),
    _r("Chemical", "Chemical Adjustment", "↑ pH", "Mode button", automation="experimental", code_key="chemical.base_enabled"),
    _r("Chemical", "Chemical Adjustment", "Base Type", "ComboBox", options="NaOH (30)|NaOH (50)", automation="experimental", code_key="chemical.base_type"),
    _r("Chemical", "Chemical Adjustment", "Base target pH", "Numeric edit", unit="pH", automation="experimental", code_key="chemical.base_target_ph"),
    _r("Chemical", "Chemical Adjustment", "Base LSI", "Readout", unit="-"),
    _r("Chemical", "Chemical Adjustment", "Anti-Scalant", "Mode button", automation="experimental", code_key="chemical.antiscalant_enabled"),
    _r("Chemical", "Chemical Adjustment", "Anti-Scalant Type", "ComboBox", automation="experimental", code_key="chemical.antiscalant_type", notes="Exact WAVE combo label is accepted from Excel."),
    _r("Chemical", "Chemical Adjustment", "Anti-Scalant Dose", "Numeric edit", unit="mg/L", automation="experimental", code_key="chemical.antiscalant_dose_mg_l"),
    _r("Chemical", "Chemical Adjustment", "Dechlorinator", "Mode button", automation="experimental", code_key="chemical.dechlorinator_enabled"),
    _r("Chemical", "Chemical Adjustment", "Dechlorinator Type", "ComboBox", automation="experimental", code_key="chemical.dechlorinator_type", notes="Exact WAVE combo label is accepted from Excel."),
    _r("Chemical", "Chemical Adjustment", "Dechlorinator Dose", "Numeric edit", unit="mg/L", automation="experimental", code_key="chemical.dechlorinator_dose_mg_l"),
    _r("Chemical", "Chemical Adjustment", "Temperature mode", "ComboBox", options="Minimum|Design|Maximum|Specify", automation="experimental", code_key="chemical.temperature_mode"),
    _r("Chemical", "Chemical Adjustment", "Temperature value", "Numeric edit/readout", unit="°C", dependency="Temperature=Specify enables edit", automation="experimental", code_key="chemical.temperature_c"),
    _r("Chemical", "Chemical Adjustment", "RO Recovery mode", "ComboBox", options="Basic default|Specify|Based on RO config", automation="experimental", code_key="chemical.recovery_mode"),
    _r("Chemical", "Chemical Adjustment", "RO Recovery value", "Numeric edit/readout", unit="%", dependency="Recovery=Specify enables edit", automation="experimental", code_key="chemical.recovery_value_pct"),
    _r("Chemical output", "Chemical Adjustment", "Adjustment calculation table", "Readout grid", options="pH|LSI|Stiff & Davis|TDS|Ionic Strength|HCO3|CO2|CO3|CaSO4|BaSO4|SrSO4|CaF2|SiO2|Mg(OH)2", automation="experimental", code_key="chemical.table_snapshot"),
    _r("Error", "Calculation", "Convergence Error", "Modal dialog", options="WAVE has failed to converge. Please review your design.", automation="stable", code_key="error.convergence", notes="Must be classified as case failure; never blindly acknowledged as success."),
    _r("Export", "Report ribbon", "Export to PDF", "Button", automation="stable", code_key="pdf_name"),
]


def catalog_payload() -> dict[str, Any]:
    return {
        "schema_version": CATALOG_SCHEMA_VERSION,
        "automation_version": "V52",
        "source": "User-supplied WAVE RO UI inventory videos, 2026-07-01 and 2026-07-03",
        "observed_test_membranes": list(OBSERVED_TEST_MEMBRANES),
        "observed_restricted_membrane_labels": list(OBSERVED_RESTRICTED_MEMBRANE_LABELS),
        "items": RO_UI_CATALOG,
    }


def write_catalog_json(path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(catalog_payload(), ensure_ascii=False, indent=2), encoding="utf-8")
    return path


__all__ = ["RO_UI_CATALOG", "OBSERVED_TEST_MEMBRANES", "OBSERVED_RESTRICTED_MEMBRANE_LABELS", "catalog_payload", "write_catalog_json"]
