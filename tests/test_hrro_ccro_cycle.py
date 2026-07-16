from app.schemas.simulation import ScenarioInput
from app.services.simulation.engine import SimulationEngine


def _case(pf_ratio=270.0, pf_assist=False, pf_assist_flow=0.0):
    return ScenarioInput(
        **{
            "simulation_id": "hrro-ccro-cycle-selftest",
            "project_id": "selftest",
            "scenario_name": "1.82 m3h CCRO cycle diagnostics",
            "feed": {
                "flow_m3h": 2.02,
                "tds_mgL": 412.4,
                "temperature_C": 25.0,
                "ph": 6.5,
                "pressure_bar": 0.0,
                "ions": {
                    "Na": 87.17,
                    "Ca": 41.89,
                    "Mg": 9.28,
                    "Cl": 127.4,
                    "SO4": 146.6,
                },
            },
            "stages": [
                {
                    "module_type": "HRRO",
                    "element_inch": 8,
                    "elements": 3,
                    "vessel_count": 1,
                    "elements_per_vessel": 3,
                    "membrane_model": "filmtec-soar-5000i",
                    "membrane_area_m2": 37.16,
                    "recovery_target_pct": 90.0,
                    "stop_recovery_pct": 90.0,
                    "feed_flow_m3h": 2.02,
                    "loop_volume_m3": 0.09,
                    "cc_recycle_m3h_per_pv": 4.54,
                    "recirc_flow_m3h": 4.54,
                    "pf_feed_ratio_pct": pf_ratio,
                    "pf_recovery_pct": 10.0,
                    "pf_cp_assist_enabled": pf_assist,
                    "pf_cp_assist_flow_m3h_per_pv": pf_assist_flow,
                    "timestep_s": 30,
                    "max_minutes": 60,
                    "pump_eff": 0.8,
                }
            ],
        }
    )


def test_hrro_ccro_cycle_exposes_wave_style_pf_cc_values():
    out = SimulationEngine().run(_case())
    stage = out.stage_metrics[0]
    cycle = stage.chemistry["ccro_cycle"]

    assert stage.recovery_pct == 90.0
    assert abs(cycle["cc_permeate_flow_m3h_per_pv"] - 1.818) < 0.02
    assert abs(cycle["cc_concentrate_flow_m3h_per_pv"] - 4.54) < 0.01
    assert abs(cycle["pf_feed_flow_m3h_per_pv"] - 4.91) < 0.05
    assert abs(cycle["pf_concentrate_flow_m3h_per_pv"] - 4.42) < 0.05
    assert 26.0 < cycle["cc_sequence_duration_min"] < 28.0
    assert 1.0 < cycle["pf_sequence_duration_min"] < 1.4
    assert any((w.key == "pf_feed_ratio_max") for w in (out.warnings or []))
    assert {p.phase for p in (stage.time_history or [])} >= {"CC", "PF"}


def test_hrro_pf_cp_assist_warns_when_p3_exceeds_pf_feed():
    out = SimulationEngine().run(_case(pf_ratio=150.0, pf_assist=True, pf_assist_flow=4.54))
    cycle = out.stage_metrics[0].chemistry["ccro_cycle"]
    assert cycle["pf_cp_assist_enabled"] is True
    assert cycle["pf_cp_assist_flow_m3h_per_pv"] == 4.54
    assert any((w.key == "pf_cp_assist_suction_margin") for w in (out.warnings or []))
