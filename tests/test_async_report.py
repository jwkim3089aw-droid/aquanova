# tests/test_async_report.py
import os
import sys
import time
import uuid
import requests

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.session import SessionLocal
from app.db.models.scenario import Scenario

BASE_URL = "http://localhost:8003/api/v1"
TEST_PDF_OUTPUT = "test_async_report_result.pdf"


def setup_dummy_scenario() -> str:
    db = SessionLocal()
    try:
        scn_id = uuid.uuid4()
        prj_id = uuid.uuid4()

        dummy_input = {
            "project_id": str(prj_id),
            "scenario_name": "Pipeline Worker Test",
            "feed": {
                "flow_m3h": 100,
                "tds_mgL": 35000,
                "temperature_C": 25,
                "pressure_bar": 1,
            },
            "stages": [
                {
                    "stage_id": "1",
                    "kind": "RO",
                    "cfg": {
                        "recovery_target_pct": 50,
                        "pressure_bar": 60,
                        "elements": 60,
                        "membrane_area_m2": 37.2,
                        "membrane_A_lmh_bar": 1.5,
                        "membrane_B_lmh": 0.5,
                        "membrane_salt_rejection_pct": 99.5,
                    },
                }
            ],
            "options": {},
        }

        scn = Scenario(
            id=scn_id, project_id=prj_id, name="Worker Test", input_json=dummy_input
        )
        db.add(scn)
        db.commit()

        print(f"[*] Test Scenario created: {scn_id}")
        return str(scn_id)
    finally:
        db.close()


def get_smart_endpoints():
    print("\n[*] Scanning FastAPI Swagger documentation for exact routes...")
    try:
        res = requests.get("http://localhost:8003/openapi.json")
        if res.status_code == 200:
            paths = res.json().get("paths", {})
            enqueue_url = None
            status_url_base = None

            for p, methods in paths.items():
                if "enqueue" in p and "post" in methods:
                    enqueue_url = f"http://localhost:8003{p}"
                elif "{job_id}" in p and "download" not in p and "get" in methods:
                    status_url_base = f"http://localhost:8003{p}".replace(
                        "/{job_id}", ""
                    )

            if enqueue_url and status_url_base:
                print(f"[*] Auto-discovered Enqueue API: {enqueue_url}")
                return enqueue_url, status_url_base
    except Exception as e:
        print(f"[*] Swagger scan failed: {e}")

    print("[!] Could not auto-discover. Using default fallback routes.")
    return f"{BASE_URL}/reports/enqueue", f"{BASE_URL}/reports"


def run_pipeline_test():
    print("=== Async Report Pipeline E2E Test ===")

    enqueue_url, status_base_url = get_smart_endpoints()
    scenario_id = setup_dummy_scenario()

    # 1. Enqueue Request
    print(f"\n[1] Requesting Report Generation (Enqueue)...")
    payload = {"scenario_id": scenario_id}
    res = requests.post(enqueue_url, json=payload)

    if res.status_code != 200:
        print(f"[FAIL] Enqueue failed ({res.status_code}): {res.text}")
        sys.exit(1)

    data = res.json()
    job_id = data["job_id"]
    mode = data.get("mode", "unknown")
    print(f"[*] Job Queued Successfully. Job ID: {job_id} (Mode: {mode})")

    # 2. Polling Status
    print("\n[2] Polling Status via Worker...")
    max_retries = 15
    for i in range(max_retries):
        status_res = requests.get(f"{status_base_url}/{job_id}")

        # 💡 [핵심] JSON 파싱 전에 에러인지 먼저 확인하고 텍스트 그대로 출력!
        if status_res.status_code != 200:
            print(f"[FAIL] Status polling API returned {status_res.status_code} Error!")
            print(f"--> Server Error Details: {status_res.text[:1000]}")
            sys.exit(1)

        status_data = status_res.json()
        current_status = status_data["status"]

        print(f" - Attempt {i+1}/{max_retries}: Status is '{current_status}'")

        if current_status == "succeeded":
            print("[*] Worker successfully generated the PDF!")
            break
        elif current_status == "failed":
            error_msg = status_data.get("error_message", "Unknown error")
            print(f"[FAIL] Worker job failed: {error_msg}")
            sys.exit(1)

        time.sleep(2)
    else:
        print("[FAIL] Timeout: Worker did not complete the job in time.")
        sys.exit(1)

    # 3. Download Artifact
    print("\n[3] Downloading Generated PDF...")
    dl_res = requests.get(f"{status_base_url}/{job_id}/download")

    if dl_res.status_code == 200:
        with open(TEST_PDF_OUTPUT, "wb") as f:
            f.write(dl_res.content)
        print(f"[*] Download successful. File saved to '{TEST_PDF_OUTPUT}'")
        file_size = os.path.getsize(TEST_PDF_OUTPUT)
        print(f"[*] Verified File Size: {file_size} bytes")
    else:
        print(f"[FAIL] Download failed: {dl_res.text}")
        sys.exit(1)

    print("\n=== [SUCCESS] Async Worker Pipeline is fully operational! ===")


if __name__ == "__main__":
    run_pipeline_test()
