# app/services/water_chemistry.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Dict, Tuple
import math

# ---------------------------------------------------------
# 1. 물리/화학 상수 (Molecular Weights & Valences)
# ---------------------------------------------------------
# 엑셀 '유입원수성상' 시트 및 WAVE 이온 데이터 커버
MW_H = 1.008
MW_C = 12.011
MW_N = 14.007
MW_O = 15.999
MW_NA = 22.990  # Sodium
MW_MG = 24.305  # Magnesium
MW_AL = 26.982  # Aluminum
MW_SI = 28.085  # Silicon
MW_P = 30.974  # Phosphorus
MW_S = 32.065  # Sulfur
MW_CL = 35.453  # Chloride
MW_K = 39.098  # Potassium
MW_CA = 40.078  # Calcium
MW_MN = 54.938  # Manganese
MW_FE = 55.845  # Iron
MW_F = 18.998  # Fluoride
MW_B = 10.811  # Boron
MW_SR = 87.62  # Strontium
MW_BA = 137.327  # Barium
MW_BR = 79.904  # Bromide

# 화합물 분자량
MW_CACO3 = 100.09
MW_SO4 = MW_S + 4 * MW_O  # 96.06
MW_HCO3 = MW_H + MW_C + 3 * MW_O  # 61.017
MW_NO3 = MW_N + 3 * MW_O  # 62.005
MW_CO3 = MW_C + 3 * MW_O  # 60.01
MW_PO4 = MW_P + 4 * MW_O  # 94.97
MW_NH4 = MW_N + 4 * MW_H  # 18.04
MW_SIO2 = MW_SI + 2 * MW_O  # 60.08

# 🛑 [WAVE PATCH] Valences (원자가 - 전하량)
VAL_NA, VAL_K, VAL_NH4 = 1, 1, 1
VAL_CA, VAL_MG, VAL_SR, VAL_BA, VAL_FE, VAL_MN = 2, 2, 2, 2, 2, 2
VAL_AL = 3

VAL_CL, VAL_F, VAL_BR, VAL_HCO3, VAL_NO3 = 1, 1, 1, 1, 1
VAL_SO4, VAL_CO3 = 2, 2
VAL_PO4 = 3

# [정밀 삼투 계수 - Osmotic Coefficients (Phi)]
PHI_NA, PHI_K, PHI_CL, PHI_HCO3, PHI_BR = 0.93, 0.93, 0.93, 0.93, 0.93
PHI_NH4, PHI_NO3, PHI_F = 0.90, 0.90, 0.90
PHI_CA, PHI_MG, PHI_SR, PHI_BA = 0.85, 0.85, 0.85, 0.85
PHI_FE, PHI_MN = 0.80, 0.80
PHI_SO4, PHI_CO3 = 0.65, 0.65
PHI_PO4 = 0.60
PHI_NEUTRAL = 1.0

# 기체 상수 (L·bar / K·mol)
R_GAS_CONSTANT = 0.0831446

# [WAVE 패치] 용해도적 상수 (Ksp at 25°C 근사 - 스케일링 예측용)
_KSP_CASO4 = 2.25e-4
_KSP_SRSO4 = 1.44e-4
_KSP_BASO4 = 1.0e-10
_KSP_CAF2 = 3.9e-11
_SIO2_SAT_MGL = 150.0


# ---------------------------------------------------------
# 2. 데이터 구조 (ChemistryProfile)
# ---------------------------------------------------------
@dataclass
class ChemistryProfile:
    tds_mgL: float
    temperature_C: float
    ph: float

    # [Cations]
    na_mgL: Optional[float] = 0.0
    k_mgL: Optional[float] = 0.0
    ca_mgL: Optional[float] = 0.0
    mg_mgL: Optional[float] = 0.0
    nh4_mgL: Optional[float] = 0.0
    sr_mgL: Optional[float] = 0.0
    ba_mgL: Optional[float] = 0.0
    fe_mgL: Optional[float] = 0.0
    mn_mgL: Optional[float] = 0.0
    al_mgL: Optional[float] = 0.0

    # [Anions]
    cl_mgL: Optional[float] = 0.0
    so4_mgL: Optional[float] = 0.0
    hco3_mgL: Optional[float] = 0.0
    no3_mgL: Optional[float] = 0.0
    f_mgL: Optional[float] = 0.0
    br_mgL: Optional[float] = 0.0
    po4_mgL: Optional[float] = 0.0
    co3_mgL: Optional[float] = 0.0

    # [Neutrals]
    sio2_mgL: Optional[float] = 0.0
    b_mgL: Optional[float] = 0.0
    co2_mgL: Optional[float] = 0.0

    # [Legacy Support]
    alkalinity_mgL_as_CaCO3: Optional[float] = None
    calcium_hardness_mgL_as_CaCO3: Optional[float] = None


