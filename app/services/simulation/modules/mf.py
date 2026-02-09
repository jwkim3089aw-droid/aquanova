# app/services/simulation/modules/mf.py
# ✅ MF Physics + simple TMP model
# ✅ "Cp 대신 permeate/product 정의"를 chemistry["streams"]로 명시 (엔진 SSOT 연동)

from __future__ import annotations

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


class MFModule(SimulationModule):
    """
    [MF Module]
    - UF보다 큰 기공 → 더 높은 permeability/flux
    - TDS 제거율은 사실상 0% (SS/박테리아 제거 목적)
    - chemistry["streams"]로 permeate/concentrate/feed 정의를 명시
    """

    def compute(self, config: StageConfig, feed: FeedInput) -> StageMetric:
        feed_flow = _f(getattr(feed, "flow_m3h", None), 0.0)
        cf_tds = _f(getattr(feed, "tds_mgL", None), 0.0)
        temp_c = _f(getattr(feed, "temperature_C", None), 25.0)

        elements = max(1, int(_f(getattr(config, "elements", None), 1)))
        area_per_el = _f(getattr(config, "membrane_area_m2", None), 60.0)
        total_area = max(1e-9, elements * max(1e-9, area_per_el))

        flux_lmh = _f(getattr(config, "flux_lmh", None), 80.0)
        bw_flux_lmh = _f(getattr(config, "backwash_flux_lmh", None), flux_lmh * 2.0)

        filt_min = _f(getattr(config, "filtration_cycle_min", None), 20.0)
        bw_sec = _f(getattr(config, "backwash_duration_sec", None), 60.0)

        filt_min = max(0.1, filt_min)
        bw_min = max(0.0, bw_sec / 60.0)

        # 유지관리 손실(CIP/CEB 등) - 기본 2% 손실
        cip_loss_factor = _f(getattr(config, "mf_cip_loss_factor", None), 0.98)
        cip_loss_factor = _clamp(cip_loss_factor, 0.7, 1.0)

        # Cycle fractions
        cycle_time_min = max(1e-6, filt_min + bw_min)
        filt_frac = filt_min / cycle_time_min
        bw_frac = bw_min / cycle_time_min

        gross_prod_rate_m3h = (flux_lmh * total_area) / 1000.0
        if feed_flow > 0 and gross_prod_rate_m3h > feed_flow:
            gross_prod_rate_m3h = feed_flow
            flux_lmh = (gross_prod_rate_m3h * 1000.0) / total_area

        bw_rate_m3h = (bw_flux_lmh * total_area) / 1000.0

        net_prod_m3h = (
            gross_prod_rate_m3h * filt_frac - bw_rate_m3h * bw_frac
        ) * cip_loss_factor
        net_prod_m3h = max(0.0, net_prod_m3h)
        if feed_flow > 0 and net_prod_m3h > feed_flow:
            net_prod_m3h = feed_flow

        recovery_pct = (net_prod_m3h / feed_flow * 100.0) if feed_flow > 1e-12 else 0.0
        qc_m3h = max(0.0, feed_flow - net_prod_m3h)

        # TMP model (very high permeability)
        # permeability @25C (LMH/bar)
        permeability_25c = _f(
            getattr(config, "mf_permeability_25c_lmh_bar", None), 500.0
        )
        # simple temp correction (optional)
        temp_corr = 1.0 + 0.025 * (temp_c - 25.0)
        temp_corr = _clamp(temp_corr, 0.5, 2.0)
        permeability = max(1e-9, permeability_25c * temp_corr)

        tmp_bar = flux_lmh / permeability
        tmp_bar = max(0.0, tmp_bar)

        p_out = _f(getattr(config, "mf_p_out_bar", None), 0.5)
        header_loss = _f(getattr(config, "mf_header_loss_bar", None), 0.0)
        p_in = p_out + tmp_bar + header_loss

        pump_eff = _f(getattr(config, "pump_eff", None), 0.75)
        pump_eff = _clamp(pump_eff, 0.2, 0.95)

        power_kw = (
            (feed_flow * p_in) / 36.0 / pump_eff if feed_flow > 0 and p_in > 0 else 0.0
        )
        sec = power_kw / net_prod_m3h if net_prod_m3h > 1e-12 else 0.0

        chem: Dict[str, Any] = {
            "streams": {
                "feed": {"flow_m3h": float(feed_flow), "tds_mgL": float(cf_tds)},
                "permeate": {
                    "flow_m3h": float(net_prod_m3h),
                    "tds_mgL": float(cf_tds),
                    "definition": "MF permeate (TDS ~ unchanged)",
                },
                "concentrate": {
                    "flow_m3h": float(qc_m3h),
                    "tds_mgL": float(cf_tds),
                    "definition": "MF waste/backwash (TDS ~ unchanged)",
                },
            },
            "model": {
                "temp_C": float(temp_c),
                "permeability_25c_lmh_bar": float(permeability_25c),
                "temp_corr": float(temp_corr),
                "permeability_lmh_bar": float(permeability),
                "tmp_bar": float(tmp_bar),
                "filtration_min": float(filt_min),
                "backwash_min": float(bw_min),
                "filt_frac": float(filt_frac),
                "bw_frac": float(bw_frac),
                "cip_loss_factor": float(cip_loss_factor),
                "net_prod_m3h": float(net_prod_m3h),
            },
        }

        return StageMetric(
            stage=0,  # engine에서 overwrite
            module_type=ModuleType.MF,
            recovery_pct=round(recovery_pct, 2),
            flux_lmh=round(flux_lmh, 1),
            ndp_bar=round(tmp_bar, 3),  # TMP를 ndp_bar에 매핑
            sec_kwhm3=round(sec, 4),
            p_in_bar=round(p_in, 3),
            p_out_bar=round(p_out, 3),
            Qf=round(feed_flow, 6),
            Qp=round(net_prod_m3h, 6),
            Qc=round(qc_m3h, 6),
            Cf=round(cf_tds, 6),
            Cp=round(cf_tds, 6),  # fallback
            Cc=round(cf_tds, 6),  # fallback
            chemistry=chem,
        )
