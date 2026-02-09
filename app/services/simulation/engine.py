# app/services/simulation/engine.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from loguru import logger

from app.api.v1.schemas import (
    FeedInput,
    KPIOut,
    ModuleType,
    ScenarioOutput,
    SimulationRequest,
    StageMetric,
    StreamOut,
    WaterChemistryOut,
)

from app.services.simulation.utils import inject_global_chemistry_into_stages

from app.services.simulation.modules.hrro import HRROModule
from app.services.simulation.modules.mf import MFModule
from app.services.simulation.modules.nf import NFModule
from app.services.simulation.modules.ro import ROModule
from app.services.simulation.modules.uf import UFModule

try:
    from app.services.water_chemistry import calc_scaling_indices, ChemistryProfile

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
    """
    chemistry 기반으로 stream을 명시할 수 있는 확장 포인트.
    (UF/MF에서 Cp 대신 permeate/product 정의를 명확히 할 때 사용)

    지원 형태(우선순위):
      1) chemistry["streams"][kind]["flow_m3h"|"tds_mgL"]
         - kind 별칭도 지원:
           permeate -> ("permeate","product")
           concentrate -> ("concentrate","brine")
      2) chemistry["<kind>_flow_m3h"], chemistry["<kind>_tds_mgL"]
      3) flat alias: permeate/product/brine 계열 키

    kind: "permeate" | "concentrate" | "feed"
    """
    chem = _get_chem_dict(metric)
    if not chem:
        return None, None

    k = (kind or "").strip().lower()

    # 1) chemistry["streams"] 우선
    streams = chem.get("streams")
    if isinstance(streams, dict):
        # kind aliases in streams
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

    # 2) flat keys
    flow_key = f"{k}_flow_m3h"
    tds_key = f"{k}_tds_mgL"
    flow_v = _to_float_opt(chem.get(flow_key))
    tds_v = _to_float_opt(chem.get(tds_key))
    if flow_v is not None or tds_v is not None:
        return flow_v, tds_v

    # 3) aliases (permeate/product, concentrate/brine)
    if k == "permeate":
        flow_v = None
        tds_v = None
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
        flow_v = None
        tds_v = None
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
    """
    kind: "permeate" | "concentrate" | "feed"
    - 1) chemistry override가 있으면 그걸 최우선 사용 (UF/MF 확장 포인트)
    - 2) 없으면 StageMetric 기본 필드(Qp/Qc/Qf, Cp/Cc/Cf) 사용
    """
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

    # default: concentrate
    flow = _f(o_flow, _f(getattr(metric, "Qc", None)))
    tds = o_tds if o_tds is not None else getattr(metric, "Cc", None)
    return _ResolvedStream(flow_m3h=flow, tds_mgL=tds)


# -------------------------
# SSOT maps
# -------------------------
# 체인 정의: 다음 stage로 무엇을 feed로 넘길지 (SSOT)
NEXT_FEED_STREAM_KIND: Dict[ModuleType, str] = {
    ModuleType.UF: "permeate",
    ModuleType.MF: "permeate",
    # RO/NF/HRRO는 multi-stage RO 관례상 concentrate chaining
    ModuleType.RO: "concentrate",
    ModuleType.NF: "concentrate",
    ModuleType.HRRO: "concentrate",
}

# 시스템 Product(제품수)로 export할 스트림 정의 (SSOT)
PRODUCT_EXPORT_STREAM_KIND: Dict[ModuleType, str] = {
    ModuleType.RO: "permeate",
    ModuleType.NF: "permeate",
    ModuleType.HRRO: "permeate",
    ModuleType.UF: "permeate",
    ModuleType.MF: "permeate",
}

# 시스템 Brine(폐수)로 export할 스트림 정의 (SSOT)
BRINE_STREAM_KIND: Dict[ModuleType, str] = {
    ModuleType.RO: "concentrate",
    ModuleType.NF: "concentrate",
    ModuleType.HRRO: "concentrate",
    ModuleType.UF: "concentrate",
    ModuleType.MF: "concentrate",
}