# ---------------------------------------------------------
# 3. 🛑 [WAVE PATCH] 이온 밸런스 측정 및 자동 보정 (Make-up)
# ---------------------------------------------------------
def _get_meq(mgL: Optional[float], mw: float, valence: int) -> float:
    if not mgL or mgL <= 0:
        return 0.0
    return (mgL / mw) * valence


def calculate_ion_balance(profile: ChemistryProfile) -> Tuple[float, float, float]:
    """양이온 합(meq/L), 음이온 합(meq/L), 그리고 오차율(%) 반환"""
    cations_meq = (
        _get_meq(profile.na_mgL, MW_NA, VAL_NA)
        + _get_meq(profile.k_mgL, MW_K, VAL_K)
        + _get_meq(profile.ca_mgL, MW_CA, VAL_CA)
        + _get_meq(profile.mg_mgL, MW_MG, VAL_MG)
        + _get_meq(profile.nh4_mgL, MW_NH4, VAL_NH4)
        + _get_meq(profile.sr_mgL, MW_SR, VAL_SR)
        + _get_meq(profile.ba_mgL, MW_BA, VAL_BA)
        + _get_meq(profile.fe_mgL, MW_FE, VAL_FE)
        + _get_meq(profile.mn_mgL, MW_MN, VAL_MN)
        + _get_meq(profile.al_mgL, MW_AL, VAL_AL)
    )

    anions_meq = (
        _get_meq(profile.cl_mgL, MW_CL, VAL_CL)
        + _get_meq(profile.so4_mgL, MW_SO4, VAL_SO4)
        + _get_meq(profile.hco3_mgL, MW_HCO3, VAL_HCO3)
        + _get_meq(profile.no3_mgL, MW_NO3, VAL_NO3)
        + _get_meq(profile.f_mgL, MW_F, VAL_F)
        + _get_meq(profile.br_mgL, MW_BR, VAL_BR)
        + _get_meq(profile.po4_mgL, MW_PO4, VAL_PO4)
        + _get_meq(profile.co3_mgL, MW_CO3, VAL_CO3)
    )

    total_meq = cations_meq + anions_meq
    error_pct = 0.0
    if total_meq > 0:
        error_pct = (abs(cations_meq - anions_meq) / total_meq) * 100.0

    return cations_meq, anions_meq, error_pct


def apply_balance_makeup(profile: ChemistryProfile) -> ChemistryProfile:
    """
    [WAVE 핵심 로직] 전하량 불균형 시 부족한 이온(Na+ 또는 Cl-)을 채워 넣습니다.
    """
    cations_meq, anions_meq, _ = calculate_ion_balance(profile)

    # 밸런스가 맞거나 입력값이 아예 없는 경우 그대로 리턴
    if abs(cations_meq - anions_meq) < 1e-4 or (cations_meq == 0 and anions_meq == 0):
        return profile

    new_profile = scale_profile_for_tds(profile, profile.tds_mgL)  # 깊은 복사 역할

    if cations_meq > anions_meq:
        # 양이온이 많다 -> 음이온(Cl-) 추가
        diff_meq = cations_meq - anions_meq
        added_cl_mgL = diff_meq * MW_CL / VAL_CL
        new_profile.cl_mgL = (new_profile.cl_mgL or 0.0) + added_cl_mgL
        new_profile.tds_mgL += added_cl_mgL
    else:
        # 음이온이 많다 -> 양이온(Na+) 추가
        diff_meq = anions_meq - cations_meq
        added_na_mgL = diff_meq * MW_NA / VAL_NA
        new_profile.na_mgL = (new_profile.na_mgL or 0.0) + added_na_mgL
        new_profile.tds_mgL += added_na_mgL

    return new_profile


