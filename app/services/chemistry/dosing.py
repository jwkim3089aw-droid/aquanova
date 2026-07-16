# app/services/chemistry/dosing.py
from __future__ import annotations
import math
from typing import Dict, Any, Tuple

from .models import ChemistryProfile, MW_HCO3, MW_CO3

# ==========================================
# 1. 분자량 및 산해리 상수
# ==========================================
MW_HCL = 36.46
MW_H2SO4 = 98.08
MW_NAOH = 40.00
PK_A1 = 6.35
PK_A2 = 10.33


# 🚀 [붕소 패치] 붕산(Boric Acid)의 산해리 상수 (약 pKa 9.24 at 25C)
# 온도가 높을수록 붕소는 더 낮은 pH에서도 쉽게 이온화됨.
def get_boric_acid_pka(temp_c: float) -> float:
    t_k = temp_c + 273.15
    return (2273.4 / t_k) + 0.01756 * t_k - 3.385


# ==========================================
# 2. 안티스케일런트 주입량 계산용 계수
# ==========================================
DOSE_BASE_MGL = 2.0
DOSE_LSI_MULTIPLIER = 1.8
DOSE_CASO4_MULTIPLIER = 0.05
DOSE_SIO2_MULTIPLIER = 0.08
MAX_DOSE_MGL = 15.0


def _f(val: Any, default: float = 0.0) -> float:
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def _calc_alpha_fractions(ph: float) -> Tuple[float, float]:
    """pH 기반 탄산계 해리 분율(Alpha) 계산 (DRY 최적화)"""
    alpha1 = 1.0 / (1.0 + 10 ** (PK_A1 - ph) + 10 ** (ph - PK_A2))
    alpha2 = 1.0 / (1.0 + 10 ** (PK_A2 - ph) + 10 ** (PK_A2 + PK_A1 - 2 * ph))
    return alpha1, alpha2


# 🚀 [붕소 패치] pH와 온도에 따른 붕소 이온화율 (Borate Fraction) 계산
def calculate_borate_fraction(ph: float, temp_c: float) -> float:
    """
    주어진 pH와 온도에서, 음전하를 띠는 붕산염(Borate, B(OH)4-)의 비율을 반환합니다.
    이온화된 붕산염은 정전기적 반발력으로 인해 분리막에서 99% 이상 제거됩니다.
    """
    pka_b = get_boric_acid_pka(temp_c)
    # Henderson-Hasselbalch 방정식 응용
    borate_fraction = 1.0 / (1.0 + 10 ** (pka_b - ph))
    return borate_fraction


def calculate_ph_adjustment(
    profile: ChemistryProfile,
    target_ph: float,
    acid_type: str = "H2SO4",
    base_type: str = "NaOH",
) -> Dict[str, Any]:
    current_ph = _f(profile.ph, 7.0)
    if abs(current_ph - target_ph) < 0.01:
        return {"chemical": "None", "dose_mgL": 0.0, "target_ph": target_ph}

    hco3_eq = _f(profile.hco3_mgL, 0.0) / MW_HCO3 / 1000.0
    co3_eq = (_f(profile.co3_mgL, 0.0) / MW_CO3 / 1000.0) * 2.0

    H_init = 10 ** (-current_ph)
    OH_init = 10 ** (-(14.0 - current_ph))
    initial_alk_eq = hco3_eq + co3_eq + OH_init - H_init

    alpha1_init, alpha2_init = _calc_alpha_fractions(current_ph)

    carb_alk_init = initial_alk_eq - OH_init + H_init
    tic_molar = carb_alk_init / max((alpha1_init + 2.0 * alpha2_init), 1e-12)

    H_target = 10 ** (-target_ph)
    OH_target = 10 ** (-(14.0 - target_ph))

    alpha1_target, alpha2_target = _calc_alpha_fractions(target_ph)

    target_alk_eq = (
        tic_molar * (alpha1_target + 2.0 * alpha2_target) + OH_target - H_target
    )
    delta_alk_eq = target_alk_eq - initial_alk_eq

    result = {"target_ph": target_ph}

    if delta_alk_eq < -1e-11:
        eq_needed = abs(delta_alk_eq)
        if "HCL" in str(acid_type).upper():
            result.update(
                {
                    "chemical": "염산 (HCl, 100%)",
                    "dose_mgL": round(eq_needed * MW_HCL * 1000.0, 2),
                    "type": "Acid",
                }
            )
        else:
            result.update(
                {
                    "chemical": "황산 (H2SO4, 100%)",
                    "dose_mgL": round(eq_needed * (MW_H2SO4 / 2.0) * 1000.0, 2),
                    "type": "Acid",
                }
            )
    elif delta_alk_eq > 1e-11:
        result.update(
            {
                "chemical": "가성소다 (NaOH, 100%)",
                "dose_mgL": round(delta_alk_eq * MW_NAOH * 1000.0, 2),
                "type": "Base",
            }
        )
    else:
        result.update({"chemical": "없음", "dose_mgL": 0.0})

    return result


def calculate_antiscalant_dosing(scaling_indices: Dict[str, Any]) -> Dict[str, Any]:
    si = {str(k).lower(): v for k, v in scaling_indices.items()}

    lsi = _f(si.get("lsi")) or _f(si.get("caco3_si"))
    caso4 = _f(si.get("caso4_sat_pct")) or (_f(si.get("caso4_si")) * 100.0)
    sio2 = _f(si.get("sio2_sat_pct")) or (_f(si.get("sio2_si")) * 100.0)

    if lsi <= 0.2 and caso4 <= 100.0 and sio2 <= 100.0:
        return {"required": False, "dose_mgL": 0.0, "warnings": []}

    dose_mgL = DOSE_BASE_MGL
    if lsi > 0:
        dose_mgL += lsi * DOSE_LSI_MULTIPLIER
    if caso4 > 100:
        dose_mgL += (caso4 - 100) * DOSE_CASO4_MULTIPLIER
    if sio2 > 100:
        dose_mgL += (sio2 - 100) * DOSE_SIO2_MULTIPLIER

    warnings = []
    if lsi > 2.0:
        warnings.append("탄산칼슘(CaCO3) 스케일 위험이 높습니다. 투입량 증량 권장.")
    if caso4 > 150:
        warnings.append("황산염 스케일 위험이 감지되었습니다.")

    return {
        "required": True,
        "dose_mgL": round(min(dose_mgL, MAX_DOSE_MGL), 2),
        "warnings": warnings,
        "purpose": "스케일 억제",
        "chemical": "범용 스케일 방지제",
    }
