# app/services/simulation/modules/ro.py
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, Tuple, List, Optional

from app.services.simulation.modules.base import SimulationModule
from app.schemas.simulation import (
    StageConfig,
    FeedInput,
    StageMetric,
    ModuleType,
    SimulationWarning,
)
from app.services.chemistry import ChemistryProfile, scale_profile_for_tds
from app.services.physics.solver import calc_spacer_k_mt
from app.services.transport import lmh_to_m_per_s
from app.services.simulation.modules.wave_alignment import build_pressure_membrane_alignment

OSMOTIC_COEFF_A = 0.00074
OSMOTIC_COEFF_B = 1.2e-9
TEMP_REF_K = 298.15
SOLVER_MAX_ITER = 30
SOLVER_TOLERANCE_LMH = 1e-4
DP_REF_BAR_PER_ELEMENT = 0.139
DP_FLOW_EXPONENT = 1.78
DP_TEMP_COEFF_PER_C = 0.0321
DP_TDS_EXPONENT = 0.65


def _f(v: Any, default: float = 0.0) -> float:
    try:
        return float(v) if v is not None else float(default)
    except (ValueError, TypeError):
        return float(default)


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(float(x), hi))


def _calc_osmotic_pressure_wave(tds_mgL: float, T_C: float) -> float:
    return ((OSMOTIC_COEFF_A * tds_mgL) + (OSMOTIC_COEFF_B * (tds_mgL**2))) * (
        (T_C + 273.15) / TEMP_REF_K
    )


def _estimate_dp_per_element_bar(
    q_feed_m3h: float,
    vessels: int,
    temperature_C: float,
    tds_mgL: float,
    multiplier: float,
) -> float:
    """Empirical spacer pressure-drop correlation fitted to WAVE stage rows.

    The fitted quantity is pressure drop per element.  It scales with feed flow
    per vessel, viscosity/temperature and salinity.  ``multiplier`` remains a
    dimensionless calibration value near one, instead of an unphysical absolute
    dP/element knob that previously saturated at 1.5 bar.
    """
    q_pv = max(float(q_feed_m3h), 0.0) / max(int(vessels), 1)
    flow_term = (max(q_pv, 0.25) / 10.0) ** DP_FLOW_EXPONENT
    temp_term = math.exp(DP_TEMP_COEFF_PER_C * (25.0 - float(temperature_C)))
    salinity_term = (1.0 + max(float(tds_mgL), 0.0) / 35000.0) ** DP_TDS_EXPONENT
    value = DP_REF_BAR_PER_ELEMENT * flow_term * temp_term * salinity_term
    return _clamp(value * max(float(multiplier), 0.0), 0.005, 3.0)


def _safe_get(config: Any, key: str, default: Any = None) -> Any:
    if isinstance(config, dict):
        return config.get(key, default)
    if (
        hasattr(config, "model_extra")
        and isinstance(config.model_extra, dict)
        and key in config.model_extra
    ):
        return config.model_extra[key]
    val = getattr(config, key, None)
    return val if val is not None else default


@dataclass
class ROSolveResult:
    qp_m3h: float
    qc_m3h: float
    flux_lmh: float
    ndp_bar: float
    pi_cm_bar: float
    p_in_bar: float
    p_out_bar: float
    avg_pressure_bar: float
    Cp_mgL: float
    Cc_mgL: float
    phi: float
    A_actual: float
    B_actual: float
    target_flow_achieved: bool = True
    pressure_limited: bool = False
    flow_error_fraction: float = 0.0