# ---------------------------------------------------------
# 4. 핵심 유틸리티 (삼투압 & 농축)
# ---------------------------------------------------------
def calculate_osmotic_pressure_bar(profile: ChemistryProfile) -> float:
    T_K = profile.temperature_C + 273.15
    sum_osmolarity = 0.0

    def _add(val_mgL, mw, phi):
        if val_mgL and val_mgL > 0:
            molarity = (val_mgL / mw) / 1000.0
            return molarity * phi
        return 0.0

    sum_osmolarity += _add(profile.na_mgL, MW_NA, PHI_NA)
    sum_osmolarity += _add(profile.k_mgL, MW_K, PHI_K)
    sum_osmolarity += _add(profile.ca_mgL, MW_CA, PHI_CA)
    sum_osmolarity += _add(profile.mg_mgL, MW_MG, PHI_MG)
    sum_osmolarity += _add(profile.nh4_mgL, MW_NH4, PHI_NH4)
    sum_osmolarity += _add(profile.sr_mgL, MW_SR, PHI_SR)
    sum_osmolarity += _add(profile.ba_mgL, MW_BA, PHI_BA)
    sum_osmolarity += _add(profile.fe_mgL, MW_FE, PHI_FE)
    sum_osmolarity += _add(profile.mn_mgL, MW_MN, PHI_MN)

    sum_osmolarity += _add(profile.cl_mgL, MW_CL, PHI_CL)
    sum_osmolarity += _add(profile.so4_mgL, MW_SO4, PHI_SO4)
    sum_osmolarity += _add(profile.hco3_mgL, MW_HCO3, PHI_HCO3)
    sum_osmolarity += _add(profile.no3_mgL, MW_NO3, PHI_NO3)
    sum_osmolarity += _add(profile.f_mgL, MW_F, PHI_F)
    sum_osmolarity += _add(profile.co3_mgL, MW_CO3, PHI_CO3)
    sum_osmolarity += _add(profile.po4_mgL, MW_PO4, PHI_PO4)
    sum_osmolarity += _add(profile.br_mgL, MW_BR, PHI_BR)

    sum_osmolarity += _add(profile.sio2_mgL, MW_SIO2, PHI_NEUTRAL)
    sum_osmolarity += _add(profile.b_mgL, MW_B, PHI_NEUTRAL)
    sum_osmolarity += _add(profile.co2_mgL, MW_C + 2 * MW_O, PHI_NEUTRAL)

    if sum_osmolarity < 1e-9 and profile.tds_mgL > 0:
        molarity_nacl = (profile.tds_mgL / (MW_NA + MW_CL)) / 1000.0
        sum_osmolarity = molarity_nacl * 2.0 * PHI_NA

    return sum_osmolarity * R_GAS_CONSTANT * T_K


def scale_profile_for_tds(
    base: ChemistryProfile, new_tds_mgL: float
) -> ChemistryProfile:
    base_tds = max(float(base.tds_mgL), 1e-6)
    factor = float(new_tds_mgL) / base_tds

    def _scale(v: Optional[float]) -> Optional[float]:
        if v is None:
            return None
        return float(v) * factor

    return ChemistryProfile(
        tds_mgL=float(new_tds_mgL),
        temperature_C=base.temperature_C,
        ph=base.ph,
        na_mgL=_scale(base.na_mgL),
        k_mgL=_scale(base.k_mgL),
        ca_mgL=_scale(base.ca_mgL),
        mg_mgL=_scale(base.mg_mgL),
        nh4_mgL=_scale(base.nh4_mgL),
        sr_mgL=_scale(base.sr_mgL),
        ba_mgL=_scale(base.ba_mgL),
        fe_mgL=_scale(base.fe_mgL),
        mn_mgL=_scale(base.mn_mgL),
        al_mgL=_scale(base.al_mgL),
        cl_mgL=_scale(base.cl_mgL),
        so4_mgL=_scale(base.so4_mgL),
        hco3_mgL=_scale(base.hco3_mgL),
        no3_mgL=_scale(base.no3_mgL),
        f_mgL=_scale(base.f_mgL),
        br_mgL=_scale(base.br_mgL),
        po4_mgL=_scale(base.po4_mgL),
        co3_mgL=_scale(base.co3_mgL),
        sio2_mgL=_scale(base.sio2_mgL),
        b_mgL=_scale(base.b_mgL),
        co2_mgL=_scale(base.co2_mgL),
        alkalinity_mgL_as_CaCO3=_scale(base.alkalinity_mgL_as_CaCO3),
        calcium_hardness_mgL_as_CaCO3=_scale(base.calcium_hardness_mgL_as_CaCO3),
    )


# ---------------------------------------------------------
# 5. 스케일 지수 계산 (LSI, Sulfate, Silica, Fluoride)
# ---------------------------------------------------------
def _safe_log10(x: float) -> float:
    return math.log10(max(float(x), 1e-30))


