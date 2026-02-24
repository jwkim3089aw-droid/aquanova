# app/services/simulation/engine.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from loguru import logger

# [WAVE MATCHING FIX] app.api.v1.schemas 대신 확장된 최신 스키마를 직접 임포트합니다.
from app.schemas.simulation import (
    FeedInput,
    KPIOut,
    ModuleType,
    ScenarioOutput,
    SimulationRequest,
    StageMetric,
    StreamOut,
    WaterChemistryOut,
    MassBalanceOut,
    SimulationWarning,
)

from app.services.simulation.utils import inject_global_chemistry_into_stages

from app.services.simulation.modules.hrro import HRROModule
from app.services.simulation.modules.mf import MFModule
from app.services.simulation.modules.nf import NFModule
from app.services.simulation.modules.ro import ROModule
from app.services.simulation.modules.uf import UFModule

try:
    from app.services.water_chemistry import (
        calc_scaling_indices,
        ChemistryProfile,
        scale_profile_for_tds,
        apply_balance_makeup,  # 🛑 [WAVE PATCH] 밸런스 메이크업 엔진 임포트
        calculate_ion_balance,  # 🛑 [WAVE PATCH] 이온 밸런스 검증 엔진 임포트
    )

    HAS_CHEMISTRY = True
except ImportError:
    HAS_CHEMISTRY = False


PRESSURE_MEMBRANE_TYPES = {ModuleType.RO, ModuleType.NF, ModuleType.HRRO}


def _f(v: Any, default: float = 0.0) -> float:
    try:
        if v is None:
            return float(default)
        return float(v)
    except Exception:
        return float(default)


def _to_float_opt(v: Any) -> Optional[float]:
    try:
        if v is None:
            return None
        x = float(v)
        return x
    except Exception:
        return None


def _r(v: Any, ndigits: int, default: float = 0.0) -> float:
    """round-safe: None / NaN 같은 입력에서도 절대 터지지 않게."""
    x = _f(v, default)
    try:
        return round(x, ndigits)
    except Exception:
        return round(float(default), ndigits)


# =============================================================================
# stream resolver (module-type based SSOT + chemistry override)
# =============================================================================
@dataclass(frozen=True)
class _ResolvedStream:
    flow_m3h: float
    tds_mgL: Optional[float]


def _get_chem_dict(metric: StageMetric) -> Optional[Dict[str, Any]]:
    chem = getattr(metric, "chemistry", None)
    return chem if isinstance(chem, dict) else None


def _chem_stream_override(
    metric: StageMetric, kind: str
) -> Tuple[Optional[float], Optional[float]]:
    chem = _get_chem_dict(metric)
    if not chem:
        return None, None

    k = (kind or "").strip().lower()

    streams = chem.get("streams")
    if isinstance(streams, dict):
        if k == "permeate":
            keys = ("permeate", "product")
        elif k == "concentrate":
            keys = ("concentrate", "brine")
        else:
            keys = ("feed",)

        for kk in keys:
            node = streams.get(kk)
            if isinstance(node, dict):
                flow_v = _to_float_opt(node.get("flow_m3h"))
                tds_v = _to_float_opt(node.get("tds_mgL"))
                if flow_v is not None or tds_v is not None:
                    return flow_v, tds_v

    flow_key = f"{k}_flow_m3h"
    tds_key = f"{k}_tds_mgL"
    flow_v = _to_float_opt(chem.get(flow_key))
    tds_v = _to_float_opt(chem.get(tds_key))
    if flow_v is not None or tds_v is not None:
        return flow_v, tds_v

    if k == "permeate":
        flow_v, tds_v = None, None
        for fk in ("permeate_flow_m3h", "product_flow_m3h"):
            v = _to_float_opt(chem.get(fk))
            if v is not None:
                flow_v = v
                break
        for ck in ("permeate_tds_mgL", "product_tds_mgL"):
            v = _to_float_opt(chem.get(ck))
            if v is not None:
                tds_v = v
                break
        if flow_v is not None or tds_v is not None:
            return flow_v, tds_v

    if k == "concentrate":
        flow_v, tds_v = None, None
        for fk in ("concentrate_flow_m3h", "brine_flow_m3h"):
            v = _to_float_opt(chem.get(fk))
            if v is not None:
                flow_v = v
                break
        for ck in ("concentrate_tds_mgL", "brine_tds_mgL"):
            v = _to_float_opt(chem.get(ck))
            if v is not None:
                tds_v = v
                break
        if flow_v is not None or tds_v is not None:
            return flow_v, tds_v

    return None, None


