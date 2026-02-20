import sys
import os
from pathlib import Path

# 프로젝트 루트 경로 추가 (app 모듈을 찾기 위함)
# C:\Users\a\Desktop\프로젝트\AquaNova\code\scripts 에서 실행 시
# 상위 폴더인 code를 python path에 추가합니다.
root_path = Path(__file__).parent.parent
sys.path.append(str(root_path))

from app.services.simulation.modules.uf import UFModule  # 수정: 파일 구조에 맞게 임포트

# 만약 파일 경로가 app/services/simulation/modules/uf.py 라면 아래와 같이 임포트
from app.services.simulation.modules.uf import UFModule
from app.api.v1.schemas import StageConfig, FeedInput


def run_verification():
    print("=" * 60)
    print("🚀 AquaNova UF Physics Engine Verification")
    print("=" * 60)

    # 1. 테스트 케이스 설정 (WAVE와 동일한 조건 입력)
    # ---------------------------------------------------------
    feed = FeedInput(
        flow_m3h=100.0, tds_mgL=500.0, temperature_C=25.0  # 25도 기준 (TCF 검증용)
    )

    config = StageConfig(
        elements=20,  # 모듈 개수
        membrane_area_m2=51.0,  # 모듈당 면적 (예: DuPont IntegraFlux SFP-2880)
        flux_lmh=60.0,  # 설계 플럭스
        uf_lp_20_lmh_bar=250.0,  # 20도 기준 투과도 (정석값)
        uf_fouling_factor=1.0,  # Clean 상태 가정
        # 하이드로릭 시퀀스 설정 (WAVE 설정값과 동기화)
        filtration_cycle_min=30.0,
        backwash_duration_sec=60.0,
        backwash_flux_lmh=90.0,  # 보통 Flux의 1.5배
        forward_flush_duration_sec=30.0,
        forward_flush_flow_m3h=100.0,
        non_op_time_sec=10.0,  # 밸브 전환 등 비가동 시간
        pump_eff=0.75,
        uf_p_out_bar=0.5,
        uf_header_loss_bar=0.2,
    )

    # 2. 타겟값 설정 (WAVE에서 계산된 결과값을 여기에 입력하세요)
    # ---------------------------------------------------------
    target_tmp = 0.211  # 예시 타겟 (WAVE 결과)
    target_recovery = 94.50  # 예시 타겟 %
    target_sec = 0.0125  # 예시 타겟 kWh/m3

    # 3. AquaNova 엔진 계산 실행
    # ---------------------------------------------------------
    engine = UFModule()
    result = engine.compute(config, feed)
    model_data = result.chemistry["model"]

    # 4. 결과 비교 및 오차 분석
    # ---------------------------------------------------------
    print(f"\n[1] Thermodynamics & Resistance")
    print(f" - TCF (at {feed.temperature_C}°C): {model_data['temp_corr_factor']:.4f}")
    print(f" - Actual Lp: {model_data['lp_actual']:.2f} LMH/bar")
    print(f" - Calc TMP: {result.ndp_bar:.4f} bar  vs  Target: {target_tmp:.4f} bar")

    tmp_error = (
        abs(result.ndp_bar - target_tmp) / target_tmp * 100 if target_tmp > 0 else 0
    )
    print(f" >> TMP Error: {tmp_error:.2f}%")

    print(f"\n[2] Hydraulics & Recovery")
    print(f" - Net Permeate: {result.Qp:.3f} m3/h")
    print(
        f" - Calc Recovery: {result.recovery_pct:.2f}%  vs  Target: {target_recovery:.2f}%"
    )

    rec_error = abs(result.recovery_pct - target_recovery)
    print(f" >> Recovery Gap: {rec_error:.2f} percentage points")

    print(f"\n[3] Energy (SEC)")
    print(
        f" - Calc SEC: {result.sec_kwhm3:.4f} kWh/m3  vs  Target: {target_sec:.4f} kWh/m3"
    )

    print("\n" + "=" * 60)
    if tmp_error < 1.0 and rec_error < 0.5:
        print("✅ VERIFICATION SUCCESS: High-Fidelity Physics Confirmed.")
    else:
        print("⚠️ VERIFICATION WARNING: Check sequence parameters or TCF model.")
    print("=" * 60)


if __name__ == "__main__":
    run_verification()
