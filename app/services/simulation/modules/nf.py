# app/services/simulation/modules/nf.py
from __future__ import annotations

import math
from typing import Any, Dict

from app.services.simulation.modules.base import SimulationModule
from app.api.v1.schemas import StageConfig, FeedInput, StageMetric, ModuleType

P_PERM_BAR = 0.0  # permeate backpressure


def _f(v: Any, default: float) -> float:
    try:
        if v is None:
            return float(default)
        return float(v)
    except Exception:
        return float(default)


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(float(x), hi))


class NFModule(SimulationModule):
    """
    [NF Module]
    - 낮은 압력, 선택적 제거
    - 간이 CP + rejection 기반 Cp
    - chemistry["streams"] 표준 출력 포함
    """

    def compute(self, config: StageConfig, feed: FeedInput) -> StageMetric:
        Qf_m3h = _f(getattr(feed, "flow_m3h", None), 0.0)
        Cf_mgL = _f(getattr(feed, "tds_mgL", None), 0.0)
        T_C = _f(getattr(feed, "temperature_C", None), 25.0)

        elements = max(1, int(_f(getattr(config, "elements", None), 1)))
        area_per_element = _f(getattr(config, "membrane_area_m2", None), 37.0)
        total_area = max(1e-9, elements * max(1e-9, area_per_element))

        A_lmh_bar = _f(getattr(config, "membrane_A_lmh_bar", None), 7.0)

        rej_pct = _f(getattr(config, "membrane_salt_rejection_pct", None), 90.0)
        rej_pct = _clamp(rej_pct, 0.0, 99.9)
        rejection_rate = rej_pct / 100.0

        p_in_bar = _f(getattr(config, "pressure_bar", None), 5.0)

        dp_module = _f(getattr(config, "dp_module_bar", None), 0.2)
        dp_total = elements * max(0.0, dp_module)

        avg_pressure = max(0.0, p_in_bar - (dp_total / 2.0))
        avg_conc = max(0.0, Cf_mgL * 1.1)

        flux_lmh = 0.0
        permeate_tds = 0.0
        ndp = 0.0
        concentrate_tds = Cf_mgL
        recovery_frac = 0.0

        for _ in range(10):
            temp_K = T_C + 273.15
            pi_bulk = (avg_conc / 1000.0) * 0.75 * (temp_K / 298.15)

            sigma = rejection_rate  # simplification
            pi_effective = pi_bulk * sigma

            ndp = avg_pressure - P_PERM_BAR - pi_effective
            if ndp < 0.1:
                ndp = 0.1

            flux_lmh = A_lmh_bar * ndp

            # CP
            cp_factor = math.exp(flux_lmh / 150.0) if flux_lmh > 0 else 1.0
            cm = avg_conc * cp_factor

            permeate_tds = cm * (1.0 - rejection_rate)
            permeate_tds = max(0.0, permeate_tds)

            qp_m3h = (flux_lmh * total_area) / 1000.0
            if Qf_m3h > 0 and qp_m3h > Qf_m3h * 0.95:
                qp_m3h = Qf_m3h * 0.95
                flux_lmh = (qp_m3h * 1000.0) / total_area

            recovery_frac = (qp_m3h / Qf_m3h) if Qf_m3h > 1e-12 else 0.0

            qc_m3h = max(1e-12, Qf_m3h - qp_m3h)
            concentrate_tds = (Qf_m3h * Cf_mgL - qp_m3h * permeate_tds) / qc_m3h
            concentrate_tds = max(0.0, concentrate_tds)

            new_avg_conc = (Cf_mgL + concentrate_tds) / 2.0
            if avg_conc > 1e-12 and (abs(new_avg_conc - avg_conc) / avg_conc) < 0.01:
                avg_conc = new_avg_conc
                break
            avg_conc = new_avg_conc

        qp_m3h = (flux_lmh * total_area) / 1000.0
        if Qf_m3h > 0 and qp_m3h > Qf_m3h * 0.95:
            qp_m3h = Qf_m3h * 0.95
            flux_lmh = (qp_m3h * 1000.0) / total_area

        qc_m3h = max(0.0, Qf_m3h - qp_m3h)
        recovery_pct = recovery_frac * 100.0  # ✅ FIX: percent

        pump_eff = _clamp(_f(getattr(config, "pump_eff", None), 0.80), 0.2, 0.95)
        power_kw = (
            (Qf_m3h * p_in_bar) / 36.0 / pump_eff
            if Qf_m3h > 0 and p_in_bar > 0
            else 0.0
        )
        sec_kwhm3 = power_kw / qp_m3h if qp_m3h > 1e-12 else 0.0

        chem: Dict[str, Any] = {
            "streams": {
                "feed": {"flow_m3h": float(Qf_m3h), "tds_mgL": float(Cf_mgL)},
                "permeate": {"flow_m3h": float(qp_m3h), "tds_mgL": float(permeate_tds)},
                "concentrate": {
                    "flow_m3h": float(qc_m3h),
                    "tds_mgL": float(concentrate_tds),
                },
            },
            "model": {
                "rejection_pct": float(rej_pct),
                "dp_total_bar": float(dp_total),
                "avg_pressure_bar": float(avg_pressure),
                "avg_conc_mgL": float(avg_conc),
                "cp_factor_last": float(
                    math.exp(flux_lmh / 150.0) if flux_lmh > 0 else 1.0
                ),
            },
        }

        return StageMetric(
            stage=0,  # engine에서 overwrite
            module_type=ModuleType.NF,
            recovery_pct=round(recovery_pct, 2),
            flux_lmh=round(flux_lmh, 2),
            sec_kwhm3=round(sec_kwhm3, 4),
            ndp_bar=round(ndp, 3),
            p_in_bar=round(p_in_bar, 3),
            p_out_bar=round(p_in_bar - dp_total, 3),
            Qf=round(Qf_m3h, 6),
            Qp=round(qp_m3h, 6),
            Qc=round(qc_m3h, 6),
            Cf=round(Cf_mgL, 6),
            Cp=round(permeate_tds, 6),
            Cc=round(concentrate_tds, 6),
            chemistry=chem,
        )
