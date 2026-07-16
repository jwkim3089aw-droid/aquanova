# app/services/chemistry/models.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Dict, Any

# ---------------------------------------------------------
# 1. 물리/화학 상수 (Molecular Weights & Valences)
# ---------------------------------------------------------
MW_H, MW_C, MW_N, MW_O = 1.008, 12.011, 14.007, 15.999
MW_NA, MW_MG, MW_AL, MW_SI = 22.990, 24.305, 26.982, 28.085
MW_P, MW_S, MW_CL, MW_K = 30.974, 32.065, 35.453, 39.098
MW_CA, MW_MN, MW_FE, MW_F = 40.078, 54.938, 55.845, 18.998
MW_B, MW_SR, MW_BA, MW_BR = 10.811, 87.62, 137.327, 79.904

MW_CACO3 = 100.0869
MW_SO4 = MW_S + 4 * MW_O
MW_HCO3 = MW_H + MW_C + 3 * MW_O
MW_NO3 = MW_N + 3 * MW_O
MW_CO3 = MW_C + 3 * MW_O
MW_PO4 = MW_P + 4 * MW_O
MW_NH4 = MW_N + 4 * MW_H
MW_SIO2 = MW_SI + 2 * MW_O

# 원자가 (Valences)
VAL_NA, VAL_K, VAL_NH4 = 1, 1, 1
VAL_CA, VAL_MG, VAL_SR, VAL_BA, VAL_FE, VAL_MN = 2, 2, 2, 2, 2, 2
VAL_AL = 3
VAL_CL, VAL_F, VAL_BR, VAL_HCO3, VAL_NO3 = 1, 1, 1, 1, 1
VAL_SO4, VAL_CO3 = 2, 2
VAL_PO4 = 3

# 삼투 계수 (Osmotic Coefficients)
PHI_NA, PHI_K, PHI_CL, PHI_HCO3, PHI_BR = 0.93, 0.93, 0.93, 0.93, 0.93
PHI_NH4, PHI_NO3, PHI_F = 0.90, 0.90, 0.90
PHI_CA, PHI_MG, PHI_SR, PHI_BA = 0.85, 0.85, 0.85, 0.85
PHI_FE, PHI_MN = 0.80, 0.80
PHI_SO4, PHI_CO3 = 0.65, 0.65
PHI_PO4 = 0.60
PHI_NEUTRAL = 1.0

R_GAS_CONSTANT = 0.0831446  # L·bar / K·mol

# 열역학 용해도적 상수 (Thermodynamic Ksp at 25°C)
_KSP_CASO4 = 2.45e-5
_KSP_SRSO4 = 3.20e-7
_KSP_BASO4 = 1.08e-10
_KSP_CAF2 = 3.90e-11


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

    alkalinity_mgL_as_CaCO3: Optional[float] = None
    calcium_hardness_mgL_as_CaCO3: Optional[float] = None

    @classmethod
    def from_feed(cls, feed: Any) -> ChemistryProfile:

        def _f(v: Any, default: float = 0.0) -> float:
            try:
                return float(v) if v is not None else float(default)
            except Exception:
                return float(default)

        chem_data = getattr(feed, "chemistry", {}) or {}
        if not isinstance(chem_data, dict):
            if hasattr(chem_data, "model_dump"):
                chem_data = chem_data.model_dump()
            elif hasattr(chem_data, "dict"):
                chem_data = chem_data.dict()
            else:
                chem_data = {}

        # feed.ions 객체 혹은 딕셔너리 안전 통합 인양 및 소문자 정규화
        ions_data = getattr(feed, "ions", None)
        if i_data := ions_data:
            if hasattr(i_data, "model_dump"):
                raw_dict = i_data.model_dump()
            elif isinstance(i_data, dict):
                raw_dict = i_data
            else:
                raw_dict = vars(i_data)

            for ik, iv in raw_dict.items():
                chem_data[str(ik).lower()] = iv

        tds = _f(getattr(feed, "tds_mgL", None), 0.0)
        temp = _f(getattr(feed, "temperature_C", None), 25.0)

        ph_design = _f(getattr(feed, "ph", None), 7.0)
        ph_25C = ph_design + 0.0125 * (temp - 25.0)

        na_val = chem_data.get("na") or (tds * (22.99 / 58.44) if not chem_data else 0)
        cl_val = chem_data.get("cl") or (tds * (35.45 / 58.44) if not chem_data else 0)

        return cls(
            tds_mgL=tds,
            temperature_C=temp,
            ph=ph_25C,
            na_mgL=float(na_val),
            cl_mgL=float(cl_val),
            k_mgL=_f(chem_data.get("k"), 0),
            ca_mgL=_f(chem_data.get("ca"), 0),
            mg_mgL=_f(chem_data.get("mg"), 0),
            nh4_mgL=_f(chem_data.get("nh4"), 0),
            sr_mgL=_f(chem_data.get("sr"), 0),
            ba_mgL=_f(chem_data.get("ba"), 0),
            fe_mgL=_f(chem_data.get("fe"), 0),
            mn_mgL=_f(chem_data.get("mn"), 0),
            al_mgL=_f(chem_data.get("al"), 0),
            so4_mgL=_f(chem_data.get("so4"), 0),
            hco3_mgL=_f(chem_data.get("hco3"), 0),
            no3_mgL=_f(chem_data.get("no3"), 0),
            f_mgL=_f(chem_data.get("f"), 0),
            br_mgL=_f(chem_data.get("br"), 0),
            po4_mgL=_f(chem_data.get("po4"), 0),
            co3_mgL=_f(chem_data.get("co3"), 0),
            sio2_mgL=_f(chem_data.get("sio2"), 0),
            b_mgL=_f(chem_data.get("b"), 0),
            co2_mgL=_f(chem_data.get("co2"), 0),
        )

    def to_dict(self) -> Dict[str, float]:
        d = {}
        for k, v in vars(self).items():
            if k.endswith("_mgL") and k != "tds_mgL" and v is not None:
                d[k.replace("_mgL", "")] = float(v)
        return d
