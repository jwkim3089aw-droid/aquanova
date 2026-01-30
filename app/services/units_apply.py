# app/services/units_apply.py
from __future__ import annotations

from copy import deepcopy
from typing import Any


def _to_engine(val: Any, cv: dict):
    """
    Convert a display-unit value -> engine canonical unit value.

    Expected cv schema:
      cv["from_display"]["scale"], cv["from_display"]["offset"]
    """
    if val is None:
        return None
    try:
        return float(val) * float(cv["from_display"]["scale"]) + float(
            cv["from_display"]["offset"]
        )
    except Exception:
        return val


def _promote_key(d: dict, legacy: str, standard: str) -> None:
    """If legacy exists, copy into standard (when missing) and remove legacy."""
    if legacy in d and standard not in d:
        d[standard] = d[legacy]
    if legacy in d:
        d.pop(legacy, None)


def _convert_inplace(d: dict, key: str, cv: dict) -> None:
    """Convert d[key] in-place if present."""
    if key in d and cv:
        d[key] = _to_engine(d[key], cv)


def apply_display_to_engine(payload: dict, conversions: dict) -> dict:
    """
    Payload (display units) -> Payload (engine canonical units)

    Engine canonical units:
      - flow: m3/h
      - pressure: bar
      - temperature: C
      - flux: LMH

    This runs BEFORE Pydantic parsing. So we:
      1) convert known numeric fields
      2) optionally absorb a few legacy keys to avoid missing conversion
    """
    d = deepcopy(payload or {})
    conversions = conversions or {}

    cv_flow = conversions.get("flow")
    cv_pressure = conversions.get("pressure")
    cv_temp = conversions.get("temperature")
    cv_flux = conversions.get("flux")

    # ----------------------
    # feed
    # ----------------------
    if isinstance(d.get("feed"), dict):
        f = d["feed"]

        # (Optional) legacy -> standard
        _promote_key(f, "flow", "flow_m3h")
        _promote_key(f, "temp_C", "temperature_C")
        _promote_key(f, "temperature_c", "temperature_C")

        _convert_inplace(f, "flow_m3h", cv_flow)
        _convert_inplace(f, "temperature_C", cv_temp)

    # ----------------------
    # stages
    # ----------------------
    if isinstance(d.get("stages"), list):
        for s in d["stages"]:
            if not isinstance(s, dict):
                continue

            # (Optional) legacy -> standard
            _promote_key(s, "pressure", "pressure_bar")
            _promote_key(s, "set_pressure", "set_pressure_bar")

            # Pressure-like inputs (RO/NF/HRRO)
            _convert_inplace(s, "pressure_bar", cv_pressure)
            _convert_inplace(s, "set_pressure_bar", cv_pressure)

            # Flux-like inputs (UF/MF, etc.)
            # Convert only the fields that represent flux rates.
            _convert_inplace(s, "flux_lmh", cv_flux)
            _convert_inplace(s, "backwash_flux_lmh", cv_flux)

    return d
