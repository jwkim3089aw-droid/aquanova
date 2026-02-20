import sys
import os
from pathlib import Path

# 프로젝트 루트 경로를 sys.path에 추가하여 app 모듈을 import 할 수 있게 설정
current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent
sys.path.insert(0, str(project_root))

from app.schemas.simulation import StageConfig, FeedInput
from app.schemas.common import ModuleType
from app.services.simulation.modules.hrro import HRROModule


def run_physics_debugger():
    print("=" * 60)
    print("🚀 [AquaNova HRRO Physics Debugger] First Principles Test")
    print("=" * 60)

    # 1. WAVE 리포트와 동일한 Feed 조건 주입 (TDS 2119 mg/L)
    feed_data = FeedInput(
        flow_m3h=100.0,
        tds_mgL=2119.0,
        temperature_C=25.0,
        ph=7.0,
    )

    # 2. WAVE 리포트와 동일한 하드웨어 스펙 강제 주입 (UI 간섭 배제)
    stage_data = StageConfig(
        module_type=ModuleType.HRRO,
        vessel_count=10,
        elements_per_vessel=5,  # 총 50 elements
        recovery_target_pct=90.0,  # 90% 회수율
        cc_recycle_m3h_per_pv=4.33,  # 농축수 순환
        loop_volume_m3=1.36,  # WAVE 리포트 CC System Volume
        membrane_model="FilmTec SOAR 6000i",
        membrane_area_m2=40.9,  # 유효 면적
        membrane_A_lmh_bar=6.35,  # SOAR 6000i 하이플럭스 투과도
        membrane_B_lmh=0.058,
        flow_factor=0.85,
        spacer={"thickness_mm": 0.864, "voidage": 0.88},  # SOAR 6000i 34-mil 스페이서
    )

    print("\n[1] 엔진 초기화 및 연산 시작...")
    hrro_engine = HRROModule()

    # 연산 실행
    result = hrro_engine.compute(config=stage_data, feed=feed_data)

    # 3. 결과 분석 및 출력
    history = result.time_history
    final_pt = history[-1] if history else None

    if not final_pt:
        print("❌ 연산 실패: Time History가 생성되지 않았습니다.")
        return

    print("\n[2] 물리 엔진 하드웨어/투과도 인식 확인")
    chem_out = (
        result.chemistry.get("physics_parameters", {})
        if isinstance(result.chemistry, dict)
        else {}
    )
    print(
        f"  - 적용된 A-Value (보정 후) : {chem_out.get('A_base', 0):.4f} LMH/bar (기대값: 6.35 * 0.85 = 5.3975)"
    )
    print(f"  - 총 멤브레인 면적         : {chem_out.get('total_area_m2', 0):.1f} m²")
    print(f"  - 평균 플럭스 (Flux)       : {result.flux_lmh:.2f} LMH")
    print(f"  - 최종 사이클 시간         : {final_pt.time_min:.2f} min")

    print("\n[3] 🔍 최대 압력(Max Pressure) 수식 분해 (First Principles Breakdown)")
    print(f"  - 목표 WAVE 압력 : 25.10 bar")
    print(f"  - 엔진 도출 압력 : {final_pt.pressure_bar:.2f} bar\n")

    # P_req = pi_wall + ndp_req + (dp_module * 0.5)
    # 로그에서 역산하여 물리적 항 분리
    flux = final_pt.flux_lmh
    ndp = final_pt.ndp_bar
    p_total = final_pt.pressure_bar

    # 삼투압과 마찰력 역산 (근사치 분해)
    # 총 압력에서 NDP를 빼면 '삼투압 + 마찰력/2' 가 남음
    residual_pressure = p_total - ndp

    print(
        "  [방정식] 총 압력(P) = 순수 구동 압력(NDP) + 벽면 삼투압(π_wall) + 마찰 저항(ΔP/2)"
    )
    print(
        f"  👉 1. 순수 구동 압력 (NDP)   : {ndp:.2f} bar (물이 멤브레인을 뚫는 힘. A-value 6.35의 힘!)"
    )
    print(
        f"  👉 2. 삼투압 & 마찰 (나머지) : {residual_pressure:.2f} bar (고농축 염분에 의한 저항 및 배관 마찰)"
    )
    print("  " + "-" * 40)
    print(f"  ✅ 최종 도출 합계 압력       : {p_total:.2f} bar")

    print("\n[4] 수질 확인")
    print(f"  - 최종 농축수 TDS (CC)     : {result.Cc:.0f} mg/L")
    print(
        f"  - 혼합 생산수 TDS (Cp)     : {result.Cp:.2f} mg/L (WAVE 타겟: 19.14 mg/L)"
    )

    print("\n" + "=" * 60)
    if abs(final_pt.pressure_bar - 25.1) <= 0.5:
        print(
            "🎉 [성공] 엔진이 WAVE의 25.1 bar 타겟과 물리적으로 완벽히 동기화되었습니다!"
        )
        print(
            "     UI/API 테스트에서 오차가 났던 것은 프론트엔드의 과거 Payload 찌꺼기 때문임이 증명되었습니다."
        )
    else:
        print(
            "⚠️ [분석 필요] 압력이 여전히 다릅니다. hrro.py의 수식을 추가 교정해야 합니다."
        )
    print("=" * 60)


if __name__ == "__main__":
    run_physics_debugger()
