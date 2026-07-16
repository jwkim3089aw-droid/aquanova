from app.schemas.simulation import ScenarioInput
from app.services.simulation.engine import SimulationEngine


def _case(**stage_overrides):
    stage = {
        "module_type": "HRRO",
        "element_inch": 8,
        "elements": 3,
        "vessel_count": 1,
        "elements_per_vessel": 3,
        "membrane_model": "filmtec-soar-5000i",
        "membrane_area_m2": 37.16,
        "membrane_A_lmh_bar": 5.50,
        "membrane_B_lmh": 0.060,
        "membrane_salt_rejection_pct": 99.5,
        "flow_factor": 0.70,
        "recovery_target_pct": 90.0,
        "stop_recovery_pct": 90.0,
        "feed_flow_m3h": 2.02,
        "loop_volume_m3": 0.09,
        "cc_recycle_m3h_per_pv": 4.50,
        "recirc_flow_m3h": 4.50,
        "min_concentrate_flow_m3h_per_pv": 4.50,
        "pf_recovery_pct": 10.0,
        "timestep_s": 30,
        "max_minutes": 60,
        "pump_eff": 0.8,
    }
    stage.update(stage_overrides)
    return ScenarioInput(
        **{
            "simulation_id": "v82-smart-partial-drain-test",
            "project_id": "selftest",
            "scenario_name": "V82 smart partial drain PF diagnostics",
            "feed": {
                "flow_m3h": 2.02,
                "tds_mgL": 412.4,
                "temperature_C": 25.0,
                "ph": 6.5,
            },
            "stages": [stage],
        }
    )


def test_v82_smart_partial_drain_fr150_mass_balance_and_crossflow():
    out = SimulationEngine().run(
        _case(
            pf_mode="smart_partial_drain",
            pf_feed_ratio_pct=150.0,
            p3_recycle_capacity_m3h_per_pv=3.70,
        )
    )
    cycle = out.stage_metrics[0].chemistry["ccro_cycle"]

    assert cycle["pf_mode"] == "smart_partial_drain"
    assert cycle["brine_valve_mode"] == "partial_pid"
    assert cycle["p3_required"] is True
    assert cycle["p2_oversizing_required"] is False
    assert cycle["crossflow_ok"] is True

    # For 2.02 m3/h feed at 90% recovery, product is 1.818 m3/h.
    # FR150 -> PF feed 2.727, drain setpoint = 2.727 - 1.818 = 0.909.
    assert abs(cycle["pf_feed_flow_m3h_per_pv"] - 2.727) < 0.03
    assert abs(cycle["pf_external_drain_setpoint_m3h_per_pv"] - 0.909) < 0.03
    assert abs(cycle["pf_membrane_total_feed_flow_m3h_per_pv"] - 6.318) < 0.05
    assert abs(cycle["pf_p3_recycle_flow_m3h_per_pv"] - 3.59) < 0.08
    assert not any(w.key == "pf_feed_ratio_max" for w in (out.warnings or []))


def test_v82_smart_partial_drain_fr120_warns_slow_flush_not_crossflow():
    out = SimulationEngine().run(
        _case(
            pf_mode="field_optimized_low_fr",
            pf_feed_ratio_pct=120.0,
            p3_recycle_capacity_m3h_per_pv=4.30,
        )
    )
    cycle = out.stage_metrics[0].chemistry["ccro_cycle"]
    assert cycle["crossflow_ok"] is True
    assert abs(cycle["pf_external_drain_setpoint_m3h_per_pv"] - 0.364) < 0.03
    assert any(w.key == "slow_flush_or_poor_salt_displacement" for w in (out.warnings or []))


def test_v82_wave_true_plug_fr150_shows_crossflow_shortfall():
    out = SimulationEngine().run(
        _case(
            pf_mode="wave_true_plug_flow",
            pf_feed_ratio_pct=150.0,
        )
    )
    cycle = out.stage_metrics[0].chemistry["ccro_cycle"]
    assert cycle["pf_mode"] == "wave_true_plug_flow"
    assert cycle["brine_valve_mode"] == "full_open"
    assert cycle["crossflow_ok"] is False
    assert cycle["p2_oversizing_required"] is False
    assert cycle["required_pf_feed_ratio_for_crossflow_pct"] > 250.0
    assert any(w.key == "pf_true_plug_crossflow_shortfall" for w in (out.warnings or []))


def test_v82_adaptive_recovery_stops_before_target_on_brine_limit():
    out = SimulationEngine().run(
        _case(
            recovery_target_pct=90.0,
            adaptive_recovery_enabled=True,
            brine_conductivity_limit_mgL=3000.0,
            adaptive_min_recovery_pct=50.0,
            feed_flow_m3h=2.02,
        )
    )
    metric = out.stage_metrics[0]
    model = metric.chemistry["model"]
    assert model["requested_target_recovery_pct"] == 90.0
    assert model["recovery_stop_reason"] == "brine_conductivity_limit"
    assert metric.recovery_pct < 90.0
    assert metric.recovery_pct >= 50.0
