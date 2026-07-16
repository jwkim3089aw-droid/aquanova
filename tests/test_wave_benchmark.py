# tests/test_wave_benchmark.py
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.simulation.engine import SimulationEngine
from app.schemas.simulation import ScenarioInput


def run_wave_benchmark():
    print("=== AquaNova Engine vs DuPont WAVE Benchmark Test ===\n")

    # [1] DuPont WAVE에서 미리 뽑아둔 '정답지' (예시 수치)
    # 실제 WAVE 리포트(PDF)에 적혀있는 숫자를 여기에 입력합니다.
    wave_target = {
        "feed_pressure_bar": 58.4,  # WAVE가 계산한 필요 압력
        "permeate_tds_mgl": 285.5,  # WAVE가 계산한 생산수 수질
        "sec_kwh_m3": 2.95,  # WAVE가 계산한 전력 소모량
    }

    # [2] WAVE에 넣었던 것과 똑같은 입력값 세팅
    payload = {
        "project_id": "wave_bench",
        "scenario_name": "WAVE SWRO Comparison",
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
                    "recovery_target_pct": 45,  # 회수율 45% 타겟
                    "elements": 60,
                    "membrane_area_m2": 37.2,  # SW30HRLE-400 스펙
                    "membrane_A_lmh_bar": 1.05,  # 물 투과 계수 (A-value)
                    "membrane_B_lmh": 0.35,  # 염 투과 계수 (B-value)
                    "membrane_salt_rejection_pct": 99.8,
                },
            }
        ],
        "options": {},
    }

    # [3] 우리 엔진 돌리기
    engine = SimulationEngine()
    print("[*] Running AquaNova Simulation Engine...")
    out = engine.run(ScenarioInput(**payload))
    kpi = out.kpi.model_dump() if out.kpi else {}

    # 결과 추출
    our_pressure = (
        kpi.get("ndp_bar", 0.0) + 28.5
    )  # 삼투압(대략) 보정 후 총 Feed Pressure 추정
    our_tds = kpi.get("prod_tds", 0.0)
    our_sec = kpi.get("sec_kwhm3", 0.0)

    print("\n--- Comparison Results ---")
    print(
        f" 1) Feed Pressure | WAVE: {wave_target['feed_pressure_bar']} bar | AquaNova: {our_pressure:.2f} bar"
    )
    print(
        f" 2) Permeate TDS | WAVE: {wave_target['permeate_tds_mgl']} mg/L | AquaNova: {our_tds:.2f} mg/L"
    )
    print(
        f" 3) Energy (SEC) | WAVE: {wave_target['sec_kwh_m3']} kWh/m3 | AquaNova: {our_sec:.2f} kWh/m3"
    )
    print("-" * 26)

    # [4] 오차율(Error Margin) 채점 (허용 오차 5% 이내)
    tolerance = 0.05

    def check_error(name, target, ours):
        err = abs(ours - target) / target
        status = "✅ PASS" if err <= tolerance else "❌ FAIL"
        print(f"[{status}] {name} Error: {err*100:.2f}% (Tolerance: {tolerance*100}%)")

    print("\n=== Benchmark Verdict ===")
    check_error("Feed Pressure", wave_target["feed_pressure_bar"], our_pressure)
    check_error("Permeate TDS", wave_target["permeate_tds_mgl"], our_tds)
    check_error("Energy (SEC)", wave_target["sec_kwh_m3"], our_sec)


if __name__ == "__main__":
    run_wave_benchmark()
