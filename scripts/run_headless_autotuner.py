# scripts/run_headless_autotuner.py
import os
import sys
import json
import logging
from typing import Dict, Any

# 프로젝트 루트 경로를 시스템 패스에 추가하여 내부 모듈 임포트 허용
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# AquaNova 핵심 시뮬레이션 엔진 및 스키마 임포트
from app.services.simulation.engine import SimulationEngine
from app.schemas.simulation import ScenarioInput

logger = logging.getLogger("AutoTuner")
logger.setLevel(logging.INFO)
stream_handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter(
    "%(asctime)s | %(levelname)-7s | %(message)s", datefmt="%H:%M:%S"
)
stream_handler.setFormatter(formatter)
logger.addHandler(stream_handler)


def optimize_membrane_constants(
    engine: SimulationEngine, wave_data: Dict[str, Any]
) -> Dict[str, Any]:
    """WAVE 타겟 수치(압력, TDS)에 도달할 때까지 A, B 상수를 Gradient Descent 방식으로 역산"""

    target_pressure = wave_data.get("feed_pressure", 0)
    target_tds = wave_data.get("permeate_tds", 0)
    feed_tds = wave_data.get("feed_tds", 2000.0)

    # 1. 초기 추정치 (Guess)
    A_val = 3.0  # 수분 투과도 초기값
    B_val = 0.1  # 염 투과도 초기값

    # 2. 학습률 (Learning Rate)
    lr_A = 0.05
    lr_B = 0.005

    elements = wave_data.get("elements_per_vessel", 6) or 6

    logger.info(f"🔄 튜닝 시작: {wave_data['membrane_model']}")
    logger.info(f"   [목표] 압력: {target_pressure} bar, 생산수 TDS: {target_tds} mg/L")

    best_A, best_B = A_val, B_val
    min_error = float("inf")

    # API 스키마(Enum)를 만족하기 위한 수질 타입 동적 할당
    valid_water_type = "SD Seawater (Well)" if feed_tds > 20000 else "RO/NF Well Water"

    for iteration in range(1, 51):
        payload = {
            "feed": {
                "flow_m3h": wave_data.get("feed_flow", 100.0),
                "ph": wave_data.get("feed_ph", 7.2) or 7.2,
                "pressure_bar": 0.0,
                "sdi15": 2.0,
                "tds_mgL": feed_tds,
                "temperature_C": wave_data.get("temperature", 25.0),
                "water_subtype": "Wells",
                "water_type": valid_water_type,  # 💡 Pydantic Enum 에러 픽스
            },
            "project_id": "autotune",
            "scenario_name": wave_data.get("membrane_model", "tuning"),
            "simulation_id": "auto_tune_process",
            "stages": [
                {
                    "elements": elements,
                    "membrane_A_lmh_bar": A_val,
                    "membrane_B_lmh": B_val,
                    "membrane_area_m2": 40.0,
                    "membrane_salt_rejection_pct": 99.5,
                    "module_type": "RO",
                    "pressure_bar": target_pressure,
                    "recovery_target_pct": wave_data.get("system_recovery", 50.0),
                }
            ],
        }

        try:
            scenario_input = ScenarioInput(**payload)
            result = engine.run(scenario_input)

            res_data = (
                result.kpi.model_dump()
                if hasattr(result, "kpi")
                else result.model_dump()
            )

            sim_pressure = res_data.get(
                "ndp_bar", res_data.get("total_feed_pressure", 0)
            )
            sim_tds = res_data.get("prod_tds", res_data.get("permeate_tds", 0))

            err_pressure = sim_pressure - target_pressure
            err_tds = sim_tds - target_tds
            total_error = abs(err_pressure) + abs(err_tds)

            if total_error < min_error:
                min_error = total_error
                best_A, best_B = A_val, B_val

            if abs(err_pressure) < 0.1 and abs(err_tds) < 0.1:
                logger.info(
                    f"   ✅ [수렴 성공] {iteration}회 만에 최적값 도달! (A={A_val:.4f}, B={B_val:.4f})"
                )
                break

            # 보정 알고리즘
            A_val += err_pressure * lr_A
            B_val -= err_tds * lr_B

            # 한계치 제어
            A_val = max(0.1, min(A_val, 15.0))
            B_val = max(0.001, min(B_val, 5.0))

        except Exception as e:
            logger.error(f"   ❌ 시뮬레이션 엔진 에러 발생: {e}")
            break

    logger.info(
        f"   🎯 [최종결과] A = {best_A:.5f}, B = {best_B:.5f} (남은 오차: {min_error:.3f})"
    )

    return {
        "membrane_model": wave_data["membrane_model"],
        "A_lmh_bar": round(best_A, 5),
        "B_lmh": round(best_B, 5),
        "final_error": round(min_error, 3),
    }


def main():
    logger.info("============================================================")
    logger.info(" AquaNova Headless Auto-Tuner (백엔드 다이렉트 최적화) 가동")
    logger.info("============================================================")

    db_path = "./.data/wave_extracted_dataset.json"
    output_path = "./.data/calibrated_membranes_constants.json"

    if not os.path.exists(db_path):
        logger.error("데이터셋 파일이 없습니다.")
        return

    with open(db_path, "r", encoding="utf-8") as f:
        wave_dataset = json.load(f)

    engine = SimulationEngine()
    calibration_results = []

    for idx, data in enumerate(wave_dataset, 1):
        if data.get("process_type") == "UF":
            continue

        if not data.get("feed_pressure") or not data.get("permeate_tds"):
            continue

        result = optimize_membrane_constants(engine, data)
        calibration_results.append(result)
        logger.info("-" * 60)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(calibration_results, f, indent=4, ensure_ascii=False)

    logger.info(f"🎉 모든 막에 대한 물리 보정(Calibration) 완료!")
    logger.info(f"💾 보정 상수 저장 위치: {output_path}")


if __name__ == "__main__":
    main()
