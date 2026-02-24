# app/services/simulation/modules/uf.py
# =============================================================================
# [AquaNova UF Physics Engine] Feed-Driven Mass Balance Patch
# - System Feed 유량을 100% 수용하여 전체 질량 수지 오차(BAL FAIL) 완벽 해결
# - 지정된 모듈 수와 유입 유량에 맞춰 '실제 운전 플럭스(Operating Flux)' 역산 산출
# =============================================================================

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
    def compute(self, config: StageConfig, feed: FeedInput) -> StageMetric:
        # ==========================================
        # 1. Inputs & Geometry
        # ==========================================
        cf_tds = _f(getattr(feed, "tds_mgL", None), 0.0)
        temp_c = _f(getattr(feed, "temperature_C", None), 25.0)
        feed_flow = _f(
            getattr(feed, "flow_m3h", None), 0.0
        )  # 시스템에서 밀어주는 실제 유입수

        elements = max(1, int(_f(getattr(config, "elements", None), 1)))
        area_per_el = _f(getattr(config, "membrane_area_m2_per_element", None), 77.0)

        if getattr(config, "membrane_area_m2", None):
            total_area = _f(config.membrane_area_m2, 77.0 * elements)
        else:
            total_area = max(1e-9, elements * area_per_el)

        maint = getattr(config, "uf_maintenance", None)

        t_filt_min = _f(getattr(maint, "filtration_duration_min", None), 60.0)
        t_bw_sec = _f(getattr(maint, "backwash_duration_sec", None), 60.0)
        t_air_sec = _f(getattr(maint, "air_scour_duration_sec", None), 30.0)
        t_ff_sec = _f(getattr(maint, "forward_flush_duration_sec", None), 30.0)

        # 사용자가 폼에 입력한 참고용 플럭스 (실제 계산 시에는 역산된 플럭스를 사용)
        design_flux = _f(getattr(config, "design_flux_lmh", None), 55.5)
        bw_flux = _f(getattr(maint, "backwash_flux_lmh", None), 100.0)
        ff_flow_mod = _f(getattr(maint, "forward_flush_flow_m3h_per_mod", None), 2.83)

        strainer_rec = _f(getattr(config, "strainer_recovery_pct", None), 99.5) / 100.0
        strainer_rec = _clamp(strainer_rec, 0.01, 1.0)

        # ==========================================
        # 2. Mass Balance (Feed-Driven Dynamics 🚀)
        # ==========================================
        # AquaNova는 앞에서 들어온 물을 무조건 다 처리해야 합니다 (Mass Balance 일치화)
        raw_intake_m3h = feed_flow
        uf_feed_in_m3h = raw_intake_m3h * strainer_rec
        strainer_loss_m3h = raw_intake_m3h - uf_feed_in_m3h

        # 사이클 시간 분율 계산
        cycle_total_min = t_filt_min + (t_bw_sec + t_air_sec + t_ff_sec) / 60.0
        cycle_total_min = max(1e-6, cycle_total_min)

        frac_filt = t_filt_min / cycle_total_min
        frac_bw = (t_bw_sec / 60.0) / cycle_total_min
        frac_ff = (t_ff_sec / 60.0) / cycle_total_min

        # 포워드 플러시 손실량 (고정)
        ff_rate_m3h = ff_flow_mod * elements
        avg_ff_loss_m3h = ff_rate_m3h * frac_ff

        # 들어온 물(uf_feed)에서 FF로 쓴 물을 빼면, 여과로 만들어내야 하는 총 생산량(Gross)이 나옴
        avg_gross_prod_m3h = max(0.0, uf_feed_in_m3h - avg_ff_loss_m3h)
        gross_flow_m3h = avg_gross_prod_m3h / frac_filt if frac_filt > 0 else 0.0

        # 💡 핵심: 이 유량을 소화하기 위해 모듈이 내야 하는 [실제 운전 플럭스] 역산
        operating_flux_lmh = (
            (gross_flow_m3h * 1000.0) / total_area if total_area > 0 else 0.0
        )

        # 역세척 손실량 산출 (BW 플럭스는 별도 펌프로 밀어주므로 고정값 유지)
        bw_rate_m3h = (bw_flux * total_area) / 1000.0
        avg_bw_loss_m3h = bw_rate_m3h * frac_bw

        # 최종 폐수량 및 순 생산량
        total_backwash_loss_m3h = avg_bw_loss_m3h + avg_ff_loss_m3h
        net_flow_m3h = max(0.0, avg_gross_prod_m3h - avg_bw_loss_m3h)
        average_flux_lmh = (
            (net_flow_m3h * 1000.0) / total_area if total_area > 0 else 0.0
        )

        gross_recovery_pct = (
            (avg_gross_prod_m3h / uf_feed_in_m3h * 100.0) if uf_feed_in_m3h > 0 else 0.0
        )
        net_recovery_pct = (
            (net_flow_m3h / raw_intake_m3h * 100.0) if raw_intake_m3h > 0 else 0.0
        )

        # ==========================================
        # 3. Temperature Viscosity & Pressure
        # ==========================================
        mu_20 = 1.002
        mu_t = 1.234 * (10 ** ((247.8 / (temp_c + 133.15)) - 1.2))
        temp_corr_factor = _clamp(mu_20 / max(1e-9, float(mu_t)), 0.25, 4.0)

        Lp_20 = _f(getattr(config, "uf_Lp_20_lmh_bar", None), 250.0)
        Lp_actual = Lp_20 * temp_corr_factor

        flow_factor = _clamp(_f(getattr(config, "flow_factor", None), 1.0), 0.1, 1.0)

        # 압력 계산 시 사용자 입력 플럭스가 아닌 [실제 운전 플럭스(operating_flux_lmh)] 적용!
        tmp_bar = operating_flux_lmh / max(Lp_actual * flow_factor, 1e-9)

        p_out = _f(getattr(config, "permeate_back_pressure_bar", None), 0.5)
        header_loss = _f(getattr(config, "dp_module_bar", None), 0.2)
        p_in = p_out + tmp_bar + header_loss

        pump_eff = _clamp(_f(getattr(config, "pump_eff", None), 0.75), 0.2, 0.95)
        power_kw = (
            (uf_feed_in_m3h * p_in) / 36.0 / pump_eff if uf_feed_in_m3h > 0 else 0.0
        )
        sec = power_kw / net_flow_m3h if net_flow_m3h > 1e-12 else 0.0

        # ==========================================
        # 4. Output Mapping
        # ==========================================
        total_waste_m3h = total_backwash_loss_m3h + strainer_loss_m3h

        chem: Dict[str, Any] = {
            "streams": {
                "feed": {"flow_m3h": float(raw_intake_m3h), "tds_mgL": float(cf_tds)},
                "permeate": {
                    "flow_m3h": float(net_flow_m3h),
                    "tds_mgL": float(cf_tds),
                    "definition": "Net UF Filtrate",
                },
                "concentrate": {
                    "flow_m3h": float(total_waste_m3h),
                    "tds_mgL": float(cf_tds),
                    "definition": "UF Backwash + FF + Strainer Waste",
                },
            },
            "model": {
                "temp_corr_factor": float(temp_corr_factor),
                "Lp_actual_lmh_bar": float(Lp_actual),
                "operating_flux_lmh": float(operating_flux_lmh),
            },
        }

        return StageMetric(
            stage=0,
            module_type=ModuleType.UF,
            design_flux_lmh=round(design_flux, 2),
            instantaneous_flux_lmh=round(
                operating_flux_lmh, 2
            ),  # 역산된 실제 플럭스 반환
            average_flux_lmh=round(average_flux_lmh, 2),
            flux_lmh=round(average_flux_lmh, 2),
            gross_flow_m3h=round(gross_flow_m3h, 3),
            net_flow_m3h=round(net_flow_m3h, 3),
            backwash_loss_m3h=round(total_backwash_loss_m3h, 3),
            recovery_pct=round(gross_recovery_pct, 2),
            net_recovery_pct=round(net_recovery_pct, 2),
            tmp_bar=round(tmp_bar, 3),
            ndp_bar=round(tmp_bar, 3),
            p_in_bar=round(p_in, 3),
            p_out_bar=round(p_out, 3),
            dp_bar=round(header_loss, 3),
            sec_kwhm3=round(sec, 4),
            Qf=round(raw_intake_m3h, 6),
            Qp=round(net_flow_m3h, 6),
            Qc=round(total_waste_m3h, 6),
            Cf=round(cf_tds, 6),
            Cp=round(cf_tds, 6),
            Cc=round(cf_tds, 6),
            chemistry=chem,
        )
