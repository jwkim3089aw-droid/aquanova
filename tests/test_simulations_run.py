# ./tests/test_simulations_run.py

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_run_simulation_success():
    payload = {
        "project_id": "11111111-1111-1111-1111-111111111111",
        "scenario_name": "RO_2Stage_A",
        "feed": {
            "flow_m3h": 20.0,
            "tds_mgL": 2500,
            "temperature_C": 25.0,
            "ph": 7.2
        },
        "stages": [
            {
                "type": "RO",
                "elements": 6,
                "pressure_bar": 15.0,
                "recovery_target_pct": 45.0
            }
        ],
        "options": {}
    }
    res = client.post("/api/v1/simulations:run", json=payload)
    assert res.status_code == 200
    body = res.json()
    assert "scenario_id" in body
    assert body["kpi"]["recovery_pct"] >= 40.0

def test_run_simulation_validation_error():
    bad = {
        "project_id": "not-a-uuid",
        "scenario_name": "",
        "feed": {
            "flow_m3h": -1,
            "tds_mgL": -10,
            "temperature_C": 200,
            "ph": 20
        },
        "stages": [
            {
                "type": "UF",
                "elements": 0,
                "pressure_bar": 0
            }
        ],
        "options": {}
    }
    res = client.post("/api/v1/simulations:run", json=bad)
    assert res.status_code == 422
    body = res.json()
    assert body.get("code") == "INVALID_INPUT"