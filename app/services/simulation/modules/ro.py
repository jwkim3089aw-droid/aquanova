# app/services/simulation/modules/ro.py
from __future__ import annotations

import math
from typing import Any, Dict

from app.services.simulation.modules.base import SimulationModule
from app.api.v1.schemas import StageConfig, FeedInput, StageMetric, ModuleType

P_PERM_BAR = 0.0  # permeate backpressure (atm-ish)


def _f(v: Any, default: float) -> float:
    try:
        if v is None:
            return float(default)
        return float(v)
    except Exception:
        return float(default)


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(float(x), hi))


def _safe_exp(x: float) -> float:
    # avoid overflow (exp(700) ~ 1e304)
    return math.exp(_clamp(x, -80.0, 80.0))


def _osmotic_pressure_bar(conc_mgL: float, temp_c: float) -> float:
    """
    Very simple van't Hoff-like approximation.
    conc_mgL -> g/L: /1000
    For seawater 35 g/L -> ~27 bar (order)
    """
    c_gL = max(0.0, conc_mgL) / 1000.0
    t_k = max(1.0, temp_c + 273.15)
    # scale factor tuned for "reasonable" RO ranges (keeps your existing behavior)
    return c_gL * 0.75 * (t_k / 298.15)


class ROModule(SimulationModule):
    """
    [RO Module]
    - Solution-Diffusion + simple CP
    - Fixed-point iteration on avg_conc (bulk average) for self-consistency
    - chemistry["streams"] / chemistry["model"] 표준 출력 포함
    - IMPORTANT: 수렴 후 최종 1회 재계산으로 ndp/flux/Cp/chemistry 값 일관성 보장
    """

    def compute(self, config: StageConfig, feed: FeedInput) -> StageMetric:
        # -----------------------------
        # Inputs
        # -----------------------------
        Qf_m3h = _f(getattr(feed, "flow_m3h", None), 0.0)
        Cf_mgL = _f(getattr(feed, "tds_mgL", None), 0.0)
        T_C = _f(getattr(feed, "temperature_C", None), 25.0)

        # Geometry
        elements = max(1, int(_f(getattr(config, "elements", None), 1)))
        area_per_element = _f(getattr(config, "membrane_area_m2", None), 40.0)
        total_area = max(1e-9, elements * max(1e-9, area_per_element))

        # Membrane params (units: LMH/bar and LMH)
        A = max(0.0, _f(getattr(config, "membrane_A_lmh_bar", None), 3.0))
        B_lmh = max(0.0, _f(getattr(config, "membrane_B_lmh", None), 0.1))

        # Pressure / DP
        p_in_bar = max(0.0, _f(getattr(config, "pressure_bar", None), 15.0))
        dp_module = max(0.0, _f(getattr(config, "dp_module_bar", None), 0.2))
        dp_total = float(elements * dp_module)
        p_out_bar = max(0.0, p_in_bar - dp_total)

        # Use average feed-side pressure across module
        avg_pressure_bar = max(0.0, p_in_bar - dp_total / 2.0)
        deltaP_bar = max(0.0, avg_pressure_bar - P_PERM_BAR)

        # Early exit
        if Qf_m3h <= 1e-12 or total_area <= 1e-12 or A <= 0.0:
            chem: Dict[str, Any] = {
                "streams": {
                    "feed": {"flow_m3h": float(Qf_m3h), "tds_mgL": float(Cf_mgL)},
                    "permeate": {"flow_m3h": 0.0, "tds_mgL": 0.0},
                    "concentrate": {
                        "flow_m3h": float(Qf_m3h),
                        "tds_mgL": float(Cf_mgL),
                    },
                },
                "model": {
                    "dp_total_bar": float(dp_total),
                    "avg_pressure_bar": float(avg_pressure_bar),
                    "avg_conc_mgL": float(Cf_mgL),
                    "cp_factor_last": 1.0,
                    "p_perm_bar": float(P_PERM_BAR),
                    "delta_p_bar": float(deltaP_bar),
                    "pi_cm_bar": float(_osmotic_pressure_bar(Cf_mgL, T_C)),
                    "delta_pi_bar": float(_osmotic_pressure_bar(Cf_mgL, T_C)),
                },
            }
            return StageMetric(
                stage=0,
                module_type=ModuleType.RO,
                recovery_pct=0.0,
                flux_lmh=0.0,
                sec_kwhm3=0.0,
                ndp_bar=0.0,
                delta_pi_bar=round(_osmotic_pressure_bar(Cf_mgL, T_C), 3),
                p_in_bar=round(p_in_bar, 3),
                p_out_bar=round(p_out_bar, 3),
                Qf=round(Qf_m3h, 6),
                Qp=0.0,
                Qc=round(Qf_m3h, 6),
                Cf=round(Cf_mgL, 6),
                Cp=0.0,
                Cc=round(Cf_mgL, 6),
                chemistry=chem,
            )

        # -----------------------------
        # Fixed-point iteration on avg_conc
        # -----------------------------
        # Start with mild CP-ish guess
        avg_conc_mgL = max(0.0, Cf_mgL * 1.2)

        # Tunables
        max_iter = 20
        tol_rel = 0.01
        min_conc_frac = 0.05  # keep concentrate nonzero: Qp <= 95% of Qf
        cp_scale = 150.0  # same spirit as your code
        cp_max = 5.0  # avoid crazy CP amplification

        # Placeholders for last iteration
        last_flux_lmh = 0.0
        last_cp_factor = 1.0
        last_cm_mgL = avg_conc_mgL
        last_pi_cm_bar = 0.0
        last_ndp_bar = 0.0
        last_qp_m3h = 0.0
        last_qc_m3h = 0.0
        last_cp_mgL = 0.0
        last_cc_mgL = Cf_mgL

        for _ in range(max_iter):
            # compute using current avg_conc guess
            # Step 1) (temporary) flux based on pi at membrane surface (cm)
            # We model cm via CP factor depending on flux; use a quick inner consistency:
            # First assume cm ~ avg_conc, compute a provisional flux, then update cm once.
            pi_bulk_bar = _osmotic_pressure_bar(avg_conc_mgL, T_C)

            # provisional ndp/flux using bulk pi
            ndp_prov = max(0.0, deltaP_bar - pi_bulk_bar)
            flux_prov = A * ndp_prov

            # CP update (bounded)
            cp_factor = _safe_exp(flux_prov / cp_scale) if flux_prov > 0 else 1.0
            cp_factor = _clamp(cp_factor, 1.0, cp_max)
            cm_mgL = max(0.0, avg_conc_mgL * cp_factor)

            # use membrane-surface pi for final ndp/flux this iteration
            pi_cm_bar = _osmotic_pressure_bar(cm_mgL, T_C)
            ndp_bar = max(0.0, deltaP_bar - pi_cm_bar)
            flux_lmh = A * ndp_bar

            # permeate concentration (Solution-Diffusion)
            if (flux_lmh + B_lmh) > 1e-12:
                Cp_mgL = (B_lmh * cm_mgL) / (flux_lmh + B_lmh)
            else:
                Cp_mgL = 0.0

            Cp_mgL = max(0.0, Cp_mgL)
            # Enforce non-negative rejection vs bulk feed (stops Cp > Cf warnings)
            if Cf_mgL > 0:
                Cp_mgL = min(Cp_mgL, Cf_mgL)

            # flow from flux
            qp_m3h = (flux_lmh * total_area) / 1000.0
            if qp_m3h > Qf_m3h * (1.0 - min_conc_frac):
                qp_m3h = Qf_m3h * (1.0 - min_conc_frac)
                flux_lmh = (qp_m3h * 1000.0) / total_area

            qc_m3h = max(1e-12, Qf_m3h - qp_m3h)

            # concentrate salt balance
            Cc_mgL = (Qf_m3h * Cf_mgL - qp_m3h * Cp_mgL) / qc_m3h
            Cc_mgL = max(0.0, Cc_mgL)

            # Update avg concentration estimate
            new_avg = (Cf_mgL + Cc_mgL) / 2.0
            rel = abs(new_avg - avg_conc_mgL) / max(1e-12, avg_conc_mgL)

            # keep last iteration results for debugging (optional)
            last_flux_lmh = flux_lmh
            last_cp_factor = cp_factor
            last_cm_mgL = cm_mgL
            last_pi_cm_bar = pi_cm_bar
            last_ndp_bar = ndp_bar
            last_qp_m3h = qp_m3h
            last_qc_m3h = qc_m3h
            last_cp_mgL = Cp_mgL
            last_cc_mgL = Cc_mgL

            avg_conc_mgL = new_avg
            if rel < tol_rel:
                break

        # -----------------------------
        # FINAL recompute with converged avg_conc_mgL (self-consistent output)
        # -----------------------------
        pi_bulk_bar = _osmotic_pressure_bar(avg_conc_mgL, T_C)
        ndp_prov = max(0.0, deltaP_bar - pi_bulk_bar)
        flux_prov = A * ndp_prov

        cp_factor = _safe_exp(flux_prov / cp_scale) if flux_prov > 0 else 1.0
        cp_factor = _clamp(cp_factor, 1.0, cp_max)
        cm_mgL = max(0.0, avg_conc_mgL * cp_factor)

        pi_cm_bar = _osmotic_pressure_bar(cm_mgL, T_C)
        ndp_bar = max(0.0, deltaP_bar - pi_cm_bar)
        flux_lmh = A * ndp_bar

        if (flux_lmh + B_lmh) > 1e-12:
            Cp_mgL = (B_lmh * cm_mgL) / (flux_lmh + B_lmh)
        else:
            Cp_mgL = 0.0

        Cp_mgL = max(0.0, Cp_mgL)
        if Cf_mgL > 0:
            Cp_mgL = min(Cp_mgL, Cf_mgL)

        qp_m3h = (flux_lmh * total_area) / 1000.0
        if qp_m3h > Qf_m3h * (1.0 - min_conc_frac):
            qp_m3h = Qf_m3h * (1.0 - min_conc_frac)
            flux_lmh = (qp_m3h * 1000.0) / total_area

        qc_m3h = max(0.0, Qf_m3h - qp_m3h)
        if qc_m3h <= 1e-12:
            qc_m3h = 1e-12

        Cc_mgL = (Qf_m3h * Cf_mgL - qp_m3h * Cp_mgL) / qc_m3h
        Cc_mgL = max(0.0, Cc_mgL)

        recovery_frac = (qp_m3h / Qf_m3h) if Qf_m3h > 1e-12 else 0.0
        recovery_pct = recovery_frac * 100.0

        # Energy
        pump_eff = _clamp(_f(getattr(config, "pump_eff", None), 0.80), 0.2, 0.95)
        power_kw = (
            ((Qf_m3h * p_in_bar) / 36.0 / pump_eff)
            if (Qf_m3h > 0 and p_in_bar > 0)
            else 0.0
        )
        sec_kwhm3 = (power_kw / qp_m3h) if qp_m3h > 1e-12 else 0.0

        delta_pi_bar = pi_cm_bar  # since permeate side assumed ~0 osmotic

        chem: Dict[str, Any] = {
            "streams": {
                "feed": {"flow_m3h": float(Qf_m3h), "tds_mgL": float(Cf_mgL)},
                "permeate": {"flow_m3h": float(qp_m3h), "tds_mgL": float(Cp_mgL)},
                "concentrate": {"flow_m3h": float(qc_m3h), "tds_mgL": float(Cc_mgL)},
            },
            "model": {
                "dp_total_bar": float(dp_total),
                "avg_pressure_bar": float(avg_pressure_bar),
                "avg_conc_mgL": float(avg_conc_mgL),
                "cp_factor_last": float(cp_factor),
                "p_perm_bar": float(P_PERM_BAR),
                "delta_p_bar": float(deltaP_bar),
                "pi_cm_bar": float(pi_cm_bar),
                "delta_pi_bar": float(delta_pi_bar),
                # last iteration debug hint (optional)
                "debug_last_iter": {
                    "flux_lmh": float(last_flux_lmh),
                    "cp_factor": float(last_cp_factor),
                    "cm_mgL": float(last_cm_mgL),
                    "pi_cm_bar": float(last_pi_cm_bar),
                    "ndp_bar": float(last_ndp_bar),
                    "Qp_m3h": float(last_qp_m3h),
                    "Qc_m3h": float(last_qc_m3h),
                    "Cp_mgL": float(last_cp_mgL),
                    "Cc_mgL": float(last_cc_mgL),
                },
            },
        }

        return StageMetric(
            stage=0,  # engine에서 overwrite
            module_type=ModuleType.RO,
            recovery_pct=round(recovery_pct, 2),
            flux_lmh=round(flux_lmh, 2),
            sec_kwhm3=round(sec_kwhm3, 4),
            ndp_bar=round(ndp_bar, 3),
            delta_pi_bar=round(delta_pi_bar, 3),
            p_in_bar=round(p_in_bar, 3),
            p_out_bar=round(p_out_bar, 3),
            Qf=round(Qf_m3h, 6),
            Qp=round(qp_m3h, 6),
            Qc=round(qc_m3h, 6),
            Cf=round(Cf_mgL, 6),
            Cp=round(Cp_mgL, 6),
            Cc=round(Cc_mgL, 6),
            chemistry=chem,
        )
