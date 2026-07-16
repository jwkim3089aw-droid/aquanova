# app/services/simulation/modules/hrro/helpers.py
from typing import Any, Dict, Optional, Tuple
from app.data.membranes import MEMBRANES
from app.schemas.simulation import FeedInput
from app.services.chemistry import (
    ChemistryProfile,
    calculate_osmotic_pressure_bar,
    get_water_density_kg_m3,
    get_water_viscosity_pa_s,
)

PA_TO_BAR = 1.0 / 1e5
LMH_TO_MPS = 1e-3 / 3600.0


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(float(x), hi))


def _f(v: Any, default: float) -> float:
    try:
        return float(default) if v is None else float(v)
    except:
        return float(default)


def _i(v: Any, default: int) -> int:
    try:
        return int(default) if v is None else int(v)
    except:
        return int(default)


def _normalize_model_key(value: Any) -> str:
    import re

    return re.sub(r"[^a-z0-9]", "", str(value or "").lower())


def _get_membrane_rejections(model_name: str) -> Tuple[float, Dict[str, float]]:
    name_key = _normalize_model_key(model_name)
    bulk_rej = 99.5
    ion_rej: Dict[str, float] = {}

    exact = None
    fuzzy = []
    for membrane in MEMBRANES:
        keys = {
            _normalize_model_key(membrane.get("id")),
            _normalize_model_key(membrane.get("name")),
        }
        for alias in membrane.get("aliases", []) or []:
            keys.add(_normalize_model_key(alias))
        keys.discard("")
        if name_key in keys:
            exact = membrane
            break
        if any(min(len(name_key), len(key)) >= 8 and (name_key in key or key in name_key) for key in keys):
            fuzzy.append(membrane)

    matched = exact or (fuzzy[0] if len(fuzzy) == 1 else None)
    if matched:
        bulk_rej = float(matched.get("salt_rejection_pct", 99.5))
        ion_rej = dict(matched.get("ion_rejections", {}) or {})

    # Legacy fallback only for SOAR 5000i when no catalog profile is available.
    if not ion_rej and "soar5000" in name_key:
        ion_rej = {
            "na": 0.992, "k": 0.990, "cl": 0.994, "f": 0.990,
            "no3": 0.985, "hco3": 0.995, "ca": 0.9995, "mg": 0.9995,
            "so4": 0.9998, "ba": 0.999, "sr": 0.999, "sio2": 0.997,
            "b": 0.850,
        }

    # Normalize once; callers should use lower-case canonical ion keys.
    normalized = {str(key).lower(): float(value) for key, value in ion_rej.items()}
    return bulk_rej, normalized


def _dict_to_profile(ions: dict, temp: float, ph: float) -> ChemistryProfile:
    return ChemistryProfile(
        tds_mgL=sum(ions.values()),
        temperature_C=temp,
        ph=ph,
        na_mgL=ions.get("na", 0.0),
        cl_mgL=ions.get("cl", 0.0),
        k_mgL=ions.get("k", 0.0),
        ca_mgL=ions.get("ca", 0.0),
        mg_mgL=ions.get("mg", 0.0),
        so4_mgL=ions.get("so4", 0.0),
        hco3_mgL=ions.get("hco3", 0.0),
        sr_mgL=ions.get("sr", 0.0),
        ba_mgL=ions.get("ba", 0.0),
        f_mgL=ions.get("f", 0.0),
        sio2_mgL=ions.get("sio2", 0.0),
        no3_mgL=ions.get("no3", 0.0),
    )


def _apply_charge_balance(ions: dict) -> dict:
    valences = {
        "na": (1, 22.99),
        "k": (1, 39.10),
        "ca": (2, 40.08),
        "mg": (2, 24.31),
        "sr": (2, 87.62),
        "ba": (2, 137.33),
        "cl": (-1, 35.45),
        "so4": (-2, 96.06),
        "hco3": (-1, 61.02),
        "no3": (-1, 62.00),
        "f": (-1, 19.00),
    }
    cat_meq, an_meq = 0.0, 0.0
    for k, v in ions.items():
        if k in valences and v > 0:
            val, mw = valences[k]
            meq = (v / mw) * abs(val)
            if val > 0:
                cat_meq += meq
            else:
                an_meq += meq

    diff = cat_meq - an_meq
    b_ions = ions.copy()
    if diff > 1e-4:
        b_ions["cl"] = b_ions.get("cl", 0.0) + (diff * 35.45)
    elif diff < -1e-4:
        b_ions["na"] = b_ions.get("na", 0.0) + (abs(diff) * 22.99)
    return b_ions


def _extract_ions_from_feed(feed: FeedInput) -> Dict[str, float]:
    ions = {}
    if hasattr(feed, "chemistry") and feed.chemistry:
        d = (
            feed.chemistry.model_dump()
            if hasattr(feed.chemistry, "model_dump")
            else (
                feed.chemistry.dict()
                if hasattr(feed.chemistry, "dict")
                else feed.chemistry
            )
        )
        if isinstance(d, dict):
            ions.update(d)
    if hasattr(feed, "ions") and feed.ions:
        d = (
            feed.ions.model_dump()
            if hasattr(feed.ions, "model_dump")
            else (feed.ions.dict() if hasattr(feed.ions, "dict") else feed.ions)
        )
        if isinstance(d, dict):
            ions.update(d)

    normalized = {}
    for k, v in ions.items():
        if v is None:
            continue
        k_low = str(k).lower().replace("_mgl", "").replace("_mg/l", "").strip()
        if k_low in ["tds", "temperature_c", "ph"]:
            continue
        try:
            val = float(v)
            if val > 0:
                normalized[k_low] = val
        except:
            pass
    return normalized


def _calc_water_properties(profile: ChemistryProfile) -> Tuple[float, float, float]:
    rho = get_water_density_kg_m3(profile.temperature_C, profile.tds_mgL)
    mu = get_water_viscosity_pa_s(profile.temperature_C, profile.tds_mgL)
    pi = calculate_osmotic_pressure_bar(profile)
    return rho, mu, pi


def _mass_transfer_coeff(
    rho: float, mu: float, vel: float, dh: float, diff: float
) -> float:
    Re = max((rho * vel * dh) / mu, 1.0)
    Sc = max(mu / (rho * diff), 1.0)
    Sh = 0.065 * (Re**0.875) * (Sc**0.25)
    return max((Sh * diff) / dh, 1e-8)


def _pressure_drop_spacer(
    rho: float, mu: float, vel: float, dh: float, length: float
) -> float:
    Re = max((rho * vel * dh) / mu, 1.0)
    f_sp = 2.00 * (Re**-0.3)
    dp_pa = f_sp * (length / dh) * (rho * (vel**2) / 2.0)
    return min(max(0.0, dp_pa * PA_TO_BAR), 3.0)
