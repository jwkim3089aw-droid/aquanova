import sys
import os
from pathlib import Path
import traceback
from unittest.mock import MagicMock

# -------------------------------------------------------------------------
# 1. 환경 설정 (프로젝트 루트 경로 추가)
# -------------------------------------------------------------------------
# 현재 파일 위치: .../code/scripts/test_hrro_debug.py
# 프로젝트 루트: .../code/
current_file = Path(__file__).resolve()
project_root = current_file.parent.parent

print(f"[*] Script Location: {current_file}")
print(f"[*] Project Root: {project_root}")

# sys.path에 프로젝트 루트 추가 (app 모듈을 찾기 위함)
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# -------------------------------------------------------------------------
# [Critical Fix] 순환 참조 방지용 Mocking
# -------------------------------------------------------------------------
sys.modules["app.services.tasks"] = MagicMock()
print("[*] Mocked 'app.services.tasks' to prevent circular imports.")

# -------------------------------------------------------------------------
# 2. 모듈 임포트 테스트 (Robust Import Strategy)
# -------------------------------------------------------------------------
print("\n[Step 1] Importing Modules...")
simulate_HRRO_cycle = None
HRROCycleResult = None

try:
    # Case A: solvers가 패키지(폴더)인 경우
    print("   [Attempt 1] Trying 'app.services.simulation.solvers.hrro'...")
    from app.services.simulation.solvers.hrro import simulate_HRRO_cycle
    from app.services.simulation.models import HRROCycleResult
    print("   [OK] Success via solvers.hrro")

except (ImportError, ModuleNotFoundError) as e1:
    print(f"   [WARN] Attempt 1 failed: {e1}")
    try:
        # Case B: solvers가 모듈(파일)인 경우, 그 안에 함수가 있는지 확인
        print("   [Attempt 2] Trying 'app.services.simulation.solvers' (as module)...")
        from app.services.simulation.solvers import simulate_HRRO_cycle
        from app.services.simulation.models import HRROCycleResult
        print("   [OK] Success via solvers module")
        
    except (ImportError, AttributeError) as e2:
        print(f"   [WARN] Attempt 2 failed: {e2}")
        try:
            # Case C: 폴더명이 단수형(solver)인 경우
            print("   [Attempt 3] Trying 'app.services.simulation.solver.hrro'...")
            from app.services.simulation.solver.hrro import simulate_HRRO_cycle
            from app.services.simulation.models import HRROCycleResult
            print("   [OK] Success via solver.hrro")
            
        except (ImportError, ModuleNotFoundError) as e3:
            print(f"   [FAIL] All import attempts failed.")
            print(f"   Last Error: {e3}")
            sys.exit(1)

# -------------------------------------------------------------------------
# 3. 테스트 데이터 정의 (UI에서 보내는 값과 유사하게 설정)
# -------------------------------------------------------------------------
print("\n[Step 2] Setting up Test Data...")

# 기본 테스트 조건 (일반적인 BWRO 조건)
test_inputs = {
    "C0_mgL": 2000.0,       # 초기 농도 2000ppm
    "V0_m3": 2.0,           # 루프 부피 2톤
    "T_C": 25.0,            # 온도 25도
    "elements": 6,          # 엘리먼트 6개
    "p_set_bar": 15.0,      # 운전 압력 15bar
    "recirc_flow_m3h": 12.0, # 순환 유량 12m3/h
    "bleed_m3h": 0.0,       # 블리드 없음 (완전 폐쇄)
    "makeup_tds_mgL": 2000.0,
    "timestep_s": 5,        # 5초 간격 계산
    "max_minutes": 30.0,    # 최대 30분 운전
    "stop_permeate_tds_mgL": 500.0, # 생산수질 500ppm 넘으면 정지
    "stop_recovery_pct": 60.0,      # 회수율 60% 도달 시 정지
    
    # 옵션 (막 파라미터 강제 주입)
    "options": {
        "hrro_membrane_type": "RO",
        # Generic BWRO 8040 Spec
        "A": 3.0,       # LMH/bar
        "B_lmh": 0.4,   # LMH
        "area": 37.0,   # m2
        "max_flux": 40.0
    }
}

print(f"   Inputs: {test_inputs}")

# -------------------------------------------------------------------------
# 4. 시뮬레이션 실행 및 추적
# -------------------------------------------------------------------------
print("\n[Step 3] Running Simulation...")

try:
    # 함수 직접 호출
    result = simulate_HRRO_cycle(**test_inputs)
    
    print("\n[Step 4] Validation Result")
    
    if result is None:
        print("   [FAIL] Result is None!")
    elif isinstance(result, HRROCycleResult) or type(result).__name__ == 'HRROCycleResult':
        print("   [SUCCESS] Received valid HRROCycleResult object.")
        print("-" * 40)
        print(f"   Process Time      : {result.minutes:.2f} min")
        print(f"   Recovery          : {getattr(result, 'recovery_pct', 0.0):.2f} %")
        print(f"   Total Permeate    : {result.Qp_total_m3:.4f} m3")
        print(f"   Avg Flux          : {result.avg_Jw_lmh:.2f} LMH")
        print(f"   Avg Permeate TDS  : {result.Cp_mix_mgL:.2f} mg/L")
        print(f"   Final Loop TDS    : {result.C_loop_final_mgL:.2f} mg/L")
        print("-" * 40)
        
        if result.Qp_total_m3 <= 0:
            print("   [WARNING] Total Permeate is 0. Simulation might have failed internally.")
        else:
            print("   [OK] Data looks reasonable.")
            
    else:
        print(f"   [FAIL] Unknown result type: {type(result)}")
        print(f"   Value: {result}")

except Exception as e:
    print("\n[FAIL] Simulation Crashed!")
    traceback.print_exc()