class SimulationEngine:
    """
    정석 오케스트레이터:
    - stage 순차 실행 + chaining(stream definition; NEXT_FEED_STREAM_KIND)
    - system KPI 집계(prod_tds는 module-type based PRODUCT_EXPORT_STREAM_KIND로 집계)
    - UF/MF product 정의는 chemistry["streams"]["permeate"/"product"] 등을 통해 Cp 없이도 명시 가능
    """

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
                    batchcycle=None,
                    prod_tds=0.0,
                    feed_m3h=_f(request.feed.flow_m3h),
                    permeate_m3h=0.0,
                ),
                stage_metrics=[],
                chemistry=self._get_chemistry(request.feed),
            )

        current_feed: FeedInput = request.feed
        stage_metrics: List[StageMetric] = []
        stage_types: List[ModuleType] = []

        # ✅ stage별 resolved streams 캐시 (feed/permeate/concentrate)
        resolved_streams: List[Dict[str, _ResolvedStream]] = []

        total_power_kw = 0.0

        for idx, stage_conf in enumerate(request.stages):
            module_type: ModuleType = stage_conf.module_type
            handler = self.modules.get(module_type)

            if not handler:
                logger.warning(f"Unknown module type '{module_type}', fallback to RO.")
                handler = self.modules[ModuleType.RO]
                module_type = ModuleType.RO

            if module_type == ModuleType.HRRO and idx != len(request.stages) - 1:
                logger.warning(
                    "HRRO stage is not the last stage. Chaining after HRRO may be physically inconsistent."
                )

            metric: StageMetric = handler.compute(stage_conf, current_feed)
            metric.stage = idx + 1
            stage_metrics.append(metric)
            stage_types.append(module_type)

            total_power_kw += self._calc_power(
                _f(getattr(metric, "Qf", None)), _f(getattr(metric, "p_in_bar", None))
            )

            # ✅ cache resolve once
            cache = {
                "feed": _stream_from_metric(metric, "feed"),
                "permeate": _stream_from_metric(metric, "permeate"),
                "concentrate": _stream_from_metric(metric, "concentrate"),
            }
            resolved_streams.append(cache)

            # chaining
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
                water_type=getattr(current_feed, "water_type", None),
                water_subtype=getattr(current_feed, "water_subtype", None),
                turbidity_ntu=getattr(current_feed, "turbidity_ntu", None),
                tss_mgL=getattr(current_feed, "tss_mgL", None),
                sdi15=getattr(current_feed, "sdi15", None),
                toc_mgL=getattr(current_feed, "toc_mgL", None),
                chemistry=getattr(current_feed, "chemistry", None),
            )

        # system product aggregates
        feed_flow = _f(request.feed.flow_m3h)
        prod_flow, prod_tds, avg_flux, avg_ndp = self._aggregate_system_product(
            stage_types=stage_types,
            stage_metrics=stage_metrics,
            resolved_streams=resolved_streams,
            feed=request.feed,
        )

        sys_recovery = (prod_flow / feed_flow * 100.0) if feed_flow > 0 else 0.0

        # SEC priority
        sys_sec = 0.0
        if len(stage_metrics) == 1 and stage_types[0] == ModuleType.HRRO:
            sys_sec = _f(getattr(stage_metrics[0], "sec_kwhm3", None))
        else:
            sys_sec = (total_power_kw / prod_flow) if prod_flow > 1e-12 else 0.0

        # brine (last stage SSOT)
        last_type = stage_types[-1]
        last_cache = resolved_streams[-1]
        br_kind = BRINE_STREAM_KIND.get(last_type, "concentrate")
        br_s = last_cache.get(br_kind) or last_cache["concentrate"]
        brine_flow = _f(br_s.flow_m3h, 0.0)
        brine_tds = _f(br_s.tds_mgL, _f(getattr(current_feed, "tds_mgL", None)))

        # ---------------------------------------------------------
        # ✅ batchcycle KPI (UF/MF filtration cycle, minutes)
        # - 가장 마지막 UF/MF stage의 filtration_cycle_min을 batchcycle로 export
        # - UF/MF가 없으면 None
        # ---------------------------------------------------------
        batchcycle = None
        try:
            for st in reversed(request.stages or []):
                if getattr(st, "module_type", None) in (ModuleType.UF, ModuleType.MF):
                    batchcycle = _to_float_opt(
                        getattr(st, "filtration_cycle_min", None)
                    )
                    break
        except Exception:
            batchcycle = None

        final_kpi = KPIOut(
            recovery_pct=_r(sys_recovery, 2),
            flux_lmh=_r(avg_flux, 1),
            ndp_bar=_r(avg_ndp, 2),
            sec_kwhm3=_r(sys_sec, 3),
            prod_tds=_r(prod_tds, 2),
            feed_m3h=feed_flow,
            permeate_m3h=_r(prod_flow, 6),
        )

        streams = [
            StreamOut(
                label="Feed",
                flow_m3h=feed_flow,
                tds_mgL=_f(request.feed.tds_mgL),
                ph=_f(request.feed.ph),
                pressure_bar=_f(getattr(request.feed, "pressure_bar", 0.0)),
            ),
            StreamOut(
                label="Product",
                flow_m3h=_f(prod_flow),
                tds_mgL=_f(prod_tds),
                ph=_f(request.feed.ph),
                pressure_bar=0.0,
            ),
            StreamOut(
                label="Brine",
                flow_m3h=_f(brine_flow),
                tds_mgL=_f(brine_tds),
                ph=_f(request.feed.ph),
                pressure_bar=0.0,
            ),
        ]

        return ScenarioOutput(
            scenario_id=request.simulation_id or str(UUID(int=0)),
            streams=streams,
            kpi=final_kpi,
            stage_metrics=stage_metrics,
            time_history=next(
                (m.time_history for m in stage_metrics if m.time_history), None
            ),
            chemistry=self._get_chemistry(request.feed),
        )

    def _aggregate_system_product(
        self,
        *,
        stage_types: List[ModuleType],
        stage_metrics: List[StageMetric],
        resolved_streams: List[Dict[str, _ResolvedStream]],
        feed: FeedInput,
    ) -> Tuple[float, float, float, float]:
        """
        시스템 Product 정의(정석, 모듈 타입 기반):

        1) pressure membrane(RO/NF/HRRO)가 하나라도 있으면:
           - product = pressure membrane stage들의 export product stream 합
           - prod_tds = Σ(Q*tds)/Σ(Q) (tds=None인 stage는 tds 가중에서 제외)
             * 모든 tds가 None이면 prod_tds=0.0 (HRRO excel_only + cp_mode=none 유지)
           - avg_flux/avg_ndp도 product flow 가중 (값이 None인 stage는 제외)

        2) pressure membrane이 하나도 없으면(UF/MF only):
           - product = 마지막 stage export product stream
           - prod_tds: 해당 stream tds가 None이면 feed.tds로 fallback
        """
        if not stage_metrics:
            return 0.0, 0.0, 0.0, 0.0

        pressure_idxs = [
            i for i, t in enumerate(stage_types) if t in PRESSURE_MEMBRANE_TYPES
        ]
        has_pressure = len(pressure_idxs) > 0

        if has_pressure:
            prod_flow = 0.0

            tds_w_sum = 0.0
            tds_w_flow = 0.0

            flux_w_sum = 0.0
            flux_w_flow = 0.0

            ndp_w_sum = 0.0
            ndp_w_flow = 0.0

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
        """펌프 동력(kW) = (Q[m3/h] * P[bar]) / 36 / eff"""
        q = _f(flow_m3h)
        p = _f(pressure_bar)
        e = _f(eff, 0.8)
        if q <= 0 or p <= 0 or e <= 1e-9:
            return 0.0
        return (q * p) / 36.0 / e

    def _get_chemistry(self, feed: FeedInput) -> Optional[WaterChemistryOut]:
        if not HAS_CHEMISTRY:
            return None
        try:
            prof = ChemistryProfile(
                tds_mgL=_f(feed.tds_mgL),
                temperature_C=_f(feed.temperature_C),
                ph=_f(feed.ph),
            )
            return WaterChemistryOut(feed=calc_scaling_indices(prof))
        except Exception:
            return None
