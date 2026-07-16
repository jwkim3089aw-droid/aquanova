# scripts/test_ro_autotuner.py
import json
import logging
import sys
import re
import numpy as np
from scipy.optimize import minimize
from collections import defaultdict

from app.services.simulation.modules.ro import ROModule
from app.schemas.simulation import FeedInput, StageConfig
from app.schemas.common import ModuleType

logger = logging.getLogger("AutoTuner")
logger.setLevel(logging.INFO)

stream_handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter(
    "%(asctime)s | %(levelname)-7s | %(message)s", datefmt="%H:%M:%S"
)
stream_handler.setFormatter(formatter)
logger.addHandler(stream_handler)

DB_PATH = "./.data/wave_extracted_dataset.json"

MEMBRANE_BASELINES = {
    "FilmTec BW30-400": {"A": 4.0, "B": 0.5},
    "FilmTec ECO PRO-440": {"A": 5.0, "B": 0.3},
    "FilmTec SW30HRLE-400": {"A": 1.15, "B": 0.05},
    "FilmTec SOAR 3000i": {"A": 3.5, "B": 0.1},
    "FilmTec SOAR 4000i": {"A": 4.5, "B": 0.08},
    "FilmTec SOAR 5000i": {"A": 5.5, "B": 0.06},
    "FilmTec SOAR 6000i": {"A": 6.5, "B": 0.04},
    "FilmTec SOAR 7000i": {"A": 7.5, "B": 0.02},
    "FilmTec NF270-400": {"A": 12.5, "B": 0.1},
}


def normalize_model_name(name: str) -> str:
    return re.sub(r"\s+", " ", name.strip())