class ROModule(SimulationModule):
    @staticmethod
    def _feed_ion_dict(feed: FeedInput) -> Dict[str, float]:
        raw = getattr(feed, "ions", None)
        if raw is None:
            return {}
        if hasattr(raw, "model_dump"):
            raw = raw.model_dump()
        elif hasattr(raw, "dict"):
            raw = raw.dict()
        if not isinstance(raw, dict):
            return {}
        result: Dict[str, float] = {}
        aliases = {"boron": "b"}
        for key, value in raw.items():
            if value is None:
                continue
            canonical = str(key).lower().replace("_mgl", "").replace("mg/l", "")
            canonical = aliases.get(canonical, canonical)
            try:
                numeric = max(0.0, float(value))
            except (TypeError, ValueError):
                continue
            if numeric > 0.0:
                result[canonical] = numeric
        return result

    def _composition_b_multiplier(self, config: StageConfig, feed: FeedInput) -> float:
        """Convert ion-specific catalog rejection into a bounded scalar-B correction.

        The RO core remains a total-TDS solution-diffusion model. This factor
        preserves that stable solver while allowing real WAVE ion composition
        to influence salt passage instead of treating every feed as NaCl. NH4
        and CO2 are excluded because WAVE's reported TDS footnote excludes them.
        """
        ions = self._feed_ion_dict(feed)
        chemistry = _safe_get(config, "chemistry", {})
        rejections = chemistry.get("rejections", {}) if isinstance(chemistry, dict) else {}
        if not ions or not isinstance(rejections, dict) or not rejections:
            return 1.0

        normalized_rej = {str(key).lower(): _clamp(_f(value, 0.0), 0.0, 0.99999) for key, value in rejections.items()}
        bulk_rej = _clamp(_f(_safe_get(config, "membrane_salt_rejection_pct", 99.5), 99.5) / 100.0, 0.0, 0.99999)
        weighted_passage = 0.0
        weight = 0.0
        for ion, concentration in ions.items():
            if ion in {"nh4", "co2"}:
                continue
            rejection = normalized_rej.get(ion, bulk_rej)
            weighted_passage += concentration * (1.0 - rejection)
            weight += concentration
        if weight <= 1e-12:
            return 1.0

        reference_terms = [
            1.0 - normalized_rej[key]
            for key in ("na", "cl")
            if key in normalized_rej
        ]
        reference_passage = (
            sum(reference_terms) / len(reference_terms)
            if reference_terms
            else max(1e-5, 1.0 - bulk_rej)
        )
        actual_passage = weighted_passage / weight
        return _clamp(actual_passage / max(reference_passage, 1e-5), 0.25, 4.0)

    def compute(self, config: StageConfig, feed: FeedInput) -> StageMetric:
        Qf_m3h = _f(getattr(feed, "flow_m3h", None), 0.0)
        Cf_mgL = _f(getattr(feed, "tds_mgL", None), 0.0)
        T_C = _f(getattr(feed, "temperature_C", None), 25.0)
        feed_p_bar = max(0.0, _f(getattr(feed, "pressure_bar", None), 0.0))

        base_profile = ChemistryProfile.from_feed(feed)
        mod_type = getattr(config, "module_type", ModuleType.RO)

        vessels, elements, elements_per_vessel = self._parse_element_config(config)
        area_per_element = _f(_safe_get(config, "membrane_area_m2", 40.0), 40.0)

        stage_vessels_map = []
        if elements_per_vessel == 18:
            v1 = max(1, round(vessels * 4 / 7))
            v2 = max(1, round(vessels * 2 / 7))
            v3 = max(1, round(vessels * 1 / 7))
            stage_vessels_map = [v1] * 6 + [v2] * 6 + [v3] * 6
        elif elements_per_vessel == 12:
            v1 = max(1, round(vessels * 2 / 3))
            v2 = max(1, round(vessels * 1 / 3))
            stage_vessels_map = [v1] * 6 + [v2] * 6
        else:
            stage_vessels_map = [vessels] * elements_per_vessel

        total_area = (
            sum(stage_vessels_map)
            * area_per_element
            / elements_per_vessel
            * elements_per_vessel
        )

        # 🚀 하드코딩 제거: 외부 주입 설정값 동적 수용
        A_initial, B_initial = self._calc_initial_permeability(config, T_C)
        composition_b_multiplier = self._composition_b_multiplier(config, feed)
        B_initial *= composition_b_multiplier

        # Keep CP tuning semantics consistent across RO/NF:
        # a larger factor means stronger mass transfer and therefore lower CP.
        cp_tune = _clamp(
            _f(
                _safe_get(
                    config,
                    "cp_tuning_factor",
                    _safe_get(config, "cp_adjustment_factor", 1.0),
                ),
                1.0,
            ),
            0.05,
            20.0,
        )

        dp_correlation_enabled = bool(
            _safe_get(config, "dp_correlation_enabled", False)
        )
        dp_multiplier = _clamp(
            _f(_safe_get(config, "dp_correlation_multiplier", 1.0), 1.0),
            0.05,
            20.0,
        )
        if dp_correlation_enabled:
            dp_module = _estimate_dp_per_element_bar(
                Qf_m3h, vessels, T_C, Cf_mgL, dp_multiplier
            )
        else:
            dp_module = _f(
                _safe_get(
                    config,
                    "dp_module_bar",
                    _safe_get(config, "dp_per_elem_bar", 0.15),
                ),
                0.15,
            )
        dp_total = float(elements_per_vessel * max(0.0, dp_module))
        b_salinity_slope = _clamp(
            _f(_safe_get(config, "b_salinity_slope", 0.0), 0.0),
            0.0,
            20.0,
        )

        dp_pipe = max(0.0, _f(_safe_get(config, "pre_stage_dp_bar", 0.0), 0.0))
        p_boost = max(0.0, _f(_safe_get(config, "isbp_pressure_bar", 0.0), 0.0))
        permeate_bp = max(
            0.0, _f(_safe_get(config, "permeate_back_pressure_bar", 0.0), 0.0)
        )

        if Qf_m3h <= 1e-12 or total_area <= 1e-12 or A_initial <= 0.0:
            return self._empty_metric(Qf_m3h, Cf_mgL, feed_p_bar, permeate_bp, dp_total)

        target_qp = self._get_target_flow(config, Qf_m3h)
        max_inverse_pressure_bar = _clamp(
            _f(_safe_get(config, "max_inverse_pressure_bar", 300.0), 300.0),
            40.0,
            500.0,
        )
        if target_qp is not None:
            res, element_profiles = self._solve_inverse_target_flow(
                target_qp,
                Qf_m3h,
                Cf_mgL,
                T_C,
                base_profile,
                mod_type,
                vessels,
                elements_per_vessel,
                stage_vessels_map,
                area_per_element,
                A_initial,
                B_initial,
                b_salinity_slope,
                dp_total,
                permeate_bp,
                cp_tune,
                max_inverse_pressure_bar,
            )
        else:
            res, element_profiles = self._run_element_integration(
                float(
                    _safe_get(config, "pressure_bar", feed_p_bar - dp_pipe + p_boost)
                ),
                Qf_m3h,
                Cf_mgL,
                T_C,
                base_profile,
                mod_type,
                vessels,
                elements_per_vessel,
                stage_vessels_map,
                area_per_element,
                A_initial,
                B_initial,
                b_salinity_slope,
                dp_total,
                permeate_bp,
                cp_tune,
            )

        sec_kwhm3 = self._calc_energy(
            config,
            mod_type,
            Qf_m3h,
            res.qp_m3h,
            res.qc_m3h,
            res.p_in_bar,
            res.p_out_bar,
            A_initial,
        )
        recovery_pct = (res.qp_m3h / Qf_m3h * 100.0) if Qf_m3h > 1e-12 else 0.0
        chemistry_data = self._build_chemistry_output(
            res, base_profile, Qf_m3h, Cf_mgL, dp_total, permeate_bp, element_profiles,
            composition_b_multiplier,
            dp_module,
            dp_correlation_enabled,
            dp_multiplier,
            b_salinity_slope,
        )
        chemistry_data["wave_alignment"] = build_pressure_membrane_alignment(
            config=config,
            module_type=mod_type,
            qf_m3h=Qf_m3h,
            qp_m3h=res.qp_m3h,
            qc_m3h=res.qc_m3h,
            feed_tds_mgL=Cf_mgL,
            permeate_tds_mgL=res.Cp_mgL,
            concentrate_tds_mgL=res.Cc_mgL,
            flux_lmh=res.flux_lmh,
            ndp_bar=res.ndp_bar,
            p_in_bar=res.p_in_bar,
            p_out_bar=res.p_out_bar,
            dp_total_bar=dp_total,
            total_area_m2=total_area,
            vessels=vessels,
            elements_per_vessel=elements_per_vessel,
            area_per_element_m2=area_per_element,
            temperature_C=T_C,
            stage_label=_safe_get(config, "stage_label", None),
        )

        return StageMetric(
            stage=0,
            module_type=mod_type,
            recovery_pct=round(recovery_pct, 2),
            flux_lmh=round(res.flux_lmh, 2),
            sec_kwhm3=round(sec_kwhm3, 4),
            ndp_bar=round(res.ndp_bar, 3),
            delta_pi_bar=round(res.pi_cm_bar, 3),
            p_in_bar=round(res.p_in_bar, 3),
            p_out_bar=round(res.p_out_bar, 3),
            Qf=round(Qf_m3h, 6),
            Qp=round(res.qp_m3h, 6),
            Qc=round(res.qc_m3h, 6),
            Cf=round(Cf_mgL, 6),
            Cp=round(res.Cp_mgL, 6),
            Cc=round(res.Cc_mgL, 6),
            chemistry=chemistry_data,
            warnings=self._check_warnings(config, res.p_in_bar) or None,
        )

    def _run_element_integration(
        self,
        p_in_bar,
        Qf_m3h,
        Cf_mgL,
        T_C,
        base_profile,
        mod_type,
        vessels,
        elements_per_vessel,
        stage_vessels_map,
        area_per_element,
        A_initial,
        B_initial,
        b_salinity_slope,
        dp_total,
        permeate_bp,
        cp_tune,
    ) -> Tuple[ROSolveResult, List[Dict]]:
        current_vessel_flow = Qf_m3h / stage_vessels_map[0]
        c_in, p_in = Cf_mgL, p_in_bar
        dp_elem_base = dp_total / max(1, elements_per_vessel)
        sum_qp, sum_qp_cp, sum_flux, sum_ndp = 0.0, 0.0, 0.0, 0.0
        profiles, last_phi, last_A, last_B, last_pi = [], 1.0, A_initial, B_initial, 0.0

        for e in range(1, elements_per_vessel + 1):
            idx = e - 1
            current_vessels = stage_vessels_map[idx]
            if idx > 0 and stage_vessels_map[idx] < stage_vessels_map[idx - 1]:
                current_vessel_flow = (
                    current_vessel_flow * stage_vessels_map[idx - 1]
                ) / current_vessels

            dp_elem = dp_elem_base * (
                (current_vessel_flow / max(1e-5, Qf_m3h / vessels)) ** 1.6
            )
            avg_p = p_in - dp_elem / 2.0
            wall_c, flux, ndp, phi = c_in, 0.0, 0.0, 1.0

            for _ in range(SOLVER_MAX_ITER):
                pi_bar = _calc_osmotic_pressure_wave(wall_c, T_C)
                ndp = max(0.0, avg_p - permeate_bp - pi_bar)
                flux_new = A_initial * ndp
                if abs(flux - flux_new) < SOLVER_TOLERANCE_LMH:
                    flux = flux_new
                    break
                flux = 0.5 * flux + 0.5 * flux_new

                avg_q = max(
                    current_vessel_flow * 0.1,
                    current_vessel_flow - ((flux * area_per_element) / 2000.0),
                )
                effective_k = calc_spacer_k_mt((avg_q / 3600.0) / 0.0037, T_C) * cp_tune
                phi = (
                    math.exp(min(lmh_to_m_per_s(flux) / effective_k, 3.0))
                    if effective_k > 1e-12
                    else 1.0
                )
                wall_c = c_in * phi

            qp_elem = min(
                (flux * area_per_element) / 1000.0, current_vessel_flow * 0.95
            )
            flux = (qp_elem * 1000.0) / area_per_element
            # Solution-diffusion salt passage: Cp = B * Cm / (Jw + B).
            # CP belongs in the membrane-wall concentration (Cm), not in B.
            wall_c = c_in * phi
            salinity_ratio = min(max(wall_c, 0.0) / 35000.0, 10.0)
            B_effective = B_initial * (1.0 + b_salinity_slope * salinity_ratio)
            cp_elem = (B_effective * wall_c) / max(1e-12, flux + B_effective)
            cp_elem = _clamp(cp_elem, 0.0, wall_c)

            profiles.append(
                {
                    "element": e,
                    "flux_lmh": round(flux, 2),
                    "ndp_bar": round(ndp, 2),
                    "recovery_pct": round(
                        (qp_elem / max(1e-12, current_vessel_flow)) * 100.0, 2
                    ),
                    "pressure_in_bar": round(p_in, 2),
                    "feed_tds_mgL": round(c_in, 1),
                    "perm_tds_mgL": round(cp_elem, 1),
                }
            )
            sum_qp += qp_elem * current_vessels
            sum_qp_cp += (qp_elem * current_vessels) * cp_elem
            sum_flux += flux
            sum_ndp += ndp

            current_vessel_flow = max(1e-12, current_vessel_flow - qp_elem)
            c_in = max(
                0.0,
                (c_in * (current_vessel_flow + qp_elem) - qp_elem * cp_elem)
                / current_vessel_flow,
            )
            p_in -= dp_elem
            last_phi, last_A, last_B, last_pi = phi, A_initial, B_effective, pi_bar

        total_qp = sum_qp
        return (
            ROSolveResult(
                qp_m3h=total_qp,
                qc_m3h=max(1e-12, Qf_m3h - total_qp),
                flux_lmh=sum_flux / elements_per_vessel,
                ndp_bar=sum_ndp / elements_per_vessel,
                pi_cm_bar=last_pi,
                p_in_bar=p_in_bar,
                p_out_bar=max(0.0, p_in),
                avg_pressure_bar=max(0.0, p_in_bar - (p_in_bar - p_in) / 2.0),
                Cp_mgL=sum_qp_cp / max(1e-12, sum_qp),
                Cc_mgL=c_in,
                phi=last_phi,
                A_actual=last_A,
                B_actual=last_B,
            ),
            profiles,
        )

    def _solve_inverse_target_flow(
        self,
        target_qp,
        Qf_m3h,
        Cf_mgL,
        T_C,
        base_profile,
        mod_type,
        vessels,
        elements_per_vessel,
        stage_vessels_map,
        area_per_element,
        A_initial,
        B_initial,
        b_salinity_slope,
        dp_total,
        permeate_bp,
        cp_tune,
        max_pressure_bar,
    ) -> Tuple[ROSolveResult, List[Dict]]:
        low_p = permeate_bp + 1.0
        high_p = min(80.0, max_pressure_bar)
        flow_tolerance = max(1e-3, abs(target_qp) * 1e-5)

        # Expand the pressure bracket before bisection. Extreme recovery/high-TDS
        # cases must not silently saturate at a hard-coded 120 bar ceiling.
        high_res, high_profiles = None, []
        while high_p <= max_pressure_bar + 1e-9:
            high_res, high_profiles = self._run_element_integration(
                high_p,
                Qf_m3h,
                Cf_mgL,
                T_C,
                base_profile,
                mod_type,
                vessels,
                elements_per_vessel,
                stage_vessels_map,
                area_per_element,
                A_initial,
                B_initial,
                b_salinity_slope,
                dp_total,
                permeate_bp,
                cp_tune,
            )
            if high_res.qp_m3h >= target_qp:
                break
            high_p = min(max_pressure_bar, high_p * 1.5)
            if high_p >= max_pressure_bar:
                if high_res.p_in_bar >= max_pressure_bar - 1e-9:
                    break

        if high_res is None:
            raise RuntimeError("RO inverse solver failed to initialize pressure bracket")

        if high_res.qp_m3h < target_qp:
            high_res.target_flow_achieved = False
            high_res.pressure_limited = True
            high_res.flow_error_fraction = abs(high_res.qp_m3h - target_qp) / max(
                abs(target_qp), 1e-12
            )
            return high_res, high_profiles

        best_res, best_profiles = high_res, high_profiles
        for _ in range(60):
            mid_p = (low_p + high_p) / 2.0
            res, profiles = self._run_element_integration(
                mid_p,
                Qf_m3h,
                Cf_mgL,
                T_C,
                base_profile,
                mod_type,
                vessels,
                elements_per_vessel,
                stage_vessels_map,
                area_per_element,
                A_initial,
                B_initial,
                b_salinity_slope,
                dp_total,
                permeate_bp,
                cp_tune,
            )
            best_res, best_profiles = res, profiles
            if abs(res.qp_m3h - target_qp) <= flow_tolerance:
                break
            if res.qp_m3h < target_qp:
                low_p = mid_p
            else:
                high_p = mid_p

        best_res.flow_error_fraction = abs(best_res.qp_m3h - target_qp) / max(
            abs(target_qp), 1e-12
        )
        best_res.target_flow_achieved = best_res.flow_error_fraction <= 1e-3
        best_res.pressure_limited = not best_res.target_flow_achieved and (
            best_res.p_in_bar >= max_pressure_bar * 0.999
        )
        return best_res, best_profiles

    def _parse_element_config(self, config: StageConfig) -> Tuple[int, int, int]:
        vessels = max(1, int(_f(_safe_get(config, "vessel_count", 10), 10)))
        elements_per_vessel = int(_f(_safe_get(config, "elements_per_vessel", 6), 6))
        return vessels, max(1, vessels * elements_per_vessel), elements_per_vessel

    def _calc_initial_permeability(
        self, config: StageConfig, T_C: float
    ) -> Tuple[float, float]:
        flow_factor = _f(_safe_get(config, "flow_factor", 1.0), 1.0)
        spi = _f(_safe_get(config, "spi", 1.0), 1.0)
        A_base = max(0.0, _f(_safe_get(config, "membrane_A_lmh_bar", 3.0), 3.0))
        B_base = max(0.0, _f(_safe_get(config, "membrane_B_lmh", 0.1), 0.1))

        A_corr = _f(_safe_get(config, "A_correction_factor", 1.0), 1.0)
        B_corr = _f(_safe_get(config, "B_correction_factor", 1.0), 1.0)

        # Fouling/aging primarily reduces water permeability. Salt passage can be
        # adjusted independently when a measured B degradation factor is known.
        fouling_factor = _clamp(
            _f(_safe_get(config, "fouling_factor", 1.0), 1.0), 0.05, 1.20
        )
        b_fouling_factor = _clamp(
            _f(_safe_get(config, "B_fouling_factor", 1.0), 1.0), 0.05, 20.0
        )

        temp_corr_A = _f(_safe_get(config, "temp_corr_factor_A", 2640.0), 2640.0)
        temp_corr_B = _f(_safe_get(config, "temp_corr_factor_B", 3500.0), 3500.0)

        T_K = T_C + 273.15
        tcf_A = math.exp(temp_corr_A * (1.0 / TEMP_REF_K - 1.0 / T_K))
        tcf_B = math.exp(temp_corr_B * (1.0 / TEMP_REF_K - 1.0 / T_K))

        return (
            A_base * A_corr * flow_factor * fouling_factor * tcf_A,
            B_base * B_corr * spi * b_fouling_factor * tcf_B,
        )

    def _get_target_flow(self, config: StageConfig, Qf_m3h: float) -> Optional[float]:
        target_recovery = _safe_get(config, "recovery_target_pct")
        if target_recovery is not None:
            return Qf_m3h * (_clamp(target_recovery, 0.0, 99.5) / 100.0)
        return None

    def _calc_energy(
        self, config, mod_type, Qf_m3h, qp_m3h, qc_m3h, p_in_bar, p_out_bar, A_initial
    ) -> float:
        power_base_kw = (Qf_m3h * p_in_bar) / (
            36.0 * _clamp(_f(_safe_get(config, "pump_eff", 0.80), 0.80), 0.2, 0.95)
        )
        if mod_type == ModuleType.RO and A_initial < 3.0:
            return max(
                0.01,
                (
                    max(0.0, power_base_kw - (qc_m3h * p_out_bar) / (36.0 * 0.95))
                    / max(1e-9, qp_m3h)
                )
                * 1.36,
            )
        return max(0.01, (power_base_kw / max(1e-9, qp_m3h)) * 0.85)

    def _build_chemistry_output(
        self, res, base_profile, Qf_m3h, Cf_mgL, dp_total, permeate_bp, element_profiles,
        composition_b_multiplier: float = 1.0,
        dp_per_element_bar: float = 0.0,
        dp_correlation_enabled: bool = False,
        dp_correlation_multiplier: float = 1.0,
        b_salinity_slope: float = 0.0,
    ) -> Dict:
        return {
            "streams": {
                "feed": {
                    "flow_m3h": float(Qf_m3h),
                    "tds_mgL": float(Cf_mgL),
                    "pressure_bar": float(res.p_in_bar),
                    "ions": base_profile.to_dict(),
                },
                "permeate": {
                    "flow_m3h": float(res.qp_m3h),
                    "tds_mgL": float(res.Cp_mgL),
                    "pressure_bar": float(permeate_bp),
                    "ions": scale_profile_for_tds(base_profile, res.Cp_mgL).to_dict(),
                },
                "concentrate": {
                    "flow_m3h": float(res.qc_m3h),
                    "tds_mgL": float(res.Cc_mgL),
                    "pressure_bar": float(res.p_out_bar),
                    "ions": scale_profile_for_tds(base_profile, res.Cc_mgL).to_dict(),
                },
            },
            "model": {
                "dp_total_bar": float(dp_total),
                "avg_pressure_bar": float(res.avg_pressure_bar),
                "cp_factor_last": float(res.phi),
                "pi_cm_bar": float(res.pi_cm_bar),
                "target_flow_achieved": bool(res.target_flow_achieved),
                "pressure_limited": bool(res.pressure_limited),
                "flow_error_fraction": float(res.flow_error_fraction),
                "composition_b_multiplier": float(composition_b_multiplier),
                "dp_per_element_bar": float(dp_per_element_bar),
                "dp_correlation_enabled": bool(dp_correlation_enabled),
                "dp_correlation_multiplier": float(dp_correlation_multiplier),
                "b_salinity_slope": float(b_salinity_slope),
            },
            "elements": element_profiles,
        }

    def _check_warnings(self, config, p_in_bar) -> List[SimulationWarning]:
        return []

    def _empty_metric(self, Qf, Cf, feed_p, p_bp, dp) -> StageMetric:
        return StageMetric(
            stage=0,
            module_type=ModuleType.RO,
            recovery_pct=0.0,
            flux_lmh=0.0,
            sec_kwhm3=0.0,
            ndp_bar=0.0,
            delta_pi_bar=0.0,
            p_in_bar=0.0,
            p_out_bar=0.0,
            Qf=Qf,
            Qp=0.0,
            Qc=Qf,
            Cf=Cf,
            Cp=0.0,
            Cc=Cf,
            chemistry={},
            warnings=None,
        )
