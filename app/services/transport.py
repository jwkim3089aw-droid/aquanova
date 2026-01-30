# app/services/transport.py
from __future__ import annotations
import math

# 상수
R_BAR_L_PER_MOL_K = 0.08314  # bar·L/(mol·K)                                    # [UNCHANGED]
IONIC_FACTOR = 2.0           # NaCl 반트호프 계수 i≈2                             # [UNCHANGED]
MW_NACL = 58.44              # g/mol                                             # [UNCHANGED]

# ---- 단위 변환 ----
def lmh_to_m_per_s(lmh: float) -> float:
    # 1 LMH = 1e-3 m3/(m2·h) = (1e-3/3600) m/s
    return lmh * (1e-3 / 3600.0)                                                  # [UNCHANGED]

def m_per_s_to_lmh(ms: float) -> float:
    return ms * (3600.0 / 1e-3)                                                   # [UNCHANGED]

def b_mps_to_lmh(b_mps: float) -> float:
    # 1 m/s == 3,600,000 LMH
    return float(b_mps) * 3_600_000.0                                             # [ADDED]

# ---- 물성 근사 (25±10°C 범위 가정) ----
def viscosity_water_pa_s(T_C: float) -> float:
    # Andrade 근사: μ[Pa·s]
    T_K = T_C + 273.15
    A, B, C = 2.414e-5, 247.8, 140.0
    return A * 10 ** (B / (T_K - C))                                              # [UNCHANGED]

def density_water_kg_m3(T_C: float) -> float:
    # 단순 근사
    return 997.0 - 0.3 * (T_C - 25.0)                                             # [UNCHANGED]

def diffusivity_nacl_m2_s(T_C: float) -> float:
    # 25°C ~ 35°C 근사 (문헌값 1.5e-9 @25°C)
    return 1.5e-9 * (1.0 + 0.02 * (T_C - 25.0))                                   # [UNCHANGED]

# ---- 삼투압 (반트호프, TDS→몰농도 근사) ----
def tds_mgL_to_mol_per_L(tds_mgL: float) -> float:
    return (tds_mgL / 1000.0) / MW_NACL                                           # [UNCHANGED]

def osmotic_pressure_bar(tds_mgL: float, T_C: float) -> float:
    C = tds_mgL_to_mol_per_L(tds_mgL)
    T_K = T_C + 273.15
    return IONIC_FACTOR * R_BAR_L_PER_MOL_K * T_K * C                              # [UNCHANGED]

# ---- TCF (온도 보정) ----
def tcf_A_B(T_C: float, ref_C: float = 25.0) -> float:
    # Arrhenius형 간단 보정 (물 점도 기반 근사)
    mu_ref = viscosity_water_pa_s(ref_C)
    mu_now = viscosity_water_pa_s(T_C)
    return mu_ref / mu_now                                                         # [UNCHANGED]

# ---- Sherwood/질량전달계수 k ----
def reynolds(rho, v, Dh, mu) -> float:
    return rho * v * Dh / mu                                                       # [UNCHANGED]

def schmidt(mu, rho, D) -> float:
    return mu / (rho * D)                                                          # [UNCHANGED]

def sherwood(Re, Sc) -> float:
    # 복합 구간: laminar~turbulent 혼합 근사
    if Re < 2100:
        return 0.664 * math.sqrt(Re) * (Sc ** (1/3))
    return 0.023 * (Re ** 0.83) * (Sc ** (1/3))                                    # [UNCHANGED]

def mass_transfer_k_m_s(v: float, Dh: float, T_C: float, rho: float | None = None, mu: float | None = None) -> float:
    _rho = density_water_kg_m3(T_C) if rho is None else rho
    _mu  = viscosity_water_pa_s(T_C) if mu  is None else mu
    D    = diffusivity_nacl_m2_s(T_C)
    Re   = reynolds(_rho, v, Dh, _mu)
    Sc   = schmidt(_mu, _rho, D)
    Sh   = sherwood(Re, Sc)
    return Sh * D / Dh  # [m/s]                                                    # [UNCHANGED]

# ---- CP (film theory) ----
def cp_factor(Jw_lmh: float, k_m_s: float) -> float:
    # C_m = C_b * exp(Jw/k)
    Jw_ms = lmh_to_m_per_s(Jw_lmh)
    return math.exp(max(0.0, Jw_ms / max(k_m_s, 1e-8)))                            # [UNCHANGED]

# ---- ΔP (Darcy–Weisbach 근사) ----
def friction_factor(Re: float) -> float:
    if Re <= 0:
        return 0.0
    if Re < 2100:
        return 64.0 / Re
    # Blasius 근사
    return 0.3164 * (Re ** -0.25)                                                  # [UNCHANGED]

def delta_p_darcy_pa(rho: float, v: float, Dh: float, L: float, mu: float) -> float:
    Re = reynolds(rho, v, Dh, mu)
    f  = friction_factor(Re)
    return f * (L / Dh) * 0.5 * rho * v * v                                       # [UNCHANGED]

def pa_to_bar(pa: float) -> float:
    return pa / 1e5                                                                # [UNCHANGED]
