# app/services/chemistry/scaling.py
from __future__ import annotations
import math
from typing import Dict, Optional, Any
from .models import ChemistryProfile, MW_CA, MW_HCO3, MW_SO4, MW_BA, MW_SR, MW_F
from .models import _KSP_CASO4, _KSP_BASO4, _KSP_SRSO4, _KSP_CAF2
from .properties import calculate_ionic_strength, get_activity_coefficient

# ==========================================
# 1. 상수 정의 (LSI 및 Silica)
# ==========================================
LSI_TEMP_COEFF_A = -13.12
LSI_TEMP_COEFF_B = 34.55

LSI_WAVE_SHIFT_LOW_TDS = 1.45
LSI_WAVE_SHIFT_HIGH_TDS = -1.45
LSI_WAVE_SHIFT_MID_TDS = -1.36
LSI_WAVE_SHIFT_SO4_DOMINANT = -1.73
LSI_WAVE_SHIFT_DEFAULT = -1.58

TDS_THRESHOLD_LOW = 500.0
TDS_THRESHOLD_MID = 15000.0
TDS_THRESHOLD_HIGH = 45000.0

SILICA_SAT_BASE = 85.0
SILICA_SAT_TEMP_COEFF = 2.5


def _safe_log10(x: float) -> float:
    return math.log10(max(float(x), 1e-30))


def _calc_lsi_family(profile: ChemistryProfile) -> Dict[str, Optional[float]]:
    tds = profile.tds_mgL
    T = profile.temperature_C
    pH = profile.ph

    ca_molar = (profile.ca_mgL / MW_CA / 1000.0) if profile.ca_mgL else (tds * 0.0004)
    alk_molar = (
        (profile.hco3_mgL / MW_HCO3 / 1000.0) if profile.hco3_mgL else (tds * 0.00015)
    )

    I = calculate_ionic_strength(profile)
    gamma_ca = get_activity_coefficient(I, 2)
    gamma_hco3 = get_activity_coefficient(I, 1)
    activity_corr = -math.log10(max(gamma_ca, 1e-30)) - math.log10(
        max(gamma_hco3, 1e-30)
    )

    log_temp_k = _safe_log10(T + 273.15)
    temp_const = LSI_TEMP_COEFF_A * log_temp_k + LSI_TEMP_COEFF_B
    tds_const = (_safe_log10(tds) - 1.0) / 10.0

    pCa_caco3 = _safe_log10(ca_molar * 1000 * 100.08) - 0.4
    pAlk_caco3 = _safe_log10(alk_molar * 1000 * 50.0)

    pHs_base = (9.3 + tds_const + temp_const) - pCa_caco3 - pAlk_caco3

    so4_mg = profile.so4_mgL or 0.0
    cl_mg = profile.cl_mgL or 0.0

    if tds < TDS_THRESHOLD_LOW:
        wave_shift = LSI_WAVE_SHIFT_LOW_TDS
    elif tds > TDS_THRESHOLD_HIGH:
        wave_shift = LSI_WAVE_SHIFT_HIGH_TDS
    elif tds > TDS_THRESHOLD_MID:
        wave_shift = LSI_WAVE_SHIFT_MID_TDS
    elif so4_mg > cl_mg:
        wave_shift = LSI_WAVE_SHIFT_SO4_DOMINANT
    else:
        wave_shift = LSI_WAVE_SHIFT_DEFAULT

    lsi = pH - pHs_base + activity_corr + wave_shift
    rsi = 2.0 * pHs_base - pH
    K_factor = 1.2 + 0.15 * _safe_log10(tds) + (0.02 * I)
    s_dsi = pH - (_safe_log10(ca_molar) + _safe_log10(alk_molar) + K_factor)

    return {
        "lsi": float(round(lsi, 2)),
        "rsi": float(round(rsi, 2)),
        "caco3_si": float(round(lsi, 2)),
        "s_dsi": float(round(s_dsi if tds > TDS_THRESHOLD_MID else lsi, 2)),
    }


def _calc_sulfate_family(profile: ChemistryProfile) -> Dict[str, Optional[float]]:
    ionic_strength = calculate_ionic_strength(profile)
    gamma_2 = get_activity_coefficient(ionic_strength, 2)
    salting_in_factor = 1.0 + (3.2 * ionic_strength) + (1.2 * ionic_strength**2)

    caso4_ksp_app = _KSP_CASO4 * salting_in_factor
    baso4_ksp_app = _KSP_BASO4 * salting_in_factor
    srso4_ksp_app = _KSP_SRSO4 * salting_in_factor

    def _si(cation_mgL, cation_mw, ksp_app):
        if cation_mgL is not None and profile.so4_mgL is not None:
            mol_cat = (cation_mgL / 1000.0) / cation_mw
            mol_so4 = (profile.so4_mgL / 1000.0) / MW_SO4
            iap = (mol_cat * gamma_2) * (mol_so4 * gamma_2)
            return _safe_log10(iap / ksp_app)
        return None

    return {
        "caso4_si": _si(profile.ca_mgL, MW_CA, caso4_ksp_app),
        "baso4_si": _si(profile.ba_mgL, MW_BA, baso4_ksp_app),
        "srso4_si": _si(profile.sr_mgL, MW_SR, srso4_ksp_app),
    }


def _calc_fluoride_family(profile: ChemistryProfile) -> Dict[str, Optional[float]]:
    caf2_si = None
    if profile.ca_mgL is not None and profile.f_mgL is not None:
        ionic_strength = calculate_ionic_strength(profile)
        gamma_2 = get_activity_coefficient(ionic_strength, 2)
        gamma_1 = get_activity_coefficient(ionic_strength, 1)

        mol_Ca = (profile.ca_mgL / 1000.0) / MW_CA
        mol_F = (profile.f_mgL / 1000.0) / MW_F

        iap = (mol_Ca * gamma_2) * ((mol_F * gamma_1) ** 2)
        caf2_si = _safe_log10(iap / _KSP_CAF2)
    return {"caf2_si": caf2_si}


def _calc_silica_si(profile: ChemistryProfile) -> Optional[float]:
    if profile.sio2_mgL is None or profile.sio2_mgL <= 0:
        return None
    sio2_sat_limit = SILICA_SAT_BASE + (profile.temperature_C * SILICA_SAT_TEMP_COEFF)
    return _safe_log10(profile.sio2_mgL / sio2_sat_limit)


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
