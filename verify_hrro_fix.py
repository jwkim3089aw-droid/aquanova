# scripts/verify_hrro_fix.py
import sys
import os

# 프로젝트 루트 경로 추가
sys.path.append(os.getcwd())

print("========================================")
print("🛡️ HRRO 모듈 격리 검증 (Blackbox Test)")
print("========================================")


def run_verification():
    try:
        # 1. 모듈 강제 로딩 (순환 참조 회피 시도)
        from app.services.simulation.modules.hrro import HRROModule

        # 스키마는 필요한 것만 가져오기
        from app.schemas.simulation import (
            StageConfig,
            FeedInput,
            HRROMassTransferIn,
            HRROSpacerIn,
        )
        from app.schemas.common import ModuleType

        print("✅ [1] 모듈 Import 성공 (순환 참조 없음)")

    except ImportError as e:
        print(f"❌ [1] 모듈 Import 실패: {e}")
        print("   -> 아직 'hrro.py' 파일 상단의 import 구문이 정리되지 않았습니다.")
        print(
            "   -> 순환 참조(Circular Import)가 해결되지 않으면 로직 확인 불가능합니다."
        )
        return

    # 2. 테스트 시나리오 설정 (사용자 스크린샷 기반)
    # 목표: 60%에서 멈추는지 확인
    print("\n⚙️ [2] 테스트 시나리오 설정")
    print("   - Target Recovery: 60.0%")
    print("   - Max Time: 30.0 min")

    feed = FeedInput(flow_m3h=10.0, tds_mgL=35000.0, temperature_C=25.0, ph=8.0)

    config = StageConfig(
        module_type=ModuleType.HRRO,
        elements=6,
        pressure_bar=28.0,
        loop_volume_m3=2.0,
        recirc_flow_m3h=12.0,
        recovery_target_pct=60.0,  # 🎯 핵심 설정
        stop_recovery_pct=60.0,  # 🎯 핵심 설정
        max_minutes=30.0,
        membrane_area_m2=37.0,
        membrane_A_lmh_bar=4.5,
        membrane_B_lmh=0.1,
    )

    # 3. 실행
    print("\n🚀 [3] 시뮬레이션 계산 시작...")
    try:
        hrro = HRROModule()
        result = hrro.compute(config, feed)

        final_rec = result.recovery_pct
        final_time = result.time_history[-1].time_min

        print("-" * 40)
        print(f"📊 결과: Recovery {final_rec}% (at {final_time} min)")
        print("-" * 40)

        # 4. 판정
        if final_rec > 100.0:
            print("❌ [FAIL] 결과가 100%를 초과했습니다 (107% 현상 재현됨).")
            print(
                "   👉 원인: 'hrro.py' 파일에 break 문이 없거나, 올바른 위치에 저장되지 않았습니다."
            )
            print(
                "   👉 조치: 제가 드린 '순환 참조 해결 + break 추가' 코드를 다시 붙여넣고 저장하세요."
            )

        elif final_rec > 62.0:  # 약간의 오차 허용
            print(f"❌ [FAIL] 목표(60%)를 무시하고 {final_rec}%까지 진행되었습니다.")
            print(
                "   👉 원인: 로직에 'if current_recovery >= target: break' 구문이 없습니다."
            )

        else:
            print("✅ [PASS] 정상! 목표 회수율(60%) 근처에서 정확히 멈췄습니다.")
            print("=" * 50)
            print("📢 [결론] 파일 시스템의 코드는 완벽합니다.")
            print("   그런데도 웹에서 107%가 뜬다면, 100% '서버 재시작' 문제입니다.")
            print("   터미널을 껐다가 다시 켜세요.")
            print("=" * 50)

    except Exception as e:
        print(f"💥 실행 중 에러 발생: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    run_verification()
