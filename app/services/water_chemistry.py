# app/services/water_chemistry.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Dict
import math

# ---------------------------------------------------------
# 1. 물리/화학 상수 (Molecular Weights, g/mol)
# ---------------------------------------------------------
# 엑셀 '유입원수성상' 시트의 모든 이온 데이터 커버
MW_H   = 1.008
MW_C   = 12.011
MW_N   = 14.007
MW_O   = 15.999
MW_NA  = 22.990  # Sodium
MW_MG  = 24.305  # Magnesium
MW_AL  = 26.982  # Aluminum
MW_SI  = 28.085  # Silicon
MW_P   = 30.974  # Phosphorus
MW_S   = 32.065  # Sulfur
MW_CL  = 35.453  # Chloride
MW_K   = 39.098  # Potassium
MW_CA  = 40.078  # Calcium
MW_MN  = 54.938  # Manganese
MW_FE  = 55.845  # Iron
MW_F   = 18.998  # Fluoride
MW_B   = 10.811  # Boron
MW_SR  = 87.62   # Strontium
MW_BA  = 137.327 # Barium
MW_BR  = 79.904  # Bromide

# 화합물 분자량
MW_CACO3 = 100.09
MW_SO4   = MW_S + 4 * MW_O        # 96.06
MW_HCO3  = MW_H + MW_C + 3 * MW_O # 61.017
MW_NO3   = MW_N + 3 * MW_O        # 62.005
MW_CO3   = MW_C + 3 * MW_O        # 60.01
MW_PO4   = MW_P + 4 * MW_O        # 94.97
MW_NH4   = MW_N + 4 * MW_H        # 18.04
MW_SIO2  = MW_SI + 2 * MW_O       # 60.08

# [정밀 삼투 계수 - Osmotic Coefficients (Phi)]
# WAVE급 정밀도를 위해 전하량과 이온 크기에 따른 활동도 차이를 반영합니다.
# 단순 몰농도 합산 방식보다 훨씬 정확한 삼투압(Osmotic Pressure)을 제공합니다.
PHI_NA   = 0.93
PHI_K    = 0.93
PHI_CA   = 0.85 # 2가 이온은 1보다 작음
PHI_MG   = 0.85
PHI_NH4  = 0.90
PHI_SR   = 0.85
PHI_BA   = 0.85
PHI_FE   = 0.80
PHI_MN   = 0.80

PHI_CL   = 0.93
PHI_SO4  = 0.65 # 중요: 황산염은 삼투압 기여도가 낮음
PHI_HCO3 = 0.93
PHI_NO3  = 0.90
PHI_F    = 0.90
PHI_CO3  = 0.65
PHI_PO4  = 0.60 
PHI_BR   = 0.93

PHI_NEUTRAL = 1.0 # 중성 물질

# 기체 상수 (L·bar / K·mol)
R_GAS_CONSTANT = 0.0831446

# 용해도적 상수 (25°C 근사 - 스케일링 예측용)
_KSP_CASO4 = (0.015 ** 2)      # CaSO4
_KSP_SRSO4 = (0.012 ** 2)      # SrSO4
_KSP_BASO4 = (1.0e-5 ** 2)     # BaSO4
_SIO2_SAT_MGL = 150.0          # Silica Saturation


# ---------------------------------------------------------
# 2. 데이터 구조 (ChemistryProfile)
# ---------------------------------------------------------

@dataclass
class ChemistryProfile:
    """
    한 지점(Feed / Loop / Brine)의 상세 수질 상태.
    엑셀의 '유입원수성상'에 있는 모든 이온을 담을 수 있습니다.
    """
    # [기본 물리 정보]
    tds_mgL: float
    temperature_C: float
    ph: float
    
    # [Cations - 양이온]
    na_mgL: Optional[float] = 0.0
    k_mgL: Optional[float] = 0.0
    ca_mgL: Optional[float] = 0.0
    mg_mgL: Optional[float] = 0.0
    nh4_mgL: Optional[float] = 0.0
    sr_mgL: Optional[float] = 0.0
    ba_mgL: Optional[float] = 0.0
    fe_mgL: Optional[float] = 0.0
    mn_mgL: Optional[float] = 0.0
    
    # [Anions - 음이온]
    cl_mgL: Optional[float] = 0.0
    so4_mgL: Optional[float] = 0.0
    hco3_mgL: Optional[float] = 0.0
    no3_mgL: Optional[float] = 0.0
    f_mgL: Optional[float] = 0.0
    br_mgL: Optional[float] = 0.0
    po4_mgL: Optional[float] = 0.0
    co3_mgL: Optional[float] = 0.0
    
    # [Neutrals - 중성]
    sio2_mgL: Optional[float] = 0.0
    b_mgL: Optional[float] = 0.0
    co2_mgL: Optional[float] = 0.0

    # [Legacy Support - 합계 지표]
    alkalinity_mgL_as_CaCO3: Optional[float] = None 
    calcium_hardness_mgL_as_CaCO3: Optional[float] = None


