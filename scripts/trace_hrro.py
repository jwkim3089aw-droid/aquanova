# scripts/trace_hrro.py
import sys
import os
import inspect

# 프로젝트 루트 경로 설정
sys.path.append(os.getcwd())

print("==================================================")
print("🕵️‍♂️ HRRO 코드 & 로직 정밀 추적기 (Trace)")
print("==================================================")


def run_trace():
    # --------------------------------------------------------
    # 1. 파일 시스템 검증: 파이썬이 보고 있는 코드를 직접 출력
    # --------------------------------------------------------
    print("\n📂 [Step 1] 현재 로딩된 'hrro.py' 소스코드 검사")

    try:
        # 강제 임포트 (순환 참조 방지 처리)
        from app.services.simulation.modules.hrro import HRROModule

        # 실제 파이썬이 로딩한 파일 경로 확인
        module_path = sys.modules["app.services.simulation.modules.hrro"].__file__
        print(f"   📍 파일 위치: {module_path}")

        # compute 메서드의 소스코드 가져오기
        source_lines = inspect.getsource(HRROModule.compute)

        # 'break' 문과 'stop_recovery' 관련 로직이 있는지 눈으로 확인
        print("   🔍 'compute' 함수 내부 검색 중...")

        has_break = False
        has_target_check = False

        lines = source_lines.split("\n")
        for i, line in enumerate(lines):
            # 핵심 키워드 검색
            if "stop_recovery_pct" in line or "target_recovery_pct" in line:
                if "config." in line and "=" in line:  # 할당 부분
                    print(f"      Line {i}: {line.strip()}")
                    has_target_check = True

            if "if current_recovery >= target_recovery_pct:" in line:
                print(f"      Line {i}: {line.strip()}  <-- ✅ 조건문 발견")
                if i + 1 < len(lines) and "break" in lines[i + 1]:
                    print(
                        f"      Line {i+1}: {lines[i+1].strip()}                  <-- ✅ break 발견"
                    )
                    has_break = True

        if has_break and has_target_check:
            print(
                "\n   ✅ [PASS] 소스코드에 '정지 로직(Break)'이 확실히 포함되어 있습니다."
            )
        else:
            print(
                "\n   ❌ [FAIL] 소스코드에 정지 로직이 없습니다! 파일이 저장이 안 됐거나 엉뚱한 파일입니다."
            )
            return  # 더 이상 테스트 의미 없음

    except Exception as e:
        print(f"   ❌ 읽기 실패: {e}")
        return

    # --------------------------------------------------------
    # 2. 로직 검증: 실제 계산 돌려보기
    # --------------------------------------------------------
    print("\n🤖 [Step 2] 시뮬레이션 강제 구동 (Target: 60%)")

    # 필요한 스키마만 로컬 임포트 (에러 방지)
    from app.schemas.simulation import StageConfig, FeedInput
    from app.schemas.common import ModuleType

    # 107%가 나왔던 그 조건 그대로 설정
    feed = FeedInput(flow_m3h=10.0, tds_mgL=35000.0, temperature_C=25.0, ph=8.0)
    config = StageConfig(
        module_type=ModuleType.HRRO,
        elements=6,
        pressure_bar=28.0,
        loop_volume_m3=2.0,
        recirc_flow_m3h=12.0,
        recovery_target_pct=60.0,
        stop_recovery_pct=60.0,  # 🎯 목표
        max_minutes=30.0,
    )

    hrro = HRROModule()
    result = hrro.compute(config, feed)

    last_rec = result.recovery_pct
    last_time = result.time_history[-1].time_min

    print(f"\n   📊 시뮬레이션 결과:")
    print(f"      - 최종 회수율: {last_rec}%")
    print(f"      - 종료 시간:   {last_time}분")

    if last_rec > 62.0:
        print(f"\n   ❌ [FAIL] 여전히 {last_rec}% 입니다. 로직이 작동하지 않습니다.")
    else:
        print(f"\n   ✅ [PASS] 60% 근처에서 정상 종료되었습니다.")
        print(
            "   👉 결론: 백엔드 코드는 정상입니다. 문제는 '웹에서 보내는 데이터'에 있습니다."
        )


if __name__ == "__main__":
    run_trace()
cd
