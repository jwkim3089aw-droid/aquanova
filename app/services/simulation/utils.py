# app/services/simulation/utils.py
from app.services.transport import viscosity_water_pa_s

# ============================================================
# 기본 상수
# ============================================================
R_BAR_L_PER_MOL_K = 0.08314
P_PERM_BAR = 0.0              # 투과측 배압 (가정)
DEFAULT_REF_TEMP_C = 25.0     # 표준 테스트 온도

def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))

def temp_correct_A(A_ref: float, temp_C: float, ref_C: float = 25.0) -> float:
    """온도보정: 점도 비율로 보정 (온도 상승 -> 점도 하락 -> 투과율 증가)"""
    mu = viscosity_water_pa_s(temp_C)
    mu_ref = viscosity_water_pa_s(ref_C)
    return A_ref * (mu_ref / max(mu, 1e-6))

def mps_to_lmh(J_mps: float) -> float:
    return (J_mps * 1000.0) * 3600.0

def lmh_to_mps(J_lmh: float) -> float:
    return (J_lmh / 1000.0) / 3600.0