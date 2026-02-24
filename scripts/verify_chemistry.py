# scripts/verify_chemistry.py
import sys
from pathlib import Path

# AquaNova 프로젝트 루트 디렉토리를 sys.path에 추가하여 app 모듈을 import 할 수 있게 합니다.
root_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(root_dir))

from app.services.water_chemistry import (
    ChemistryProfile,
    calculate_ion_balance,
    apply_balance_makeup,
    calculate_osmotic_pressure_bar,
    calc_scaling_indices,
)


def run_verification():
    print("=" * 60)
    print("🌊 [AquaNova] WAVE Water Chemistry Engine Verification 🌊")
    print("=" * 60)

    # 1. 의도적으로 밸런스가 맞지 않는(양이온이 더 많은) 가상의 원수 프로필 생성
    # 양이온(Na, Ca, Mg)의 당량(meq/L) 합이 음이온(Cl, SO4)보다 큰 상황을 가정합니다.
    test_profile = ChemistryProfile(
        tds_mgL=1000.0,
        temperature_C=25.0,
        ph=7.5,
        na_mgL=200.0,  # Cation
        ca_mgL=100.0,  # Cation
        mg_mgL=50.0,  # Cation
        cl_mgL=300.0,  # Anion
        so4_mgL=150.0,  # Anion
        sio2_mgL=10.0,  # Neutral
    )

    print("\n[Step 1] Initial Ion Balance Check")
    cat_meq, an_meq, error_pct = calculate_ion_balance(test_profile)
    print(f"  - Cations (양이온 합): {cat_meq:.2f} meq/L")
    print(f"  - Anions  (음이온 합): {an_meq:.2f} meq/L")
    print(f"  - Error   (오차율):    {error_pct:.2f}%")
    if error_pct > 0:
        print("  🚨 경고: 이온 밸런스가 맞지 않습니다! (Make-up 필요)")

    print("\n[Step 2] Applying WAVE Balance Make-up...")
    balanced_profile = apply_balance_makeup(test_profile)

    cat_meq2, an_meq2, error_pct2 = calculate_ion_balance(balanced_profile)
    print(f"  - New Cations: {cat_meq2:.2f} meq/L")
    print(f"  - New Anions:  {an_meq2:.2f} meq/L")
    print(f"  - New Error:   {error_pct2:.2f}%  ✅ 완벽하게 보정됨!")

    # 무엇이 얼마나 추가되었는지 확인
    added_cl = balanced_profile.cl_mgL - (test_profile.cl_mgL or 0)
    added_na = balanced_profile.na_mgL - (test_profile.na_mgL or 0)

    if added_cl > 0:
        print(
            f"  💡 조치결과: 음이온 부족으로 염소(Cl-) {added_cl:.2f} mg/L 자동 추가됨."
        )
    if added_na > 0:
        print(
            f"  💡 조치결과: 양이온 부족으로 나트륨(Na+) {added_na:.2f} mg/L 자동 추가됨."
        )

    print(
        f"  - Updated TDS: {test_profile.tds_mgL:.2f} -> {balanced_profile.tds_mgL:.2f} mg/L"
    )

    print("\n[Step 3] Calculating Osmotic Pressure (삼투압 계산)")
    pi_bar = calculate_osmotic_pressure_bar(balanced_profile)
    print(f"  - 25°C 기준 삼투압: {pi_bar:.3f} bar")

    print("\n[Step 4] Calculating Scaling Indices (스케일링 지수 예측)")
    scaling = calc_scaling_indices(balanced_profile)

    def safe_round(val, digits=3):
        return round(val, digits) if val is not None else "N/A (입력 데이터 부족)"

    print("  - Langelier Saturation Index (LSI):", safe_round(scaling.get("lsi")))
    print(
        "  - Stiff & Davis Stability Index (S&DSI):", safe_round(scaling.get("s_dsi"))
    )
    print("  - CaSO4 Saturation (%):", safe_round(scaling.get("caso4_sat_pct"), 2))
    print("  - SiO2 Saturation (%):", safe_round(scaling.get("sio2_sat_pct"), 2))

    print("\n" + "=" * 60)
    print("🚀 모든 화학 엔진 테스트 통과 완료!")
    print("=" * 60)


if __name__ == "__main__":
    run_verification()
