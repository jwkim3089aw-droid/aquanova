from app.schemas.simulation import ScenarioInput
from app.services.simulation.engine import SimulationEngine
from app.services.simulation.wave_benchmark import run_wave_1p82_hrro_r90_benchmark


def test_v80_wave_quality_closes_1p82_hrro_tds_benchmark_failures():
    report = run_wave_1p82_hrro_r90_benchmark()
    summary = report.summary
    assert summary["failed_keys"] == []
    rows = {row.key: row for row in report.rows}
    assert rows["system.product_tds_mgL"].status == "PASS"
    assert rows["pass.final_concentrate_tds_mgL"].status == "PASS"
    assert abs(rows["system.product_tds_mgL"].actual - 9.28) < 0.2
    assert abs(rows["pass.final_concentrate_tds_mgL"].actual - 4038.0) < 20.0


def test_v80_hrro_stage_exposes_wave_quality_alignment_payload():
    payload = {
        "project_id": "v80-wave-quality-test",
        "scenario_name": "V80 HRRO water quality alignment smoke",
        "feed": {"flow_m3h": 2.02, "tds_mgL": 412.4, "temperature_C": 25.0, "ph": 6.5},
        "stages": [
            {
                "module_type": "HRRO",
                "recovery_target_pct": 90.0,
                "vessel_count": 1,
                "elements_per_vessel": 3,
                "elements": 3,
                "element_inch": 8,
                "membrane_model": "FilmTec SOAR 5000i",
                "membrane_area_m2": 37.16,
                "membrane_A_lmh_bar": 5.50,
                "membrane_B_lmh": 0.060,
                "membrane_salt_rejection_pct": 99.5,
                "flow_factor": 0.70,
                "pump_efficiency": 0.80,
                "loop_volume_m3": 0.09,
                "cc_recycle_m3h_per_pv": 4.54,
                "pf_feed_ratio_pct": 270.0,
                "pf_recovery_pct": 10.0,
                "dp_per_elem_bar": 0.0333,
                "max_minutes": 60.0,
                "hrro_engine": "physics",
                "hrro_pressure_limit_bar": 12.0,
                "max_tmp_bar": 12.0,
            }
        ],
    }
    out = SimulationEngine().run(ScenarioInput(**payload))
    metric = out.stage_metrics[0]
    quality = metric.chemistry["wave_quality_alignment"]
    assert quality["schema"] == "aquanova.hrro.wave_quality.v80"
    assert quality["raw_engine_product_tds_mgL"] < quality["product_tds_mgL"]
    assert metric.Cp == round(quality["product_tds_mgL"], 2)
    assert metric.Cc == round(quality["final_concentrate_tds_mgL"], 2)
