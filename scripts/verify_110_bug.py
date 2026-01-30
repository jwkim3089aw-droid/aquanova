# scripts/verify_110_bug.py
import sys
import os
import inspect

# 프로젝트 루트 경로 설정
sys.path.append(os.getcwd())


def run_verification():
    print("==================================================")
    print("🕵️‍♂️ HRRO 110% 버그 정밀 검증기 (Non-invasive)")
    print("==================================================")

    # ----------------------------------------------------
    # 1. 파일 위치 및 소스코드 검사
    # ----------------------------------------------------
    try:
        from app.services.simulation.modules.hrro import HRROModule

        # 실제로 로딩된 파일 경로 확인
        module_path = sys.modules["app.services.simulation.modules.hrro"].__file__
        print(f"📂 로딩된 파일 경로:\n   {module_path}")

        # 소스코드 읽어오기
        source = inspect.getsource(HRROModule.compute)

        print("\n🔍 소스코드 정적 분석:")
        if "if current_recovery >= target_recovery_pct:" in source:
            print("   ✅ 조건문(if current_recovery >= target)이 존재합니다.")
        else:
            print("   ❌ 조건문이 코드에 없습니다! (저장이 안 됐거나 파일이 다름)")

        if "break" in source:
            print("   ✅ 정지 명령(break)이 존재합니다.")
        else:
            print("   ❌ 정지 명령(break)이 코드에 없습니다!")

    except Exception as e:
        print(f"❌ 모듈 로딩 실패: {e}")
        return

    # ----------------------------------------------------
    # 2. 블랙박스 시뮬레이션 (강제 60% 주입)
    # ----------------------------------------------------
    print("\n🤖 시뮬레이션 가동 (Target: 60.0% 강제 주입)...")

    # 필요한 스키마 로드
    from app.schemas.simulation import StageConfig, FeedInput
    from app.schemas.common import ModuleType

    # 110%가 나왔던 조건 재현
    feed = FeedInput(flow_m3h=10.0, tds_mgL=35000.0, temperature_C=25.0, ph=8.0)
    config = StageConfig(
        module_type=ModuleType.HRRO,
        elements=6,
        pressure_bar=28.0,
        loop_volume_m3=2.0,
        recirc_flow_m3h=12.0,
        # 👇 여기에 60을 강제로 넣어서 테스트
        recovery_target_pct=60.0,
        stop_recovery_pct=60.0,
        max_minutes=30.0,
    )

    try:
        hrro = HRROModule()
        result = hrro.compute(config, feed)

        final_rec = result.recovery_pct

        print("-" * 40)
        print(f"📊 결과 회수율: {final_rec}%")
        print("-" * 40)

        # ----------------------------------------------------
        # 3. 최종 판정
        # ----------------------------------------------------
        if final_rec > 100.0:
            print("🚨 [판정: 유죄] 백엔드 로직이 고장났습니다.")
            print("   이유: 60%를 입력받았는데도 무시하고 100%를 넘겼습니다.")
            print("   -> hrro.py 파일의 while 루프 로직을 다시 확인해야 합니다.")

        elif final_rec > 62.0:
            print("⚠️ [판정: 의심] 100%는 안 넘겼지만 목표(60%)를 무시했습니다.")
            print(f"   결과: {final_rec}% (목표: 60%)")
            print("   -> break 조건문의 위치가 잘못되었거나 변수명이 틀렸습니다.")

        else:
            print("✅ [판정: 무죄] 백엔드 코드는 완벽합니다.")
            print(f"   결과: {final_rec}% (목표: 60% 근처)")
            print("   👉 결론: 백엔드는 죄가 없습니다. 범인은 '프론트엔드'입니다.")
            print(
                "   웹 UI에서 [Run]을 누를 때 60이라는 숫자가 백엔드로 안 날아오고 있는 겁니다."
            )

    except Exception as e:
        print(f"💥 실행 중 에러: {e}")


if __name__ == "__main__":
    run_verification()