def _stream_from_metric(metric: StageMetric, kind: str) -> _ResolvedStream:
    k = (kind or "").strip().lower()
    o_flow, o_tds = _chem_stream_override(metric, k)

    if k == "permeate":
        flow = _f(o_flow, _f(getattr(metric, "Qp", None)))
        tds = o_tds if o_tds is not None else getattr(metric, "Cp", None)
        return _ResolvedStream(flow_m3h=flow, tds_mgL=tds)

    if k == "feed":
        flow = _f(o_flow, _f(getattr(metric, "Qf", None)))
        tds = o_tds if o_tds is not None else getattr(metric, "Cf", None)
        return _ResolvedStream(flow_m3h=flow, tds_mgL=tds)

    flow = _f(o_flow, _f(getattr(metric, "Qc", None)))
    tds = o_tds if o_tds is not None else getattr(metric, "Cc", None)
    return _ResolvedStream(flow_m3h=flow, tds_mgL=tds)


# -------------------------
# SSOT maps
# -------------------------
NEXT_FEED_STREAM_KIND: Dict[ModuleType, str] = {
    ModuleType.UF: "permeate",
    ModuleType.MF: "permeate",
    ModuleType.RO: "concentrate",
    ModuleType.NF: "concentrate",
    ModuleType.HRRO: "concentrate",
}

PRODUCT_EXPORT_STREAM_KIND: Dict[ModuleType, str] = {
    ModuleType.RO: "permeate",
    ModuleType.NF: "permeate",
    ModuleType.HRRO: "permeate",
    ModuleType.UF: "permeate",
    ModuleType.MF: "permeate",
}

BRINE_STREAM_KIND: Dict[ModuleType, str] = {
    ModuleType.RO: "concentrate",
    ModuleType.NF: "concentrate",
    ModuleType.HRRO: "concentrate",
    ModuleType.UF: "concentrate",
    ModuleType.MF: "concentrate",
}