def _calc_lsi_family(profile: ChemistryProfile) -> Dict[str, Optional[float]]:
    tds = profile.tds_mgL
    T = profile.temperature_C
    pH = profile.ph

    CaH = profile.calcium_hardness_mgL_as_CaCO3
    if CaH is None and profile.ca_mgL is not None and profile.ca_mgL > 0:
        CaH = profile.ca_mgL * (MW_CACO3 / MW_CA)

    Alk = profile.alkalinity_mgL_as_CaCO3
    if Alk is None and profile.hco3_mgL is not None and profile.hco3_mgL > 0:
        Alk = profile.hco3_mgL * (50.0 / MW_HCO3)

    if any(v is None for v in (tds, T, pH, Alk, CaH)):
        return {"lsi": None, "rsi": None, "caco3_si": None, "s_dsi": None}

    A = (_safe_log10(tds) - 1.0) / 10.0
    B = -13.12 * _safe_log10(T + 273.0) + 34.55
    C = _safe_log10(CaH) - 0.4
    D = _safe_log10(Alk)

    pHs = (9.3 + A + B) - (C + D)
    lsi = pH - pHs
    rsi = 2.0 * pHs - pH
    s_dsi = lsi - 0.2 if tds > 10000 else lsi

    return {
        "lsi": float(lsi),
        "rsi": float(rsi),
        "caco3_si": float(lsi),
        "s_dsi": float(s_dsi),
    }


def _calc_sulfate_family(profile: ChemistryProfile) -> Dict[str, Optional[float]]:
    ca_mgL = profile.ca_mgL
    if (ca_mgL is None or ca_mgL <= 0) and profile.calcium_hardness_mgL_as_CaCO3:
        ca_mgL = profile.calcium_hardness_mgL_as_CaCO3 * (MW_CA / MW_CACO3)

    so4_mgL = profile.so4_mgL
    ba_mgL = profile.ba_mgL
    sr_mgL = profile.sr_mgL

    caso4_si, baso4_si, srso4_si = None, None, None

    if ca_mgL is not None and so4_mgL is not None:
        iap = (ca_mgL / 1000 / MW_CA) * (so4_mgL / 1000 / MW_SO4)
        caso4_si = _safe_log10(iap / _KSP_CASO4)

    if ba_mgL is not None and so4_mgL is not None:
        iap = (ba_mgL / 1000 / MW_BA) * (so4_mgL / 1000 / MW_SO4)
        baso4_si = _safe_log10(iap / _KSP_BASO4)

    if sr_mgL is not None and so4_mgL is not None:
        iap = (sr_mgL / 1000 / MW_SR) * (so4_mgL / 1000 / MW_SO4)
        srso4_si = _safe_log10(iap / _KSP_SRSO4)

    return {
        "caso4_si": caso4_si,
        "baso4_si": baso4_si,
        "srso4_si": srso4_si,
    }


def _calc_fluoride_family(profile: ChemistryProfile) -> Dict[str, Optional[float]]:
    ca_mgL = profile.ca_mgL
    if (ca_mgL is None or ca_mgL <= 0) and profile.calcium_hardness_mgL_as_CaCO3:
        ca_mgL = profile.calcium_hardness_mgL_as_CaCO3 * (MW_CA / MW_CACO3)
    f_mgL = profile.f_mgL

    caf2_si = None
    if ca_mgL is not None and f_mgL is not None:
        iap = (ca_mgL / 1000 / MW_CA) * ((f_mgL / 1000 / MW_F) ** 2)
        caf2_si = _safe_log10(iap / _KSP_CAF2)

    return {"caf2_si": caf2_si}


def _calc_silica_si(profile: ChemistryProfile) -> Optional[float]:
    if profile.sio2_mgL is None or profile.sio2_mgL <= 0:
        return None
    return _safe_log10(profile.sio2_mgL / _SIO2_SAT_MGL)


def calc_scaling_indices(profile: ChemistryProfile) -> Dict[str, Optional[float]]:
    out: Dict[str, Optional[float]] = {}

    out.update(_calc_lsi_family(profile))
    sulfates = _calc_sulfate_family(profile)
    out.update(sulfates)
    out.update(_calc_fluoride_family(profile))

    sio2_si = _calc_silica_si(profile)
    out["sio2_si"] = sio2_si

    if sulfates.get("caso4_si") is not None:
        out["caso4_sat_pct"] = round((10 ** sulfates["caso4_si"]) * 100.0, 2)

    if sulfates.get("baso4_si") is not None:
        out["baso4_sat_pct"] = round((10 ** sulfates["baso4_si"]) * 100.0, 2)

    if sio2_si is not None:
        out["sio2_sat_pct"] = round((10**sio2_si) * 100.0, 2)

    return out
