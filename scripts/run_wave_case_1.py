# scripts/run_wave_case_1.py
import os
import sys
import logging

# 프로젝트 루트 경로 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.simulation.engine import SimulationEngine
from app.schemas.simulation import ScenarioInput

logger = logging.getLogger("WaveCase1")
logger.setLevel(logging.INFO)
stream_handler = logging.StreamHandler(sys.stdout)
stream_handler.setFormatter(logging.Formatter("%(message)s"))
logger.addHandler(stream_handler)


def run_case():
    logger.info("============================================================")
    logger.info(" 🌊 WAVE Case 1 -> 💧 AquaNova 엔진 1:1 정밀 매핑 테스트")
    logger.info("============================================================")

    # 💡 WAVE 리포트의 수치와 AquaNova Schema 필드를 100% 일치시킨 Payload
    payload = {
        "project_id": "wave_test",
        "scenario_name": "WAVE Case 1 (BW30-400)",
        "simulation_id": "case-1",
        "feed": {
            "flow_m3h": 99.9,  # WAVE: Net Feed to Pass 1
            "tds_mgL": 470.1,  # WAVE: Feed TDSa
            "temperature_C": 25.0,  # WAVE: Temperature (RO 25.0°C)
            "ph": 7.7,  # WAVE: pH
            "pressure_bar": 0.0,
            "water_type": "RO/NF Well Water",
            "water_subtype": "Well Water (SDI < 3)",
            # 💡 [핵심] WAVE 리포트 'RO Solute Concentrations' 정밀 이온 매핑
            "ions": {
                "na": 9.14,
                "k": 2.81,
                "ca": 82.40,
                "mg": 9.04,
                "hco3": 240.4,
                "co3": 1.05,
                "cl": 1.29,
                "so4": 62.69,
                "sio2": 60.70,
                "co2": 6.28,
            },
        },
        "stages": [
            {
                "module_type": "RO",
                "membrane_model": "FilmTec BW30-400",
                "vessel_count": 10,  # WAVE: 10 PV
                "elements_per_vessel": 6,  # WAVE: 6 Els per PV
                "recovery_target_pct": 75.0,  # WAVE: Pass Recovery 75.0%
                "flow_factor": 0.85,  # WAVE: Flow Factor Per Stage 0.85
                # 💡 프론트엔드가 백엔드에 의무적으로 넘겨주어야 하는 기초 물리 스펙
                "membrane_area_m2": 37.16,  # 2230 m2 / 60 ea = 37.16
                "membrane_A_lmh_bar": 3.4,
                "membrane_B_lmh": 0.188,
                # 💡 이전에 오토튜너가 산출했던 최적의 보정 상수 (공식 변수명 적용)
                "A_correction_factor": 1.034,
                "B_correction_factor": 0.455,
                "dp_module_bar": 0.150,  # (수정) 엔진 규격 엄수
                "cp_tuning_factor": 0.297,  # (수정) 엔진 규격 엄수
                "temp_corr_factor_A": 2640.0,
                "temp_corr_factor_B": 3500.0,
            }
        ],
    }

    try:
        scenario_input = ScenarioInput(**payload)
        engine = SimulationEngine()

        logger.info("\n▶️ 입력된 WAVE 정밀 스펙으로 시뮬레이션 연산 중...")
        result = engine.run(scenario_input)

        # Pydantic 모델 안전 접근 (엔진 버전에 따른 대응)
        res_data = (
            result.kpi.model_dump() if hasattr(result, "kpi") else result.model_dump()
        )

        sim_pressure = res_data.get(
            "p_in_bar", res_data.get("ndp_bar", res_data.get("total_feed_pressure", 0))
        )
        sim_tds = res_data.get(
            "Cp", res_data.get("prod_tds", res_data.get("permeate_tds", 0))
        )

        # WAVE 정답지 (타겟)
        target_p = 13.1
        target_t = 4.85

        err_p = abs(sim_pressure - target_p) / target_p * 100 if target_p else 0
        err_t = abs(sim_tds - target_t) / target_t * 100 if target_t else 0

        logger.info("\n📊 [연산 결과 비교: WAVE vs AquaNova]")
        logger.info("-" * 65)
        logger.info(
            f" {'구분':<15} | {'WAVE 리포트':<15} | {'AquaNova':<15} | {'오차율'}"
        )
        logger.info("-" * 65)
        logger.info(
            f" {'유입 압력':<14} | {target_p:>10.2f} bar  | {sim_pressure:>10.2f} bar  | {err_p:>5.2f} %"
        )
        logger.info(
            f" {'생산수 TDS':<13} | {target_t:>10.2f} mg/L | {sim_tds:>10.2f} mg/L | {err_t:>5.2f} %"
        )
        logger.info("-" * 65)

    except Exception as e:
        logger.error(f"\n❌ 에러 발생: {e}")


if __name__ == "__main__":
    run_case()
