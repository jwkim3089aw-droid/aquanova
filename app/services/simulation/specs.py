# app/services/simulation/specs.py
import math
from typing import Dict, Any

from app.services.membranes import get_params_from_options
from app.services.transport import osmotic_pressure_bar
from app.services.simulation.utils import clamp

def calculate_membrane_params(
    flow_gpd: float,
    rej_pct: float,
    area_m2: float,
    test_pressure_bar: float = 15.5,  # 엑셀 기준
    test_temp_C: float = 25.0,
    test_tds_mgL: float = 2000.0,
    test_recovery_pct: float = 15.0
) -> Dict[str, float]:
    """
    제조사 카탈로그 스펙(GPD, Rejection)을 물리 모델의 A, B 계수로 변환
    """
    # 1. 단위 변환
    flow_m3d = flow_gpd * 0.00378541
    flow_lmh = (flow_m3d / 24.0) / max(area_m2, 0.1)
    
    # 2. 테스트 조건 삼투압 추정 (간이 계산 또는 transport 모듈 사용)
    cf_log_mean = (math.log(1.0 / (1.0 - test_recovery_pct/100.0)) / (test_recovery_pct/100.0))
    avg_tds = test_tds_mgL * cf_log_mean
    pi_avg = osmotic_pressure_bar(avg_tds, test_temp_C)
    
    # 3. Net Driving Pressure
    ndp = max(test_pressure_bar - pi_avg, 1.0)
    
    # 4. A값 (Water Permeability) [LMH/bar]
    A_val = flow_lmh / ndp
    
    # 5. B값 (Salt Permeability) [LMH]
    rej_frac = clamp(rej_pct / 100.0, 0.0, 0.9999)
    B_val = flow_lmh * (1.0 - rej_frac) / max(rej_frac, 0.01)
    
    return {
        "A": A_val,
        "B_lmh": B_val,
        "area": area_m2,
        "max_flux": 120.0 # Default cap
    }

def resolve_membrane_params(options: Dict[str, Any], stage_type: str = "RO") -> Dict[str, Any]:
    """
    options 딕셔너리에서 A, B 값을 찾거나, 없으면 스펙 기반으로 계산하여 반환
    """
    # 1. DB/Options에서 직접 로드 시도
    mem = get_params_from_options(options, stage_type=stage_type)
    
    # 2. A값이 없거나(0.0), 사용자가 엑셀 스펙 입력을 원할 경우
    if options.get("catalog_flow_gpd") and options.get("catalog_rej_pct"):
        calc_params = calculate_membrane_params(
            flow_gpd=float(options["catalog_flow_gpd"]),
            rej_pct=float(options["catalog_rej_pct"]),
            area_m2=float(options.get("catalog_area_m2", mem["area"])),
            test_pressure_bar=float(options.get("test_pressure_bar", 15.5)),
            test_temp_C=float(options.get("test_temp_C", 25.0)),
        )
        mem.update(calc_params)
    
    return mem