# ---------------------------------------------------------
# 3. 핵심 유틸리티 (삼투압 & 농축)
# ---------------------------------------------------------

def calculate_osmotic_pressure_bar(profile: ChemistryProfile) -> float:
    """
    [물리 엔진 핵심] 수정된 반트 호프(Van't Hoff) 식.
    각 이온별로 '삼투 계수(Phi)'를 곱해 유효 몰농도를 구하고 압력을 계산합니다.
    """
    T_K = profile.temperature_C + 273.15
    sum_osmolarity = 0.0  # (phi * C)의 합

    # Helper: (mg/L) / MW * phi
    def _add(val_mgL, mw, phi):
        if val_mgL and val_mgL > 0:
            molarity = (val_mgL / mw) / 1000.0 # mol/L
            return molarity * phi
        return 0.0

    # Cations
    sum_osmolarity += _add(profile.na_mgL, MW_NA, PHI_NA)
    sum_osmolarity += _add(profile.k_mgL, MW_K, PHI_K)
    sum_osmolarity += _add(profile.ca_mgL, MW_CA, PHI_CA)
    sum_osmolarity += _add(profile.mg_mgL, MW_MG, PHI_MG)
    sum_osmolarity += _add(profile.nh4_mgL, MW_NH4, PHI_NH4)
    sum_osmolarity += _add(profile.sr_mgL, MW_SR, PHI_SR)
    sum_osmolarity += _add(profile.ba_mgL, MW_BA, PHI_BA)
    sum_osmolarity += _add(profile.fe_mgL, MW_FE, PHI_FE)
    sum_osmolarity += _add(profile.mn_mgL, MW_MN, PHI_MN)

    # Anions
    sum_osmolarity += _add(profile.cl_mgL, MW_CL, PHI_CL)
    sum_osmolarity += _add(profile.so4_mgL, MW_SO4, PHI_SO4) # 중요: 황산염
    sum_osmolarity += _add(profile.hco3_mgL, MW_HCO3, PHI_HCO3)
    sum_osmolarity += _add(profile.no3_mgL, MW_NO3, PHI_NO3)
    sum_osmolarity += _add(profile.f_mgL, MW_F, PHI_F)
    sum_osmolarity += _add(profile.co3_mgL, MW_CO3, PHI_CO3)
    sum_osmolarity += _add(profile.po4_mgL, MW_PO4, PHI_PO4)
    sum_osmolarity += _add(profile.br_mgL, MW_BR, PHI_BR)

    # Neutrals
    sum_osmolarity += _add(profile.sio2_mgL, MW_SIO2, PHI_NEUTRAL)
    sum_osmolarity += _add(profile.b_mgL, MW_B, PHI_NEUTRAL)
    sum_osmolarity += _add(profile.co2_mgL, MW_C + 2*MW_O, PHI_NEUTRAL)

    # [Fallback] 이온 정보가 없고 TDS만 있는 경우 -> NaCl로 가정
    if sum_osmolarity < 1e-9 and profile.tds_mgL > 0:
        molarity_nacl = (profile.tds_mgL / (MW_NA + MW_CL)) / 1000.0
        sum_osmolarity = molarity_nacl * 2.0 * PHI_NA 

    # Pi = C * R * T
    return sum_osmolarity * R_GAS_CONSTANT * T_K


def scale_profile_for_tds(base: ChemistryProfile, new_tds_mgL: float) -> ChemistryProfile:
    """
    HRRO 농축 시뮬레이션용 함수.
    Loop 내의 TDS가 증가할 때, 각 이온 농도도 동일한 비율로 증가시킵니다.
    """
    base_tds = max(float(base.tds_mgL), 1e-6)
    factor = float(new_tds_mgL) / base_tds

    def _scale(v: Optional[float]) -> Optional[float]:
        if v is None: return None
        return float(v) * factor
    
    return ChemistryProfile(
        tds_mgL=float(new_tds_mgL),
        temperature_C=base.temperature_C,
        ph=base.ph,
        
        # 모든 이온 스케일링
        na_mgL=_scale(base.na_mgL), k_mgL=_scale(base.k_mgL), ca_mgL=_scale(base.ca_mgL),
        mg_mgL=_scale(base.mg_mgL), nh4_mgL=_scale(base.nh4_mgL), sr_mgL=_scale(base.sr_mgL),
        ba_mgL=_scale(base.ba_mgL), fe_mgL=_scale(base.fe_mgL), mn_mgL=_scale(base.mn_mgL),
        
        cl_mgL=_scale(base.cl_mgL), so4_mgL=_scale(base.so4_mgL), hco3_mgL=_scale(base.hco3_mgL),
        no3_mgL=_scale(base.no3_mgL), f_mgL=_scale(base.f_mgL), br_mgL=_scale(base.br_mgL),
        po4_mgL=_scale(base.po4_mgL), co3_mgL=_scale(base.co3_mgL),
        
        sio2_mgL=_scale(base.sio2_mgL), b_mgL=_scale(base.b_mgL), co2_mgL=_scale(base.co2_mgL),

        alkalinity_mgL_as_CaCO3=_scale(base.alkalinity_mgL_as_CaCO3),
        calcium_hardness_mgL_as_CaCO3=_scale(base.calcium_hardness_mgL_as_CaCO3),
    )


