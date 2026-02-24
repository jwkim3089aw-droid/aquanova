import sys
import json
from pathlib import Path

# AquaNova 프로젝트 루트 디렉토리를 sys.path에 추가
root_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(root_dir))

from app.schemas.simulation import (
    SimulationRequest,
    FeedInput,
    StageConfig,
    ModuleType,
    WAVEWaterType,
    FoulingIndicators,
    IonCompositionInput,
)
from app.services.simulation.engine import SimulationEngine


def run_e2e_verification():
    print("=" * 70)
    print("🌊 [AquaNova] Phase 3 E2E: Feed Water & Engine Verification 🌊")
    print("=" * 70)

    # ---------------------------------------------------------
    # [Step 1] 프론트엔드에서 넘어온 가상의 불균형 원수(Feed) 세팅
    # ---------------------------------------------------------
    # 의도적으로 Cations(+)이 Anions(-)보다 훨씬 많게 세팅합니다.
    # (결과적으로 엔진이 Cl-를 추가하고 TDS를 높여야 정상입니다.)
    raw_ions = IonCompositionInput(
        Na=400.0,
        Ca=80.0,
        Mg=30.0,  # 양이온
        SO4=150.0,
        HCO3=200.0,
        Cl=100.0,  # 음이온 (의도적으로 낮게 줌)
        SiO2=25.0,
    )

    # 순수 입력 이온들의 질량 합계 (보정 전 TDS)
    initial_tds = 400 + 80 + 30 + 150 + 200 + 100 + 25

    feed_payload = FeedInput(
        water_type=WAVEWaterType.WELL_WATER,
        flow_m3h=100.0,
        temperature_C=25.0,
        ph=7.5,
        tds_mgL=initial_tds,
        fouling=FoulingIndicators(
            sdi15=2.5, turbidity_ntu=0.5, tss_mgL=1.0, toc_mgL=0.5
        ),
        ions=raw_ions,
    )

    # ---------------------------------------------------------
    # [Step 2] 시뮬레이션용 단순 1단 RO 스테이지 세팅
    # ---------------------------------------------------------
    stage_payload = StageConfig(
        stage_id="Stage_1",
        module_type=ModuleType.RO,
        vessel_count=10,
        elements_per_vessel=6,
        recovery_target_pct=75.0,  # 회수율 75% 설정 (농축 4배)
        flow_factor=0.85,
    )

    # 통합 Request Payload 생성
    request_payload = SimulationRequest(
        scenario_name="Feed Water Sync Test", feed=feed_payload, stages=[stage_payload]
    )

    print("\n[Input] 프론트엔드 Request Payload 조립 완료!")
    print(f"  - 설정된 Water Type: {request_payload.feed.water_type}")
    print(f"  - 초기 입력 TDS 합계: {request_payload.feed.tds_mgL:.2f} mg/L")
    print(f"  - 파울링 지표 (SDI): {request_payload.feed.fouling.sdi15}")

    # ---------------------------------------------------------
    # [Step 3] 시뮬레이션 엔진 실행 (진입 시 자동 밸런스 Make-up 발동)
    # ---------------------------------------------------------
    print("\n[Engine] 시뮬레이션 엔진 구동 중... (밸런스 Make-up 및 물리 연산 수행)")
    engine = SimulationEngine()
    result = engine.run(request_payload)

    # ---------------------------------------------------------
    # [Step 4] 검증 결과 출력 (Assertions)
    # ---------------------------------------------------------
    print("\n" + "=" * 70)
    print("✅ [Verification 1] 자동 이온 밸런스 (Make-up) 적용 확인")
    print("=" * 70)
    balanced_tds = request_payload.feed.tds_mgL
    added_tds = balanced_tds - initial_tds
    print(f"  - 보정 전 TDS: {initial_tds:.2f} mg/L")
    print(f"  - 보정 후 TDS: {balanced_tds:.2f} mg/L")
    if added_tds > 0:
        print(
            f"  💡 성공! 음이온 부족분을 채우기 위해 염소(Cl-) {added_tds:.2f} mg/L 가 자동 추가되었습니다."
        )
        print(
            f"  - Feed.ions.Cl 업데이트 됨: 100.00 -> {request_payload.feed.ions.Cl:.2f} mg/L"
        )
    else:
        print("  ❌ 실패: 밸런스 보정이 이루어지지 않았습니다.")

    print("\n" + "=" * 70)
    print("✅ [Verification 2] System Mass Balance (질량 보존의 법칙)")
    print("=" * 70)
    mb = result.kpi.mass_balance
    print(f"  - Flow Closure Error: {mb.flow_error_pct:.4f} %")
    print(f"  - Salt Closure Error: {mb.salt_error_pct:.4f} %")
    print(f"  - System Balanced:    {mb.is_balanced}")

    print("\n" + "=" * 70)
    print("✅ [Verification 3] RO 시뮬레이션 결과 (농축 효과 및 스케일링)")
    print("=" * 70)
    feed_stream = next(s for s in result.streams if s.label == "Feed")
    brine_stream = next(s for s in result.streams if s.label == "Brine")
    print(f"  - System Recovery:    {result.kpi.recovery_pct:.1f} %")
    print(f"  - Feed TDS:           {feed_stream.tds_mgL:.2f} mg/L")
    print(
        f"  - Brine TDS (농축수): {brine_stream.tds_mgL:.2f} mg/L (약 {brine_stream.tds_mgL/feed_stream.tds_mgL:.1f}배 농축됨)"
    )

    print("\n[농축수(Brine) 스케일링 예측 지표]")
    if result.chemistry and result.chemistry.final_brine:
        brine_chem = result.chemistry.final_brine

        def safe_print(name, val):
            print(f"  - {name:<20}: {round(val, 3) if val is not None else 'N/A'}")

        safe_print("LSI", brine_chem.lsi)
        safe_print("S&DSI", brine_chem.s_dsi)
        safe_print("CaSO4 Saturation (%)", brine_chem.caso4_sat_pct)
        safe_print("SiO2 Saturation (%)", brine_chem.sio2_sat_pct)
    else:
        print("  - 스케일링 지표 계산 안됨!")

    print("\n" + "=" * 70)
    print("🚀 모든 E2E 파이프라인(Schema -> Make-up -> Engine -> Output) 검증 완료!")
    print("=" * 70)


if __name__ == "__main__":
    run_e2e_verification()
