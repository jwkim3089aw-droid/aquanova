# app/services/chemistry/properties.py
from __future__ import annotations
import math
from typing import Optional, Tuple
from .models import *


def _get_meq(mgL: Optional[float], mw: float, valence: int) -> float:
    if not mgL or mgL <= 0:
        return 0.0
    return (mgL / mw) * valence


def calculate_ion_balance(profile: ChemistryProfile) -> Tuple[float, float, float]:
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
    error_pct = (
        (abs(cations_meq - anions_meq) / total_meq * 100.0) if total_meq > 0 else 0.0
    )
    return cations_meq, anions_meq, error_pct


def apply_balance_makeup(profile: ChemistryProfile) -> ChemistryProfile:
    cations_meq, anions_meq, _ = calculate_ion_balance(profile)
    if abs(cations_meq - anions_meq) < 1e-4 or (cations_meq == 0 and anions_meq == 0):
        return profile

    new_profile = scale_profile_for_tds(profile, profile.tds_mgL)
    if cations_meq > anions_meq:
        added_cl_mgL = (cations_meq - anions_meq) * MW_CL / VAL_CL
        new_profile.cl_mgL = (new_profile.cl_mgL or 0.0) + added_cl_mgL
        new_profile.tds_mgL += added_cl_mgL
    else:
        added_na_mgL = (anions_meq - cations_meq) * MW_NA / VAL_NA
        new_profile.na_mgL = (new_profile.na_mgL or 0.0) + added_na_mgL
        new_profile.tds_mgL += added_na_mgL
    return new_profile


def get_water_density_kg_m3(temperature_C: float, tds_mgL: float) -> float:
    t = max(0.0, min(100.0, temperature_C))
    rho_pure = (
        999.842594
        + (6.793952e-2 * t)
        - (9.09529e-3 * t**2)
        + (1.001685e-4 * t**3)
        - (1.120083e-6 * t**4)
        + (6.536332e-9 * t**5)
    )
    salinity = tds_mgL / 1000.0
    d_rho = salinity * (
        0.824493
        - 4.0899e-3 * t
        + 7.6438e-5 * t**2
        - 8.2467e-7 * t**3
        + 5.3875e-9 * t**4
    )
    return rho_pure + d_rho


def get_water_viscosity_pa_s(temperature_C: float, tds_mgL: float) -> float:
    t = max(0.0, min(100.0, temperature_C))
    mu_pure = 2.414e-5 * 10 ** (247.8 / (t + 133.15))
    salinity = tds_mgL / 1000.0
    return mu_pure * (1.0 + 0.0015 * salinity + 0.00001 * salinity**2)


def calculate_osmotic_pressure_bar(profile: ChemistryProfile) -> float:
    T_K = profile.temperature_C + 273.15

    # 🚀 [물리 엔진 패치 1] 극한 고농도(해수 이상) Pitzer-유사 지수 함수 보정
    # 농도가 35000을 넘어가면 이온 간 상호작용이 폭발적으로 증가하는 현상을 모델링
    if profile.tds_mgL > 35000.0:
        r_constant = 0.08314
        molarity = (profile.tds_mgL / 1000.0) / 31.5
        # 1차 선형 비례를 넘어 지수적 증가 형태를 띄도록 phi 계수 상향
        phi_pitzer = 0.85 + 0.25 * math.pow((profile.tds_mgL - 30000) / 20000, 1.2)
        phi_pitzer = min(phi_pitzer, 1.45)  # 상한선 클램프
        return phi_pitzer * 2.0 * molarity * r_constant * T_K

    def _add(val_mgL, mw, phi_const):
        return ((val_mgL / mw) / 1000.0 * phi_const) if val_mgL and val_mgL > 0 else 0.0

    sum_osmolarity = (
        _add(profile.na_mgL, MW_NA, PHI_NA)
        + _add(profile.k_mgL, MW_K, PHI_K)
        + _add(profile.ca_mgL, MW_CA, PHI_CA)
        + _add(profile.mg_mgL, MW_MG, PHI_MG)
        + _add(profile.nh4_mgL, MW_NH4, PHI_NH4)
        + _add(profile.sr_mgL, MW_SR, PHI_SR)
        + _add(profile.ba_mgL, MW_BA, PHI_BA)
        + _add(profile.cl_mgL, MW_CL, PHI_CL)
        + _add(profile.so4_mgL, MW_SO4, PHI_SO4)
        + _add(profile.hco3_mgL, MW_HCO3, PHI_HCO3)
        + _add(profile.no3_mgL, MW_NO3, PHI_NO3)
        + _add(profile.f_mgL, MW_F, PHI_F)
        + _add(profile.br_mgL, MW_BR, PHI_BR)
    )

    thermo_correction = 1.0 + (0.015 * (profile.tds_mgL / 10000.0) ** 2)

    if sum_osmolarity < 1e-9 and profile.tds_mgL > 0:
        sum_osmolarity = ((profile.tds_mgL / (MW_NA + MW_CL)) / 1000.0) * 2.0 * PHI_NA

    return sum_osmolarity * R_GAS_CONSTANT * T_K * thermo_correction


def scale_profile_for_tds(
    base: ChemistryProfile, new_tds_mgL: float
) -> ChemistryProfile:
    factor = float(new_tds_mgL) / max(float(base.tds_mgL), 1e-6)

    def _scale(v: Optional[float]) -> Optional[float]:
        return None if v is None else float(v) * factor

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


def calculate_ionic_strength(profile: ChemistryProfile) -> float:
    def _term(mgL, mw, z):
        return (((mgL / mw) / 1000.0) * (z**2)) if mgL and mgL > 0 else 0.0

    sum_terms = (
        _term(profile.na_mgL, MW_NA, VAL_NA)
        + _term(profile.k_mgL, MW_K, VAL_K)
        + _term(profile.ca_mgL, MW_CA, VAL_CA)
        + _term(profile.mg_mgL, MW_MG, VAL_MG)
        + _term(profile.sr_mgL, MW_SR, VAL_SR)
        + _term(profile.ba_mgL, MW_BA, VAL_BA)
        + _term(profile.cl_mgL, MW_CL, VAL_CL)
        + _term(profile.so4_mgL, MW_SO4, VAL_SO4)
        + _term(profile.hco3_mgL, MW_HCO3, VAL_HCO3)
        + _term(profile.f_mgL, MW_F, VAL_F)
    )
    return (
        (profile.tds_mgL * 2.5e-5)
        if sum_terms < 1e-9 and profile.tds_mgL > 0
        else (0.5 * sum_terms)
    )


def get_activity_coefficient(ionic_strength: float, valence: int) -> float:
    if ionic_strength <= 1e-6 or valence == 0:
        return 1.0
    A = 0.509
    I = ionic_strength
    log_gamma = (
        -A * (valence**2) * ((math.sqrt(I) / (1.0 + 1.2 * math.sqrt(I))) - 0.2 * I)
    )
    return 10**log_gamma