# ---------------------------------------------------------
# 4. 스케일 지수 계산 (LSI, Sulfate, Silica)
# ---------------------------------------------------------

def _safe_log10(x: float) -> float:
    return math.log10(max(float(x), 1e-12))

def _calc_lsi_family(profile: ChemistryProfile) -> Dict[str, Optional[float]]:
    """LSI(Langelier Saturation Index) 계산."""
    tds = profile.tds_mgL
    T = profile.temperature_C
    pH = profile.ph
    
    # Ca Hardness & Alkalinity 확보
    CaH = profile.calcium_hardness_mgL_as_CaCO3
    if CaH is None and profile.ca_mgL is not None and profile.ca_mgL > 0:
        CaH = profile.ca_mgL * (MW_CACO3 / MW_CA)

    Alk = profile.alkalinity_mgL_as_CaCO3
    if Alk is None and profile.hco3_mgL is not None and profile.hco3_mgL > 0:
        Alk = profile.hco3_mgL * (50.0 / MW_HCO3)

    if any(v is None for v in (tds, T, pH, Alk, CaH)):
        return {"lsi": None, "rsi": None, "caco3_si": None}

    # APHA Method 
    A = (_safe_log10(tds) - 1.0) / 10.0
    B = -13.12 * _safe_log10(T + 273.0) + 34.55
    C = _safe_log10(CaH) - 0.4
    D = _safe_log10(Alk)

    pHs = (9.3 + A + B) - (C + D)
    lsi = pH - pHs
    rsi = 2.0 * pHs - pH

    return {"lsi": float(lsi), "rsi": float(rsi), "caco3_si": float(lsi)}

def _calc_sulfate_family(profile: ChemistryProfile) -> Dict[str, Optional[float]]:
    """황산염(Sulfate) 계열 스케일 지수 (SI)."""
    ca_mgL = profile.ca_mgL
    if (ca_mgL is None or ca_mgL <= 0) and profile.calcium_hardness_mgL_as_CaCO3:
         ca_mgL = profile.calcium_hardness_mgL_as_CaCO3 * (MW_CA / MW_CACO3)
    
    so4_mgL = profile.so4_mgL
    ba_mgL = profile.ba_mgL
    sr_mgL = profile.sr_mgL

    caso4_si = None
    if ca_mgL is not None and so4_mgL is not None:
        iap = ((ca_mgL/1000/MW_CA) * (so4_mgL/1000/MW_SO4))
        caso4_si = _safe_log10(iap / max(_KSP_CASO4, 1e-20))

    baso4_si = None
    if ba_mgL is not None and so4_mgL is not None:
        iap = ((ba_mgL/1000/MW_BA) * (so4_mgL/1000/MW_SO4))
        baso4_si = _safe_log10(iap / max(_KSP_BASO4, 1e-30))

    srso4_si = None
    if sr_mgL is not None and so4_mgL is not None:
        iap = ((sr_mgL/1000/MW_SR) * (so4_mgL/1000/MW_SO4))
        srso4_si = _safe_log10(iap / max(_KSP_SRSO4, 1e-20))

    return {
        "caso4_si": caso4_si,
        "baso4_si": baso4_si,
        "srso4_si": srso4_si,
    }

def _calc_silica_si(profile: ChemistryProfile) -> Optional[float]:
    """실리카(Silica) 스케일 지수."""
    if profile.sio2_mgL is None or profile.sio2_mgL <= 0:
        return None
    return _safe_log10(profile.sio2_mgL / _SIO2_SAT_MGL)


def calc_scaling_indices(profile: ChemistryProfile) -> Dict[str, Optional[float]]:
    out: Dict[str, Optional[float]] = {}
    out.update(_calc_lsi_family(profile))
    out.update(_calc_sulfate_family(profile))
    out["sio2_si"] = _calc_silica_si(profile)
    return out