class SimulationEngine:
    def __init__(self) -> None:
        self.modules = {
            ModuleType.RO: ROModule(),
            ModuleType.HRRO: HRROModule(),
            ModuleType.NF: NFModule(),
            ModuleType.UF: UFModule(),
            ModuleType.MF: MFModule(),
        }

    def run(self, request: SimulationRequest) -> ScenarioOutput:
        request = inject_global_chemistry_into_stages(request)

        if not request.stages:
            logger.warning("No stages provided. Returning empty scenario.")
            return ScenarioOutput(
                scenario_id=request.simulation_id or str(UUID(int=0)),
                streams=[],
                kpi=KPIOut(
                    recovery_pct=0.0,
                    flux_lmh=0.0,
                    ndp_bar=0.0,
                    sec_kwhm3=0.0,
                    feed_m3h=_f(request.feed.flow_m3h),
                    permeate_m3h=0.0,
                    prod_tds=0.0,
                ),
            )

        # 🛑 [WAVE PATCH] 0. 이온 밸런스 검사 및 자동 보정 (Make-up) 최우선 실행!
        # 여기서 보정된 TDS와 이온 농도가 이후 모든 물리 엔진(삼투압 계산 등)에 쓰입니다.
        if HAS_CHEMISTRY and getattr(request.feed, "ions", None):
            raw_prof = self._build_base_chem_profile(request.feed)
            if raw_prof:
                # 밸런스 자동 보정 적용 (양이온/음이온 부족분 채우기)
                balanced_prof = apply_balance_makeup(raw_prof)

                # 보정된 TDS 및 Na, Cl 데이터를 FeedInput 원본에 덮어쓰기! (엔진 전체에 전파됨)
                request.feed.tds_mgL = balanced_prof.tds_mgL
                request.feed.ions.Na = balanced_prof.na_mgL
                request.feed.ions.Cl = balanced_prof.cl_mgL

                # (선택) 로깅으로 밸런스 보정 결과 남기기
                _, _, err_pct = calculate_ion_balance(raw_prof)
                if err_pct > 1e-4:
                    logger.info(
                        f"[WAVE] Feed Ion Balance adjusted. Initial Error: {err_pct:.2f}%. Updated TDS: {balanced_prof.tds_mgL:.2f} mg/L"
                    )

        current_feed: FeedInput = request.feed
        stage_metrics: List[StageMetric] = []
        stage_types: List[ModuleType] = []
        resolved_streams: List[Dict[str, _ResolvedStream]] = []

        total_power_kw = 0.0

        for idx, stage_conf in enumerate(request.stages):
            module_type: ModuleType = stage_conf.module_type
            handler = self.modules.get(module_type)

            if not handler:
                handler = self.modules[ModuleType.RO]
                module_type = ModuleType.RO

            metric: StageMetric = handler.compute(stage_conf, current_feed)
            metric.stage = idx + 1

            stage_metrics.append(metric)
            stage_types.append(module_type)

            total_power_kw += self._calc_power(
                _f(getattr(metric, "Qf", None)), _f(getattr(metric, "p_in_bar", None))
            )

            cache = {
                "feed": _stream_from_metric(metric, "feed"),
                "permeate": _stream_from_metric(metric, "permeate"),
                "concentrate": _stream_from_metric(metric, "concentrate"),
            }
            resolved_streams.append(cache)

            kind = NEXT_FEED_STREAM_KIND.get(module_type, "concentrate")
            s = cache.get(kind) or cache["concentrate"]
            next_flow, next_tds = s.flow_m3h, s.tds_mgL

            if next_tds is None:
                next_tds = _f(getattr(current_feed, "tds_mgL", None))

            current_feed = FeedInput(
                flow_m3h=_f(next_flow),
                tds_mgL=_f(next_tds),
                temperature_C=_f(getattr(current_feed, "temperature_C", None)),
                ph=_f(getattr(current_feed, "ph", None)),
                pressure_bar=_f(getattr(current_feed, "pressure_bar", None)),
                chemistry=getattr(current_feed, "chemistry", None),
                # 다음 스테이지로 넘어갈 땐 현재 시뮬레이션에서는 이온 상세 구성까지는 넘기지 않음 (기존 구조 유지)
            )

        # ---------------------------------------------------------
        # 1. System Aggregates & Balances
        # ---------------------------------------------------------
        feed_flow = _f(request.feed.flow_m3h)
        feed_tds = _f(request.feed.tds_mgL)

        prod_flow, prod_tds, avg_flux, avg_ndp = self._aggregate_system_product(
            stage_types=stage_types,
            stage_metrics=stage_metrics,
            resolved_streams=resolved_streams,
            feed=request.feed,
        )

        sys_recovery = (prod_flow / feed_flow * 100.0) if feed_flow > 0 else 0.0

        sys_sec = 0.0
        if len(stage_metrics) == 1 and stage_types[0] == ModuleType.HRRO:
            sys_sec = _f(getattr(stage_metrics[0], "sec_kwhm3", None))
        else:
            sys_sec = (total_power_kw / prod_flow) if prod_flow > 1e-12 else 0.0

        last_type = stage_types[-1]
        last_cache = resolved_streams[-1]
        br_kind = BRINE_STREAM_KIND.get(last_type, "concentrate")
        br_s = last_cache.get(br_kind) or last_cache["concentrate"]
        brine_flow = _f(br_s.flow_m3h, 0.0)
        brine_tds = _f(br_s.tds_mgL, _f(getattr(current_feed, "tds_mgL", None)))

        batchcycle = None
        for st in reversed(request.stages or []):
            if getattr(st, "module_type", None) in (ModuleType.UF, ModuleType.MF):
                batchcycle = _to_float_opt(getattr(st, "filtration_cycle_min", None))
                break

        # [WAVE FIX] Mass Balance (Flow Closure / Salt Closure)
        mass_balance = self._calc_mass_balance(
            feed_flow, feed_tds, prod_flow, prod_tds, brine_flow, brine_tds
        )

        final_kpi = KPIOut(
            recovery_pct=_r(sys_recovery, 2),
            flux_lmh=_r(avg_flux, 1),
            ndp_bar=_r(avg_ndp, 2),
            sec_kwhm3=_r(sys_sec, 3),
            prod_tds=_r(prod_tds, 2),
            feed_m3h=feed_flow,
            permeate_m3h=_r(prod_flow, 6),
            batchcycle=batchcycle,
            mass_balance=mass_balance,
        )

        streams = [
            StreamOut(
                label="Feed",
                flow_m3h=feed_flow,
                tds_mgL=feed_tds,
                ph=_f(request.feed.ph),
                pressure_bar=_f(getattr(request.feed, "pressure_bar", 0.0)),
            ),
            StreamOut(
                label="Product",
                flow_m3h=_r(prod_flow, 2),
                tds_mgL=_r(prod_tds, 2),
                ph=_f(request.feed.ph),
                pressure_bar=0.0,
            ),
            StreamOut(
                label="Brine",
                flow_m3h=_r(brine_flow, 2),
                tds_mgL=_r(brine_tds, 2),
                ph=_f(request.feed.ph),
                pressure_bar=0.0,
            ),
        ]

        # ---------------------------------------------------------
        # 2. Extract System Warnings
        # ---------------------------------------------------------
        system_warnings = self._extract_warnings(stage_metrics)

        # ---------------------------------------------------------
        # 3. Calculate Advanced Chemistry (Scaling for Brine)
        # ---------------------------------------------------------
        sys_chemistry = self._calc_system_chemistry(request, brine_tds)

        return ScenarioOutput(
            scenario_id=request.simulation_id or str(UUID(int=0)),
            streams=streams,
            kpi=final_kpi,
            stage_metrics=stage_metrics,
            time_history=next(
                (m.time_history for m in stage_metrics if m.time_history), None
            ),
            chemistry=sys_chemistry,
            warnings=system_warnings,
        )

    # =========================================================================
    # Helpers
    # =========================================================================
    def _calc_mass_balance(
        self, qf: float, cf: float, qp: float, cp: float, qb: float, cb: float
    ) -> MassBalanceOut:
        """WAVE 리포트의 FLOW CLOSURE 및 SALT CLOSURE 블록 생성"""
        flow_err = qf - (qp + qb)
        # (m3/h * mg/L) = (g/h). To get kg/h, divide by 1000.
        salt_err_g = (qf * cf) - ((qp * cp) + (qb * cb))

        flow_err_pct = (flow_err / qf * 100.0) if qf > 0 else 0.0
        salt_err_pct = (salt_err_g / (qf * cf) * 100.0) if (qf * cf) > 0 else 0.0
        rej = ((1.0 - cp / cf) * 100.0) if cf > 0 else 0.0

        return MassBalanceOut(
            flow_error_m3h=round(flow_err, 4),
            flow_error_pct=round(flow_err_pct, 2),
            salt_error_kgh=round(salt_err_g / 1000.0, 4),
            salt_error_pct=round(salt_err_pct, 2),
            system_rejection_pct=round(rej, 2),
            is_balanced=abs(flow_err_pct) < 1.0 and abs(salt_err_pct) < 5.0,
        )

    def _extract_warnings(self, metrics: List[StageMetric]) -> List[SimulationWarning]:
        """각 스테이지의 Chemistry/가이드라인 위반 사항을 System Warning으로 롤업"""
        warnings = []
        for m in metrics:
            chem = _get_chem_dict(m)
            if chem and "violations" in chem:
                for v in chem["violations"]:
                    warnings.append(
                        SimulationWarning(
                            stage=f"Stage {m.stage}",
                            module_type=m.module_type,
                            key=v.get("key", "unknown"),
                            message=v.get("message", ""),
                            value=v.get("value"),
                            limit=v.get("limit"),
                            unit=v.get("unit", ""),
                        )
                    )
        return warnings

    # 🛑 [WAVE PATCH] 새로운 스키마 구조(feed.ions)에 맞게 파라미터 단순화
    def _build_base_chem_profile(self, feed: FeedInput) -> Any:
        if not HAS_CHEMISTRY:
            return None
        prof = ChemistryProfile(
            tds_mgL=_f(feed.tds_mgL),
            temperature_C=_f(feed.temperature_C),
            ph=_f(feed.ph),
        )

        ions = getattr(feed, "ions", None)
        if ions:
            prof.na_mgL = _to_float_opt(getattr(ions, "Na", None))
            prof.k_mgL = _to_float_opt(getattr(ions, "K", None))
            prof.ca_mgL = _to_float_opt(getattr(ions, "Ca", None))
            prof.mg_mgL = _to_float_opt(getattr(ions, "Mg", None))
            prof.nh4_mgL = _to_float_opt(getattr(ions, "NH4", None))
            prof.ba_mgL = _to_float_opt(getattr(ions, "Ba", None))
            prof.sr_mgL = _to_float_opt(getattr(ions, "Sr", None))
            prof.fe_mgL = _to_float_opt(getattr(ions, "Fe", None))
            prof.mn_mgL = _to_float_opt(getattr(ions, "Mn", None))
            prof.al_mgL = _to_float_opt(getattr(ions, "Al", None))

            prof.cl_mgL = _to_float_opt(getattr(ions, "Cl", None))
            prof.so4_mgL = _to_float_opt(getattr(ions, "SO4", None))
            prof.hco3_mgL = _to_float_opt(getattr(ions, "HCO3", None))
            prof.no3_mgL = _to_float_opt(getattr(ions, "NO3", None))
            prof.f_mgL = _to_float_opt(getattr(ions, "F", None))

            prof.sio2_mgL = _to_float_opt(getattr(ions, "SiO2", None))
            prof.b_mgL = _to_float_opt(getattr(ions, "B", None))
        return prof

    def _calc_system_chemistry(
        self, request: SimulationRequest, final_brine_tds: float
    ) -> Optional[WaterChemistryOut]:
        """Feed 이온 데이터를 바탕으로 Feed 및 Final Brine의 스케일링 지수를 예측합니다."""
        if not HAS_CHEMISTRY:
            return None
        try:
            # 보정된 request.feed 데이터를 그대로 넘깁니다.
            feed_prof = self._build_base_chem_profile(request.feed)

            # 1. Feed 원수 스케일링
            feed_scaling = calc_scaling_indices(feed_prof)

            # 2. Final Brine 농축수 스케일링 (WAVE 리포트 핵심 파트)
            # Brine TDS에 맞춰 Feed의 모든 이온을 비례 농축시킵니다.
            brine_prof = scale_profile_for_tds(feed_prof, final_brine_tds)
            brine_scaling = calc_scaling_indices(brine_prof)

            return WaterChemistryOut(feed=feed_scaling, final_brine=brine_scaling)
        except Exception as e:
            logger.error(f"Failed to calculate system chemistry: {e}")
            return None

    def _aggregate_system_product(
        self,
        *,
        stage_types: List[ModuleType],
        stage_metrics: List[StageMetric],
        resolved_streams: List[Dict[str, _ResolvedStream]],
        feed: FeedInput,
    ) -> Tuple[float, float, float, float]:
        if not stage_metrics:
            return 0.0, 0.0, 0.0, 0.0

        pressure_idxs = [
            i for i, t in enumerate(stage_types) if t in PRESSURE_MEMBRANE_TYPES
        ]
        has_pressure = len(pressure_idxs) > 0

        if has_pressure:
            prod_flow, tds_w_sum, tds_w_flow = 0.0, 0.0, 0.0
            flux_w_sum, flux_w_flow = 0.0, 0.0
            ndp_w_sum, ndp_w_flow = 0.0, 0.0

            for i in pressure_idxs:
                t = stage_types[i]
                m = stage_metrics[i]
                cache = resolved_streams[i]

                kind = PRODUCT_EXPORT_STREAM_KIND.get(t, "permeate")
                s = cache.get(kind) or cache["permeate"]

                q = _f(s.flow_m3h, 0.0)
                prod_flow += q

                if s.tds_mgL is not None:
                    tds_w_sum += q * _f(s.tds_mgL, 0.0)
                    tds_w_flow += q

                if getattr(m, "flux_lmh", None) is not None:
                    flux_w_sum += q * _f(m.flux_lmh, 0.0)
                    flux_w_flow += q

                if getattr(m, "ndp_bar", None) is not None:
                    ndp_w_sum += q * _f(m.ndp_bar, 0.0)
                    ndp_w_flow += q

            prod_tds = (tds_w_sum / tds_w_flow) if tds_w_flow > 1e-12 else 0.0
            avg_flux = (flux_w_sum / flux_w_flow) if flux_w_flow > 1e-12 else 0.0
            avg_ndp = (ndp_w_sum / ndp_w_flow) if ndp_w_flow > 1e-12 else 0.0
            return prod_flow, prod_tds, avg_flux, avg_ndp

        # UF/MF only
        last_t = stage_types[-1]
        last_m = stage_metrics[-1]
        last_cache = resolved_streams[-1]

        kind = PRODUCT_EXPORT_STREAM_KIND.get(last_t, "permeate")
        s = last_cache.get(kind) or last_cache["permeate"]

        prod_flow = _f(s.flow_m3h, 0.0)
        prod_tds = _f(s.tds_mgL, _f(feed.tds_mgL, 0.0))
        avg_flux = _f(getattr(last_m, "flux_lmh", None), 0.0)
        avg_ndp = _f(getattr(last_m, "ndp_bar", None), 0.0)
        return prod_flow, prod_tds, avg_flux, avg_ndp

    def _calc_power(
        self, flow_m3h: float, pressure_bar: float, eff: float = 0.8
    ) -> float:
        q = _f(flow_m3h)
        p = _f(pressure_bar)
        e = _f(eff, 0.8)
        if q <= 0 or p <= 0 or e <= 1e-9:
            return 0.0
        return (q * p) / 36.0 / e
