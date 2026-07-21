from __future__ import annotations

from app.schemas.simulation import ScenarioInput
from app.services.simulation.engine import SimulationEngine


def _smart_fr150_case() -> ScenarioInput:
    return ScenarioInput(
        **{
            "project_id": "v136_hrro_pressure_profile",
            "scenario_name": (
                "V136 HRRO CC rise and PF pressure drop"
            ),
            "feed": {
                "flow_m3h": 2.02,
                "tds_mgL": 412.4,
                "temperature_C": 25.0,
                "ph": 6.5,
            },
            "stages": [
                {
                    "stage_id": "hrro-pressure-profile",
                    "module_type": "HRRO",
                    "recovery_target_pct": 90.0,
                    "vessel_count": 1,
                    "elements_per_vessel": 3,
                    "elements": 3,
                    "element_inch": 8,
                    "membrane_model": (
                        "FilmTec SOAR 5000i"
                    ),
                    "membrane_area_m2": 37.16,
                    "membrane_A_lmh_bar": 5.50,
                    "membrane_B_lmh": 0.060,
                    "membrane_salt_rejection_pct": 99.5,
                    "flow_factor": 0.70,
                    "pump_efficiency": 0.80,
                    "loop_volume_m3": 0.09,
                    "cc_recycle_m3h_per_pv": 4.50,
                    "pf_feed_ratio_pct": 150.0,
                    "pf_recovery_pct": 20.0,
                    "pf_mode": "smart_partial_drain",
                    "brine_valve_mode": "partial_pid",
                    "p3_recycle_capacity_m3h_per_pv": 3.70,
                    "dp_per_elem_bar": 0.0333,
                    "max_minutes": 60.0,
                    "hrro_engine": "physics",
                    "hrro_pressure_limit_bar": 12.0,
                    "max_tmp_bar": 12.0,
                }
            ],
            "options": {},
        }
    )


def test_v136_hrro_cc_pressure_rises_and_pf_pressure_drops():
    output = SimulationEngine().run(
        _smart_fr150_case()
    )

    stage = output.stage_metrics[0]
    history = stage.time_history or []

    cc_rows = [
        point
        for point in history
        if point.phase == "CC"
    ]

    pf_rows = [
        point
        for point in history
        if point.phase == "PF"
    ]

    assert len(cc_rows) >= 2
    assert len(pf_rows) >= 1

    cc_start = float(cc_rows[0].pressure_bar)
    cc_terminal = float(
        cc_rows[-1].pressure_bar
    )
    pf_initial = float(
        pf_rows[0].pressure_bar
    )

    assert cc_terminal > cc_start + 0.01
    assert pf_initial < cc_terminal - 0.01

    all_pressures = [
        float(point.pressure_bar)
        for point in history
    ]

    assert stage.p_in_bar == round(
        max(all_pressures),
        2,
    )


def test_v136_pf_history_does_not_copy_terminal_cc_pressure():
    output = SimulationEngine().run(
        _smart_fr150_case()
    )

    history = (
        output.stage_metrics[0].time_history
        or []
    )

    cc_rows = [
        point
        for point in history
        if point.phase == "CC"
    ]

    pf_rows = [
        point
        for point in history
        if point.phase == "PF"
    ]

    assert cc_rows
    assert pf_rows

    cc_terminal = float(
        cc_rows[-1].pressure_bar
    )

    pf_pressures = [
        float(point.pressure_bar)
        for point in pf_rows
    ]

    assert pf_pressures[0] != cc_terminal
    assert min(pf_pressures) < cc_terminal