def load_training_data():
    try:
        with open(DB_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

        grouped = defaultdict(list)
        for record in data:
            if (
                record.get("membrane_model")
                and record.get("feed_pressure") is not None
                and record.get("feed_flow") is not None
            ):
                norm_name = normalize_model_name(record["membrane_model"])
                grouped[norm_name].append(record)
        return grouped
    except Exception as e:
        logger.error(f"데이터베이스 로드 실패: {e}")
        return {}


def run_simulation(calib_params, record):
    engine = ROModule()

    feed = FeedInput(
        flow_m3h=record["feed_flow"],
        tds_mgL=record["feed_tds"],
        temperature_C=record["temperature"],
        pressure_bar=0.0,
    )

    model_name = normalize_model_name(record["membrane_model"])
    baseline = MEMBRANE_BASELINES.get(model_name, {"A": 4.0, "B": 0.5})

    cfg_dict = {
        "module_type": ModuleType.RO,
        "mode": "recovery",
        "recovery_target_pct": record["system_recovery"],
        "membrane_model": model_name,
        "vessel_count": 10,
        "elements_per_vessel": record.get("elements_per_vessel") or 6,
        "membrane_A_lmh_bar": baseline["A"],
        "membrane_B_lmh": baseline["B"],
        "dp_module_bar": calib_params.get("dp_module_bar", 0.15),
        "temp_corr_factor_A": calib_params.get("temp_corr_factor_A", 2640.0),
        "temp_corr_factor_B": calib_params.get("temp_corr_factor_B", 3500.0),
        "cp_tuning_factor": calib_params.get("cp_tuning_factor", 0.25),
    }

    config = StageConfig(**cfg_dict)

    try:
        return engine.compute(config, feed)
    except Exception:
        return None


def objective_pressure(x, records, has_temp_variance):
    dp_mult, temp_a_mult = x

    # 페널티 함수를 통한 물리 한계치 경계 처리
    if not (0.33 <= dp_mult <= 2.66):
        return 9999.0
    if has_temp_variance and not (0.38 <= temp_a_mult <= 2.27):
        return 9999.0

    dp_val = dp_mult * 0.15
    temp_a_val = (temp_a_mult * 2640.0) if has_temp_variance else 2640.0

    sq_errors = []
    for record in records:
        calib = {"dp_module_bar": dp_val, "temp_corr_factor_A": temp_a_val}
        res = run_simulation(calib, record)
        if not res or res.p_in_bar is None:
            return 9999.0
        sq_errors.append((res.p_in_bar - record["feed_pressure"]) ** 2)

    return float(np.mean(sq_errors))


def objective_tds(x, records, has_temp_variance, fixed_pressure_calib):
    cp_mult, temp_b_mult = x

    if not (0.20 <= cp_mult <= 10.0):
        return 9999.0
    if has_temp_variance and not (0.28 <= temp_b_mult <= 2.57):
        return 9999.0

    cp_val = cp_mult * 0.25
    temp_b_val = (temp_b_mult * 3500.0) if has_temp_variance else 3500.0

    sq_errors = []
    for record in records:
        calib = {
            "dp_module_bar": fixed_pressure_calib[0],
            "temp_corr_factor_A": fixed_pressure_calib[1],
            "cp_tuning_factor": cp_val,
            "temp_corr_factor_B": temp_b_val,
        }
        res = run_simulation(calib, record)
        if not res or res.Cp is None:
            return 9999.0
        sq_errors.append((res.Cp - record["permeate_tds"]) ** 2)

    return float(np.mean(sq_errors))


def run_autotuner():
    logger.info("============================================================")
    logger.info(" AquaNova 오토 튜너 수치 제어 보정 엔진 구동 (무구배 최적화)")
    logger.info("============================================================")

    training_data = load_training_data()
    if not training_data:
        logger.warning("학습용 유효 데이터셋이 존재하지 않습니다.")
        return

    for model_name, records in training_data.items():
        logger.info(
            f"모델 분석 최적화 루프 개시: {model_name} (총 {len(records)} 레코드)"
        )

        # 수온 데이터 분산 검사
        temps = [r["temperature"] for r in records if r.get("temperature") is not None]
        has_temp_variance = len(set(temps)) > 1

        if not has_temp_variance:
            logger.info(
                " -> 단일 온도 레코드 검출: 온도 활성화 에너지 파라미터 튜닝 생략"
            )

        # 1단계: 수리역학(압력) 파라미터 최적화
        logger.info(" -> [단계 1] 유체역학적 마찰 및 NDP 손실 파라미터 연산 중")
        initial_guess_press = [1.0, 1.0]

        res_press = minimize(
            objective_pressure,
            x0=np.array(initial_guess_press),
            args=(records, has_temp_variance),
            method="Nelder-Mead",
            options={"xatol": 1e-4, "fatol": 1e-4, "maxiter": 200},
        )

        best_dp_mult, best_temp_a_mult = res_press.x
        best_dp = best_dp_mult * 0.15
        best_temp_a = (best_temp_a_mult * 2640.0) if has_temp_variance else 2640.0
        logger.info(
            f"    - 수렴 최적화 완료 -> dp_bar: {best_dp:.4f}, temp_A: {best_temp_a:.1f}"
        )

        # 2단계: 물질전달(수질) 파라미터 최적화
        logger.info(" -> [단계 2] 경막 농도 분극 및 이온 선택성 투과 계수 연산 중")
        initial_guess_tds = [1.0, 1.0]

        res_tds = minimize(
            objective_tds,
            x0=np.array(initial_guess_tds),
            args=(records, has_temp_variance, (best_dp, best_temp_a)),
            method="Nelder-Mead",
            options={"xatol": 1e-4, "fatol": 1e-4, "maxiter": 200},
        )

        best_cp_mult, best_temp_b_mult = res_tds.x
        best_cp = best_cp_mult * 0.25
        best_temp_b = (best_temp_b_mult * 3500.0) if has_temp_variance else 3500.0
        logger.info(
            f"    - 수렴 최적화 완료 -> cp_tune: {best_cp:.4f}, temp_B: {best_temp_b:.1f}"
        )

        logger.info(f"[{model_name} 보정 프로필 설정 구조체 스펙 수치]")
        print(f"  dp_per_elem_bar: {best_dp:.3f},")
        print(f"  cp_adjustment_factor: {best_cp:.3f},")
        print(f"  temp_corr_factor_A: {best_temp_a:.1f},")
        print(f"  temp_corr_factor_B: {best_temp_b:.1f},")


if __name__ == "__main__":
    run_autotuner()
