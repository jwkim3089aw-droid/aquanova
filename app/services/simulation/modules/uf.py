# app/services/simulation/modules/uf.py
# ✅ UF Physics + Temperature viscosity correction
# ✅ "Cp 대신 permeate/product 정의"를 chemistry["streams"]로 명시 (엔진 SSOT 연동)

from __future__ import annotations

import math
from typing import Any, Dict

from app.services.simulation.modules.base import SimulationModule
from app.api.v1.schemas import StageConfig, FeedInput, StageMetric, ModuleType


def _f(v: Any, default: float) -> float:
    try:
        if v is None:
            return float(default)
        return float(v)
    except Exception:
        return float(default)


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(float(x), hi))


class UFModule(SimulationModule):
    """
    [UF High-Fidelity Module]
    - Temperature viscosity correction (permeability ~ 1/viscosity)
    - Backwash recovery logic
    - chemistry["streams"]로 permeate/concentrate/feed 정의를 명시 (Cp 의존 제거)
    """

    def compute(self, config: StageConfig, feed: FeedInput) -> StageMetric:
        # 1) Inputs
        feed_flow = _f(getattr(feed, "flow_m3h", None), 0.0)
        cf_tds = _f(getattr(feed, "tds_mgL", None), 0.0)
        temp_c = _f(getattr(feed, "temperature_C", None), 25.0)

        elements = max(1, int(_f(getattr(config, "elements", None), 1)))
        area_per_el = _f(getattr(config, "membrane_area_m2", None), 50.0)
        total_area = max(1e-9, elements * max(1e-9, area_per_el))

        target_flux = _f(getattr(config, "flux_lmh", None), 60.0)
        bw_flux = _f(getattr(config, "backwash_flux_lmh", None), target_flux * 1.5)

        t_filt_min = _f(getattr(config, "filtration_cycle_min", None), 30.0)
        t_bw_min = _f(getattr(config, "backwash_duration_sec", None), 60.0) / 60.0
        t_filt_min = max(0.1, t_filt_min)
        t_bw_min = max(0.0, t_bw_min)

        # 2) Viscosity correction (Vogel approximation)
        # mu_t: 상대적으로 "온도에 따른 점도" (임의 단위여도 ratio 목적이면 OK)
        mu_20 = 1.002  # reference-ish
        mu_t = 1.234 * (10 ** ((247.8 / (temp_c + 133.15)) - 1.2))
        mu_t = max(1e-9, float(mu_t))

        temp_corr_factor = mu_20 / mu_t
        temp_corr_factor = _clamp(temp_corr_factor, 0.25, 4.0)

        # Standard permeability @20C (Lp)
        Lp_20 = _f(
            getattr(config, "uf_Lp_20_lmh_bar", None), 250.0
        )  # optional override
        Lp_20 = max(1e-9, float(Lp_20))
        Lp_actual = Lp_20 * temp_corr_factor

        # 3) TMP (bar): J = Lp * TMP
        tmp_bar = target_flux / max(Lp_actual, 1e-9)

        # Fouling/cake factor (optional override)
        fouling_factor = _f(getattr(config, "uf_fouling_factor", None), 1.10)
        fouling_factor = _clamp(fouling_factor, 1.0, 3.0)
        tmp_bar *= fouling_factor

        # 4) Net production (m3/h) with filtration/backwash duty
        cycle_total_min = max(1e-6, t_filt_min + t_bw_min)
        filt_frac = t_filt_min / cycle_total_min
        bw_frac = t_bw_min / cycle_total_min

        gross_prod_rate_m3h = (target_flux * total_area) / 1000.0
        bw_rate_m3h = (bw_flux * total_area) / 1000.0

        vol_prod_m3h = gross_prod_rate_m3h * filt_frac
        vol_bw_m3h = bw_rate_m3h * bw_frac

        net_prod_m3h = vol_prod_m3h - vol_bw_m3h
        net_prod_m3h = max(0.0, net_prod_m3h)

        if feed_flow > 0 and net_prod_m3h > feed_flow:
            net_prod_m3h = feed_flow

        recovery_pct = (net_prod_m3h / feed_flow * 100.0) if feed_flow > 1e-12 else 0.0
        qc_m3h = max(0.0, feed_flow - net_prod_m3h)

        # 5) Pressure + SEC
        p_out = _f(getattr(config, "uf_p_out_bar", None), 0.5)  # backpressure
        header_loss = _f(getattr(config, "uf_header_loss_bar", None), 0.2)
        p_in = p_out + tmp_bar + header_loss

        pump_eff = _f(getattr(config, "pump_eff", None), 0.75)
        pump_eff = _clamp(pump_eff, 0.2, 0.95)

        power_kw = (
            (feed_flow * p_in) / 36.0 / pump_eff if feed_flow > 0 and p_in > 0 else 0.0
        )
        sec = power_kw / net_prod_m3h if net_prod_m3h > 1e-12 else 0.0

        # ✅ UF는 TDS 제거가 사실상 0% → permeate/concentrate TDS는 feed와 동일로 둔다.
        # (엔진은 chemistry["streams"]를 최우선으로 사용하므로 Cp에 의존하지 않게 됨)
        chem: Dict[str, Any] = {
            "streams": {
                "feed": {"flow_m3h": float(feed_flow), "tds_mgL": float(cf_tds)},
                "permeate": {
                    "flow_m3h": float(net_prod_m3h),
                    "tds_mgL": float(cf_tds),
                    "definition": "UF permeate (TDS ~ unchanged)",
                },
                "concentrate": {
                    "flow_m3h": float(qc_m3h),
                    "tds_mgL": float(cf_tds),
                    "definition": "UF waste/backwash (TDS ~ unchanged)",
                },
            },
            "model": {
                "temp_C": float(temp_c),
                "temp_corr_factor": float(temp_corr_factor),
                "Lp_20_lmh_bar": float(Lp_20),
                "Lp_actual_lmh_bar": float(Lp_actual),
                "tmp_bar": float(tmp_bar),
                "fouling_factor": float(fouling_factor),
                "filtration_min": float(t_filt_min),
                "backwash_min": float(t_bw_min),
                "filt_frac": float(filt_frac),
                "bw_frac": float(bw_frac),
                "gross_prod_rate_m3h": float(gross_prod_rate_m3h),
                "bw_rate_m3h": float(bw_rate_m3h),
                "net_prod_m3h": float(net_prod_m3h),
            },
        }

        return StageMetric(
            stage=0,  # engine에서 overwrite
            module_type=ModuleType.UF,
            recovery_pct=round(recovery_pct, 2),
            flux_lmh=round(target_flux, 1),
            ndp_bar=round(tmp_bar, 3),  # TMP를 ndp_bar 필드에 매핑
            sec_kwhm3=round(sec, 4),
            p_in_bar=round(p_in, 3),
            p_out_bar=round(p_out, 3),
            Qf=round(feed_flow, 6),
            Qp=round(net_prod_m3h, 6),
            Qc=round(qc_m3h, 6),
            Cf=round(cf_tds, 6),
            # backward-compatible fallback(엔진 override가 있으면 Cp를 안 봄)
            Cp=round(cf_tds, 6),
            Cc=round(cf_tds, 6),
            chemistry=chem,
        )
