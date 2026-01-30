# ./tests/test_api_simulation_reports.py
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.mark.asyncio
async def test_simulation_and_report_flow(db_session):
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. 시뮬레이션 실행
        sim_payload = {
            "project_id": "11111111-1111-1111-1111-111111111111",
            "scenario_name": "pytest_scenario",
            "feed": {
                "flow_m3h": 20.0,
                "tds_mgL": 2500,
                "temperature_C": 25.0,
                "ph": 7.2,
            },
            "stages": [
                {
                    "type": "RO",
                    "elements": 6,
                    "pressure_bar": 15.0,
                    "recovery_target_pct": 45.0,
                }
            ],
            "options": {"antiscalant": True},
        }

        resp = await ac.post("/api/v1/simulations:run", json=sim_payload)
        assert resp.status_code == 200
        sim_data = resp.json()
        scenario_id = sim_data["scenario_id"]

        # 2. 리포트 큐잉
        resp = await ac.post("/api/v1/reports:enqueue", json={"scenario_id": scenario_id})
        assert resp.status_code == 200
        enqueue_data = resp.json()
        job_id = enqueue_data["job_id"]

        # 3. 리포트 상태 조회
        resp = await ac.get(f"/api/v1/reports/{job_id}")
        assert resp.status_code == 200
        status_data = resp.json()
        assert status_data["job_id"] == job_id
        assert status_data["status"] == "queued"