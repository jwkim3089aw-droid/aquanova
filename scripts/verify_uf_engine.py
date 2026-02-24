# scripts/verify_uf_engine.py
import sys
import json
from pathlib import Path

# AquaNova 프로젝트 루트 디렉토리를 sys.path에 추가하여 app 모듈 임포트 가능하게 설정
current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent
sys.path.insert(0, str(project_root))

from app.schemas.simulation import FeedInput, StageConfig, UFMaintenanceConfig
from app.services.simulation.modules.uf import UFModule


def print_report(title: str, metric):
    """결과값을 보기 좋게 출력하는 헬퍼 함수"""
    print(f"\n{'='*50}")
    print(f"🚀 {title}")
    print(f"{'='*50}")

    print("[1. 🌊 흐름 및 물수지 (Flow & Mass Balance)]")
    print(f"  - 원수 취수량 (Raw Intake) : {metric.Qf:.3f} m³/h (스트레이너 통과 전)")
    print(
        f"  - 총 생산량 (Gross Flow)   : {metric.gross_flow_m3h:.3f} m³/h (순시 유량)"
    )
    print(
        f"  - 순 생산량 (Net Flow, Qp) : {metric.net_flow_m3h:.3f} m³/h (세정 손실 제외)"
    )
    print(
        f"  - 총 폐수량 (Waste, Qc)    : {metric.Qc:.3f} m³/h (역세+FF+스트레이너 손실)"
    )
    print(f"  - 스트레이너 회수율        : {metric.recovery_pct:.2f}% (Gross Recovery)")
    print(
        f"  - 최종 순 회수율           : {metric.net_recovery_pct:.2f}% (Net Recovery)"
    )

    print("\n[2. ⚙️ 압력 및 에너지 (Pressure & Energy)]")
    print(f"  - 설계 플럭스 (Design Flux): {metric.design_flux_lmh:.1f} LMH")
    print(f"  - 평균 플럭스 (Avg Flux)   : {metric.average_flux_lmh:.1f} LMH")
    print(f"  - 막간 차압 (TMP)          : {metric.tmp_bar:.3f} bar")
    print(f"  - 유입 압력 (Feed Press)   : {metric.p_in_bar:.3f} bar")
    print(f"  - 비에너지 소모량 (SEC)    : {metric.sec_kwhm3:.4f} kWh/m³")

    print("\n[3. 🧪 수질 (Chemistry - TDS Pass-through)]")
    print(f"  - Feed TDS  : {metric.Cf} mg/L")
    print(f"  - Perm TDS  : {metric.Cp} mg/L (UF는 염분을 제거하지 않음)")

    print(
        f"\n  * Temp Correction Factor: {metric.chemistry['model']['temp_corr_factor']:.3f}"
    )


def run_tests():
    engine = UFModule()

    # 공통 유지보수 설정 (WAVE 기본값)
    maint_config = UFMaintenanceConfig(
        filtration_duration_min=60.0,
        backwash_duration_sec=60.0,
        air_scour_duration_sec=30.0,
        forward_flush_duration_sec=30.0,
        backwash_flux_lmh=100.0,
        forward_flush_flow_m3h_per_mod=2.83,
    )

    # ---------------------------------------------------------
    # Scenario 1: WAVE Default (25°C, 기본 조건)
    # ---------------------------------------------------------
    feed_1 = FeedInput(flow_m3h=100.0, tds_mgL=500.0, temperature_C=25.0, ph=7.0)
    config_1 = StageConfig(
        module_type="UF",
        elements=10,
        membrane_area_m2_per_element=77.0,  # SFP-2860XP 기준
        design_flux_lmh=55.5,
        strainer_recovery_pct=99.5,
        uf_maintenance=maint_config,
    )
    result_1 = engine.compute(config_1, feed_1)
    print_report("Scenario 1: WAVE 기본 설계 (25°C, 55.5 LMH)", result_1)

    # ---------------------------------------------------------
    # Scenario 2: 저수온 조건 (5°C) -> 점도 증가로 TMP 상승 확인
    # ---------------------------------------------------------
    feed_2 = FeedInput(flow_m3h=100.0, tds_mgL=500.0, temperature_C=5.0, ph=7.0)
    config_2 = StageConfig(
        module_type="UF",
        elements=10,
        membrane_area_m2_per_element=77.0,
        design_flux_lmh=55.5,
        strainer_recovery_pct=99.5,
        uf_maintenance=maint_config,
    )
    result_2 = engine.compute(config_2, feed_2)
    print_report("Scenario 2: 겨울철 저수온 (5°C) - TMP 상승 테스트", result_2)

    # ---------------------------------------------------------
    # Scenario 3: 고파울링 & 스트레이너 손실 악화 (물수지 변화 확인)
    # ---------------------------------------------------------
    feed_3 = FeedInput(flow_m3h=100.0, tds_mgL=500.0, temperature_C=25.0, ph=7.0)
    config_3 = StageConfig(
        module_type="UF",
        elements=10,
        membrane_area_m2_per_element=77.0,
        design_flux_lmh=55.5,
        strainer_recovery_pct=90.0,  # 스트레이너 효율 90%로 하락
        fouling_factor=1.5,  # 파울링 저항 1.5배 증가
        uf_maintenance=maint_config,
    )
    result_3 = engine.compute(config_3, feed_3)
    print_report("Scenario 3: 고파울링 및 스트레이너 효율 저하 (90%)", result_3)


if __name__ == "__main__":
    run_tests()
