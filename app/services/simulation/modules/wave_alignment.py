"""WAVE-style design diagnostics shared by RO/NF/UF modules.

This module is intentionally non-invasive: it does not change the hydraulic
solution.  It adds the WAVE-like reporting layer that AquaNova was missing:
flow table rows, per-vessel loading, design-limit checks, and UF cycle water
accounting.  The calculation helpers accept plain floats so they can be used
from the existing RO, NF, UF and future HRRO code without importing the engine.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional


def _f(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return float(default)
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _safe_get(config: Any, key: str, default: Any = None) -> Any:
    if isinstance(config, dict):
        return config.get(key, default)
    extra = getattr(config, "model_extra", None)
    if isinstance(extra, dict) and key in extra:
        return extra[key]
    pyd_extra = getattr(config, "__pydantic_extra__", None)
    if isinstance(pyd_extra, dict) and key in pyd_extra:
        return pyd_extra[key]
    cfg = getattr(config, "cfg", None)
    if isinstance(cfg, dict) and key in cfg:
        return cfg[key]
    value = getattr(config, key, None)
    return value if value is not None else default


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(float(value), hi))


def _module_value(module_type: Any) -> str:
    return str(getattr(module_type, "value", module_type) or "").upper()


def infer_element_inch(config: Any, area_per_element_m2: float = 0.0) -> int:
    """Infer element diameter without double-dividing membrane area.

    The old guideline logic sometimes interpreted a 37 m² 8-inch element as a
    4-inch element after area normalization.  WAVE-style limits must be based on
    the physical element diameter, first from explicit config and then from the
    per-element membrane area.
    """
    explicit = _safe_get(config, "element_inch", None)
    if explicit is not None:
        try:
            return 4 if int(float(explicit)) <= 4 else 8
        except (TypeError, ValueError):
            pass
    area = _f(
        _safe_get(
            config,
            "membrane_area_m2_per_element",
            _safe_get(config, "membrane_area_m2", area_per_element_m2),
        ),
        area_per_element_m2,
    )
    return 8 if area >= 30.0 else 4


def pressure_membrane_default_limits(module_type: Any, element_inch: int) -> Dict[str, float]:
    """Conservative WAVE-like display limits for RO/NF report diagnostics.

    These are advisory limits for reporting, not hard simulation constraints.
    User-supplied config values override them in ``build_pressure_membrane_alignment``.
    """
    mod = _module_value(module_type)
    if int(element_inch) <= 4:
        base = {
            "feed_flow_min_m3h_per_pv": 0.25,
            "feed_flow_max_m3h_per_pv": 4.0,
            "concentrate_flow_min_m3h_per_pv": 0.20,
            "max_flux_lmh": 38.0,
        }
    else:
        base = {
            "feed_flow_min_m3h_per_pv": 2.5,
            "feed_flow_max_m3h_per_pv": 17.0,
            "concentrate_flow_min_m3h_per_pv": 2.7,
            "max_flux_lmh": 34.0,
        }
    if mod == "NF":
        base.update({"max_flux_lmh": 45.0, "recovery_warning_pct": 90.0})
    else:
        base.update({"recovery_warning_pct": 90.0 if int(element_inch) >= 8 else 80.0})
    return base


def build_pressure_membrane_alignment(
    *,
    config: Any,
    module_type: Any,
    qf_m3h: float,
    qp_m3h: float,
    qc_m3h: float,
    feed_tds_mgL: float,
    permeate_tds_mgL: float,
    concentrate_tds_mgL: float,
    flux_lmh: float,
    ndp_bar: float,
    p_in_bar: float,
    p_out_bar: float,
    dp_total_bar: float,
    total_area_m2: float,
    vessels: int,
    elements_per_vessel: int,
    area_per_element_m2: float,
    temperature_C: Optional[float] = None,
    stage_label: Optional[str] = None,
) -> Dict[str, Any]:
    """Return WAVE-like RO/NF report and advisory checks."""
    vessels = max(1, int(vessels or 1))
    elements_per_vessel = max(1, int(elements_per_vessel or 1))
    element_inch = infer_element_inch(config, area_per_element_m2)
    limits = pressure_membrane_default_limits(module_type, element_inch)
    for key in list(limits.keys()):
        override = _safe_get(config, key, None)
        if override is not None:
            limits[key] = _f(override, limits[key])

    feed_per_pv = _f(qf_m3h) / vessels
    conc_per_pv = _f(qc_m3h) / vessels
    recovery_pct = (_f(qp_m3h) / max(1e-12, _f(qf_m3h))) * 100.0
    rejection_pct = (1.0 - _f(permeate_tds_mgL) / max(1e-12, _f(feed_tds_mgL))) * 100.0
    design_warnings: List[Dict[str, Any]] = []

    def add_warning(key: str, message: str, value: float, limit: Any, unit: str) -> None:
        design_warnings.append(
            {
                "key": key,
                "message": message,
                "value": round(_f(value), 6),
                "limit": limit,
                "unit": unit,
                "level": "WARN",
            }
        )

    if feed_per_pv > limits["feed_flow_max_m3h_per_pv"]:
        add_warning(
            "FEED_FLOW_PER_PV_HIGH",
            "Feed flow per pressure vessel is above the WAVE-style advisory range.",
            feed_per_pv,
            limits["feed_flow_max_m3h_per_pv"],
            "m3/h/PV",
        )
    if feed_per_pv < limits["feed_flow_min_m3h_per_pv"]:
        add_warning(
            "FEED_FLOW_PER_PV_LOW",
            "Feed flow per pressure vessel is below the WAVE-style advisory range.",
            feed_per_pv,
            limits["feed_flow_min_m3h_per_pv"],
            "m3/h/PV",
        )
    if conc_per_pv < limits["concentrate_flow_min_m3h_per_pv"] and recovery_pct > 0.0:
        add_warning(
            "CONCENTRATE_FLOW_PER_PV_LOW",
            "Concentrate flow per pressure vessel is below the WAVE-style minimum-flow advisory check.",
            conc_per_pv,
            limits["concentrate_flow_min_m3h_per_pv"],
            "m3/h/PV",
        )
    if _f(flux_lmh) > limits["max_flux_lmh"]:
        add_warning(
            "FLUX_HIGH",
            "Average flux is above the advisory WAVE-style design flux range.",
            flux_lmh,
            limits["max_flux_lmh"],
            "LMH",
        )
    if recovery_pct > limits["recovery_warning_pct"]:
        add_warning(
            "RECOVERY_HIGH",
            "Stage recovery is above the advisory WAVE-style recovery range.",
            recovery_pct,
            limits["recovery_warning_pct"],
            "%",
        )

    max_pressure = _safe_get(config, "design_pressure_limit_bar", _safe_get(config, "burst_pressure_limit_bar", None))
    if max_pressure is not None and _f(p_in_bar) > _f(max_pressure):
        add_warning(
            "PRESSURE_LIMIT_EXCEEDED",
            "Feed pressure exceeds the configured design pressure limit.",
            p_in_bar,
            _f(max_pressure),
            "bar",
        )

    return {
        "schema": "aquanova.wave_alignment.pressure_membrane.v1",
        "module_type": _module_value(module_type),
        "stage_label": stage_label,
        "overview": {
            "element_inch": element_inch,
            "vessel_count": vessels,
            "elements_per_vessel": elements_per_vessel,
            "total_elements": vessels * elements_per_vessel,
            "total_active_area_m2": round(_f(total_area_m2), 6),
            "temperature_C": None if temperature_C is None else round(_f(temperature_C), 3),
            "recovery_pct": round(recovery_pct, 6),
            "rejection_pct": round(rejection_pct, 6),
            "average_flux_lmh": round(_f(flux_lmh), 6),
            "ndp_bar": round(_f(ndp_bar), 6),
            "feed_flow_m3h_per_pv": round(feed_per_pv, 6),
            "concentrate_flow_m3h_per_pv": round(conc_per_pv, 6),
        },
        "flow_table": [
            {
                "stream": "Feed",
                "flow_m3h": round(_f(qf_m3h), 6),
                "tds_mgL": round(_f(feed_tds_mgL), 6),
                "pressure_bar": round(_f(p_in_bar), 6),
            },
            {
                "stream": "Permeate",
                "flow_m3h": round(_f(qp_m3h), 6),
                "tds_mgL": round(_f(permeate_tds_mgL), 6),
                "pressure_bar": 0.0,
            },
            {
                "stream": "Concentrate",
                "flow_m3h": round(_f(qc_m3h), 6),
                "tds_mgL": round(_f(concentrate_tds_mgL), 6),
                "pressure_bar": round(_f(p_out_bar), 6),
            },
        ],
        "hydraulics": {
            "dp_total_bar": round(_f(dp_total_bar), 6),
            "dp_per_element_bar": round(_f(dp_total_bar) / elements_per_vessel, 6),
            "area_per_element_m2": round(_f(area_per_element_m2), 6),
        },
        "design_limits": limits,
        "design_warnings": design_warnings,
    }


def build_uf_alignment(
    *,
    config: Any,
    qf_raw_m3h: float,
    qf_after_strainer_m3h: float,
    net_prod_m3h: float,
    concentrate_m3h: float,
    total_area_m2: float,
    flux_lmh: float,
    tmp_initial_bar: float,
    tmp_end_bar: float,
    p_in_bar: float,
    filtration_min: float,
    backwash_min: float,
    backwash_flux_lmh: float,
    strainer_waste_m3h: float,
    air_flow_nm3h: float,
    air_power_kw: float,
    ceb_naocl_kg_day: float,
    ceb_hcl_kg_day: float,
    module_count: int,
) -> Dict[str, Any]:
    """Return WAVE-like UF cycle, water-loss and cleaning diagnostics."""
    total_area_m2 = max(1e-12, _f(total_area_m2))
    cycle_min = max(1e-9, _f(filtration_min) + _f(backwash_min))
    filtration_fraction = _f(filtration_min) / cycle_min
    bw_fraction = _f(backwash_min) / cycle_min
    gross_perm_m3h = (_f(flux_lmh) * total_area_m2) / 1000.0
    bw_rate_m3h = (_f(backwash_flux_lmh) * total_area_m2) / 1000.0
    bw_loss_m3h_equiv = bw_rate_m3h * bw_fraction
    recovery_raw_pct = (_f(net_prod_m3h) / max(1e-12, _f(qf_raw_m3h))) * 100.0
    recovery_uf_pct = (_f(net_prod_m3h) / max(1e-12, _f(qf_after_strainer_m3h))) * 100.0
    max_tmp = _safe_get(config, "max_tmp_bar", None)
    max_flux = _f(_safe_get(config, "uf_max_flux_lmh", 90.0), 90.0)
    warnings: List[Dict[str, Any]] = []

    def add_warning(key: str, message: str, value: float, limit: Any, unit: str) -> None:
        warnings.append(
            {
                "key": key,
                "message": message,
                "value": round(_f(value), 6),
                "limit": limit,
                "unit": unit,
                "level": "WARN",
            }
        )

    if max_tmp is not None and _f(tmp_end_bar) > _f(max_tmp):
        add_warning(
            "UF_TMP_HIGH",
            "End-of-cycle TMP exceeds the configured UF TMP limit.",
            tmp_end_bar,
            _f(max_tmp),
            "bar",
        )
    if _f(flux_lmh) > max_flux:
        add_warning(
            "UF_FLUX_HIGH",
            "UF gross filtration flux is above the advisory design flux.",
            flux_lmh,
            max_flux,
            "LMH",
        )
    if bw_loss_m3h_equiv > max(1e-12, gross_perm_m3h * 0.25):
        add_warning(
            "UF_BACKWASH_LOSS_HIGH",
            "Backwash equivalent flow is high relative to gross filtrate production.",
            bw_loss_m3h_equiv,
            round(gross_perm_m3h * 0.25, 6),
            "m3/h",
        )

    return {
        "schema": "aquanova.wave_alignment.uf.v1",
        "overview": {
            "module_count": int(max(1, module_count or 1)),
            "total_active_area_m2": round(total_area_m2, 6),
            "gross_flux_lmh": round(_f(flux_lmh), 6),
            "gross_filtrate_rate_m3h": round(gross_perm_m3h, 6),
            "net_product_m3h": round(_f(net_prod_m3h), 6),
            "raw_feed_recovery_pct": round(recovery_raw_pct, 6),
            "uf_recovery_after_strainer_pct": round(recovery_uf_pct, 6),
            "tmp_initial_bar": round(_f(tmp_initial_bar), 6),
            "tmp_end_bar": round(_f(tmp_end_bar), 6),
            "feed_pressure_bar": round(_f(p_in_bar), 6),
        },
        "cycle": {
            "filtration_duration_min": round(_f(filtration_min), 6),
            "backwash_duration_min": round(_f(backwash_min), 6),
            "cycle_duration_min": round(cycle_min, 6),
            "filtration_fraction": round(filtration_fraction, 8),
            "backwash_fraction": round(bw_fraction, 8),
            "backwash_flux_lmh": round(_f(backwash_flux_lmh), 6),
            "backwash_rate_m3h": round(bw_rate_m3h, 6),
            "backwash_loss_m3h_equivalent": round(bw_loss_m3h_equiv, 6),
        },
        "streams": {
            "raw_feed_m3h": round(_f(qf_raw_m3h), 6),
            "after_strainer_feed_m3h": round(_f(qf_after_strainer_m3h), 6),
            "strainer_waste_m3h": round(_f(strainer_waste_m3h), 6),
            "net_permeate_m3h": round(_f(net_prod_m3h), 6),
            "concentrate_m3h": round(_f(concentrate_m3h), 6),
        },
        "cleaning": {
            "air_scour_flow_nm3h": round(_f(air_flow_nm3h), 6),
            "air_blower_avg_kw": round(_f(air_power_kw), 6),
            "ceb_naocl_kg_day": round(_f(ceb_naocl_kg_day), 6),
            "ceb_hcl_kg_day": round(_f(ceb_hcl_kg_day), 6),
        },
        "design_warnings": warnings,
    }
