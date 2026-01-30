# check_hrro_graph.py
import requests
import json
import sys

# --------------------------------------------------------
# 1. 설정
# --------------------------------------------------------
API_URL = "http://127.0.0.1:8003/api/v1/simulation/run"
HEADERS = {"Content-Type": "application/json"}

# Visualization.tsx에서 요구하는 키 목록
REQUIRED_KEYS = {"time_min", "tds_mgL", "pressure_bar", "flux_lmh", "recovery_pct"}

# --------------------------------------------------------
# 2. HRRO 테스트 페이로드 (Schema Validation 완벽 대응)
# --------------------------------------------------------
payload = {
    # 'feed' 객체 내부 필드명 수정 (TDS -> tds_mgL 등)
    "feed": {
        "flow_m3h": 10.0,  # 필수 필드 추가
        "tds_mgL": 5000.0,  # TDS -> tds_mgL 로 이름 변경
        "temperature_C": 25.0,  # temp_c -> temperature_C 로 이름 변경
        "ph": 7.0,  # 필수 필드 추가
        "ions": {},  # (선택) 이온 조성
    },
    "stages": [
        {
            "stage_id": 1,
            "module_type": "HRRO",
            "element_model": "BW30-400",
            "quantity": 1,
            "recovery": 0.8,
            "params": {"pressure_limit_bar": 80, "batch_mode": True},
        }
    ],
}


def check_graph_data():
    print(f"🚀 Sending HRRO Simulation Request to {API_URL}...")

    try:
        response = requests.post(API_URL, json=payload, headers=HEADERS, timeout=10)
    except requests.exceptions.ConnectionError:
        print("❌ [Error] 서버에 연결할 수 없습니다. run_aquanova.ps1이 켜져 있나요?")
        sys.exit(1)

    if response.status_code != 200:
        print(f"❌ [Error] API 요청 실패 (Status: {response.status_code})")
        print("   서버 응답:", response.text)
        sys.exit(1)

    data = response.json()

    # 결과 파싱
    stage_metrics = data.get("stage_metrics", [])
    if not stage_metrics:
        stage_metrics = data.get("results", {}).get("stage_metrics", [])

    print(f"📦 Received Data. Found {len(stage_metrics)} stages.")

    hrro_stage = None
    for stage in stage_metrics:
        m_type = stage.get("module_type", "RO")
        print(f"   - Stage {stage.get('stage', '?')}: Type='{m_type}'")

        if m_type == "HRRO":
            hrro_stage = stage
            break

    if not hrro_stage:
        print("❌ [Fail] HRRO 스테이지를 찾을 수 없습니다.")
        sys.exit(1)

    # --------------------------------------------------------
    # 3. 핵심 검증: time_history 확인
    # --------------------------------------------------------
    time_history = hrro_stage.get("time_history")

    if not time_history:
        print(
            "❌ [Fail] 'time_history' 데이터가 비어있거나 없습니다. (Backend Logic Error)"
        )
        sys.exit(1)

    if not isinstance(time_history, list) or len(time_history) == 0:
        print("❌ [Fail] 'time_history'가 리스트가 아니거나 비어있습니다.")
        sys.exit(1)

    # 첫 번째 데이터 포인트 검사
    first_point = time_history[0]
    received_keys = set(first_point.keys())

    print("\n🔍 [Key Verification] Visualization.tsx vs Backend Data")
    print("-" * 50)

    missing_keys = REQUIRED_KEYS - received_keys

    print(f"   Frontend Needs: {sorted(list(REQUIRED_KEYS))}")
    print(f"   Backend Sends : {sorted(list(received_keys))}")

    if missing_keys:
        print("-" * 50)
        print(f"❌ [CRITICAL FAIL] 그래프가 그려지지 않는 이유 발견!")
        print(f"   백엔드에서 다음 키를 보내지 않고 있습니다: {missing_keys}")
        print("   👉 app/services/simulation/solvers/hrro.py 파일을 수정해야 합니다.")
    else:
        print("-" * 50)
        print(
            "✅ [PASS] 데이터 키가 완벽하게 일치합니다. 그래프가 그려져야 정상입니다."
        )


if __name__ == "__main__":
    check_graph_data()
