import requests
import json
import sys

# ✅ 서버 주소 (본인의 환경에 맞게 수정하세요. 보통 8003 포트)
API_URL = "http://127.0.0.1:8003/api/v1/membranes"


def check_membrane_data():
    print(f"📡 Connecting to {API_URL}...")

    try:
        response = requests.get(API_URL)
        response.raise_for_status()
        data = response.json()

        print(f"✅ Connection Successful! Found {len(data)} membranes.\n")

        # 확인하고 싶은 모델명 (부분 일치 검색)
        target_name = "DuPont"

        found = False
        for m in data:
            # 제조사나 이름에 target_name이 포함된 첫 번째 모델을 찾음
            if (
                target_name.lower() in str(m.get("vendor", "")).lower()
                or target_name.lower() in str(m.get("name", "")).lower()
            ):

                print(f"🔎 inspect Target: [{m.get('vendor')}] {m.get('id')}")
                print("=" * 60)
                print(json.dumps(m, indent=4))  # 전체 데이터 출력
                print("=" * 60)

                # 핵심 필드 값 검증
                print("\n[🧐 Critical Fields Check]")
                print(f"👉 Area (area_m2)        : {m.get('area_m2')}")
                print(
                    f"👉 A-Val (A_lmh_bar)    : {m.get('A_lmh_bar')}  <-- 여기가 0인지 확인하세요"
                )
                print(
                    f"👉 B-Val (B_mps)        : {m.get('B_mps')}      <-- 여기가 0인지 확인하세요"
                )
                print(f"👉 Rejection (salt_...) : {m.get('salt_rejection_pct')}")

                # Legacy Key 확인
                print("\n[Legacy Key Check (if exists)]")
                print(f"👉 perm_A               : {m.get('perm_A', 'Not Found')}")
                print(f"👉 salt_B               : {m.get('salt_B', 'Not Found')}")

                found = True
                break

        if not found:
            print(f"❌ '{target_name}' 모델을 찾을 수 없습니다.")

    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    check_membrane_data()
