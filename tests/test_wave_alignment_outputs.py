from app.schemas.simulation import ScenarioInput
from app.services.simulation.engine import SimulationEngine


def _run_one(stage):
    payload = {
        "project_id": "wave_alignment_test",
        "scenario_name": "WAVE alignment smoke",
        "feed": {
            "flow_m3h": 10.0,
            "tds_mgL": 500.0,
            "temperature_C": 25.0,
            "pressure_bar": 1.0,
        },
        "stages": [stage],
        "options": {},
    }
    return SimulationEngine().run(ScenarioInput(**payload)).stage_metrics[0]


def test_ro_wave_alignment_payload_present():
    metric = _run_one(
        {
            "stage_id": "ro1",
            "module_type": "RO",
            "recovery_target_pct": 50.0,
            "vessel_count": 2,
            "elements_per_vessel": 5,
            "membrane_area_m2": 37.16,
            "membrane_A_lmh_bar": 3.0,
            "membrane_B_lmh": 0.12,
            "membrane_salt_rejection_pct": 99.5,
            "max_inverse_pressure_bar": 80.0,
        }
    )
    wa = metric.chemistry["wave_alignment"]
    assert wa["schema"] == "aquanova.wave_alignment.pressure_membrane.v1"
    assert wa["module_type"] == "RO"
    assert wa["overview"]["element_inch"] == 8
    assert wa["flow_table"][0]["stream"] == "Feed"


def test_nf_wave_alignment_payload_present():
    metric = _run_one(
        {
            "stage_id": "nf1",
            "module_type": "NF",
            "recovery_target_pct": 70.0,
            "vessel_count": 1,
            "elements_per_vessel": 3,
            "membrane_area_m2": 37.16,
            "membrane_A_lmh_bar": 8.0,
            "membrane_B_lmh": 0.5,
        }
    )
    wa = metric.chemistry["wave_alignment"]
    assert wa["module_type"] == "NF"
    assert "design_limits" in wa
    assert wa["overview"]["recovery_pct"] >= 0.0


def test_uf_wave_alignment_payload_present():
    payload = {
        "project_id": "uf_wave_alignment_test",
        "scenario_name": "UF WAVE alignment smoke",
        "feed": {
            "flow_m3h": 6.0,
            "tds_mgL": 300.0,
            "tss_mgL": 5.0,
            "temperature_C": 20.0,
            "pressure_bar": 0.0,
        },
        "stages": [
            {
                "stage_id": "uf1",
                "module_type": "UF",
                "elements": 2,
                "membrane_area_m2": 77.0,
                "recovery_target_pct": 90.0,
                "uf_maintenance": {
                    "filtration_duration_min": 45.0,
                    "backwash_duration_sec": 60.0,
                    "backwash_flux_lmh": 100.0,
                    "air_scour_duration_sec": 20.0,
                },
            }
        ],
        "options": {},
    }
    out = SimulationEngine().run(ScenarioInput(**payload))
    wa = out.stage_metrics[0].chemistry["wave_alignment"]
    assert wa["schema"] == "aquanova.wave_alignment.uf.v1"
    assert wa["cycle"]["cycle_duration_min"] > wa["cycle"]["filtration_duration_min"]
    assert wa["streams"]["net_permeate_m3h"] > 0.0
