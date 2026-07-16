# tests/test_sensitivity_engine.py
import os
import sys
from copy import deepcopy

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.simulation.engine import SimulationEngine
from app.schemas.simulation import ScenarioInput


def extract_metrics(sim_out, case_name=""):
    kpi = sim_out.kpi.model_dump() if sim_out.kpi else {}

    permeate_flow = kpi.get("permeate_m3h", 0.0)
    energy_sec = kpi.get("sec_kwhm3", 0.0)
    ndp_bar = kpi.get("ndp_bar", 0.0)

    print(f"--- {case_name} ---")
    print(f" 1) Permeate Flow : {permeate_flow:.2f} m3/h")
    print(f" 2) Req. Pressure (NDP) : {ndp_bar:.2f} bar")
    print(f" 3) SEC (Energy)  : {energy_sec:.3f} kWh/m3")
    print("-" * 45)

    return permeate_flow, ndp_bar, energy_sec


def run_sensitivity_test():
    print("=== AquaNova Core Physics Engine Validation ===\n")

    base_payload = {
        "project_id": "engine_test",
        "scenario_name": "Baseline",
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
                    "pressure_bar": 60,  # 💡 운전 모드(Operation) 강제 고정
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

    engine = SimulationEngine()

    # [Case 1] Baseline (표준 해수)
    print("[Case 1] Baseline (Temp: 25C, TDS: 35,000 mg/L)")
    out_base = engine.run(ScenarioInput(**base_payload))
    flow_base, ndp_base, sec_base = extract_metrics(out_base, "Baseline Results")

    # [Case 2] High Salinity (고농도 해수 - 삼투압 증가)
    print("\n[Case 2] High Salinity (Temp: 25C, TDS: 45,000 mg/L)")
    payload_hs = deepcopy(base_payload)
    payload_hs["scenario_name"] = "High Salinity"
    payload_hs["feed"]["tds_mgL"] = 45000
    out_hs = engine.run(ScenarioInput(**payload_hs))
    flow_hs, ndp_hs, sec_hs = extract_metrics(out_hs, "High Salinity Results")

    # [Case 3] Low Temperature (겨울철 저수온 - 점도 증가)
    print("\n[Case 3] Low Temperature (Temp: 15C, TDS: 35,000 mg/L)")
    payload_lt = deepcopy(base_payload)
    payload_lt["scenario_name"] = "Low Temp"
    payload_lt["feed"]["temperature_C"] = 15
    out_lt = engine.run(ScenarioInput(**payload_lt))
    flow_lt, ndp_lt, sec_lt = extract_metrics(out_lt, "Low Temp Results")

    # Validation Logic (고정 압력 시스템의 물리 법칙 적용)
    print("\n=== Engine Physics Validation Result ===")

    if flow_hs < flow_base and sec_hs > sec_base:
        print(
            "✅ [PASS] Salinity Physics: High TDS -> Osmotic Pressure UP -> Permeate Flow DOWN -> SEC UP."
        )
    else:
        print("❌ [FAIL] Salinity physics validation failed.")

    if flow_lt < flow_base and sec_lt > sec_base:
        print(
            "✅ [PASS] Temp Physics: Low Temp -> Viscosity UP -> Permeate Flow DOWN -> SEC UP."
        )
    else:
        print("❌ [FAIL] Temperature physics validation failed.")


if __name__ == "__main__":
    run_sensitivity_test()
