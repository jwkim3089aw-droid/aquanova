# app/services/simulation/engine.py
from typing import List, Optional
from uuid import UUID

from loguru import logger

# Schemas
from app.api.v1.schemas import (
    SimulationRequest,
    ScenarioOutput,
    StageConfig,
    StageMetric,
    FeedInput,
    StreamOut,
    KPIOut,
    ModuleType,
    WaterChemistryOut,
)

# Modules (우리가 만든 정석 모듈들)
from app.services.simulation.modules.ro import ROModule
from app.services.simulation.modules.hrro import HRROModule
from app.services.simulation.modules.nf import NFModule
from app.services.simulation.modules.uf import UFModule
from app.services.simulation.modules.mf import MFModule

# Chemistry Helper
try:
    from app.services.water_chemistry import calc_scaling_indices, ChemistryProfile

    HAS_CHEMISTRY = True
except ImportError:
    HAS_CHEMISTRY = False


class SimulationEngine:
    def __init__(self):
        # [Strategy Pattern] 모듈 타입별 처리기 등록
        self.modules = {
            ModuleType.RO: ROModule(),
            ModuleType.HRRO: HRROModule(),
            ModuleType.NF: NFModule(),
            ModuleType.UF: UFModule(),
            ModuleType.MF: MFModule(),
        }

    def run(self, request: SimulationRequest) -> ScenarioOutput:
        """시뮬레이션 전체 실행 및 결과 집계"""

        # 1. 초기 상태 설정
        current_feed = request.feed
        stage_metrics: List[StageMetric] = []

        total_power_kw = 0.0
        total_product_flow = 0.0

        # KPI 집계용 변수
        weighted_flux_sum = 0.0
        weighted_ndp_sum = 0.0
        total_membrane_area = 0.0

        # 2. 스테이지 순차 실행 (Chaining)
        for idx, stage_conf in enumerate(request.stages):
            # (1) 모듈 선택
            module_type = stage_conf.module_type
            handler = self.modules.get(module_type)

            if not handler:
                # 안전장치: 등록되지 않은 모듈은 RO로 처리
                logger.warning(f"Unknown module type '{module_type}', fallback to RO.")
                handler = self.modules[ModuleType.RO]

            # (2) 계산 실행 (Compute)
            # 복잡한 로직은 handler 내부로 숨겨짐
            metric = handler.compute(stage_conf, current_feed)

            # (3) 메타데이터 주입
            metric.stage = idx + 1
            stage_metrics.append(metric)

            # (4) KPI 누적 계산
            power_kw = self._calc_power(metric.Qf, metric.p_in_bar)
            total_power_kw += power_kw

            # (5) 다음 스테이지 연결 로직 (Flow Connection)
            # - UF/MF: 여과된 물(Permeate)이 다음 단계로 감 (전처리)
            # - RO/NF: 농축된 물(Brine)이 다음 단계로 감 (다단 농축)
            if module_type in [ModuleType.UF, ModuleType.MF]:
                next_flow = metric.Qp
                next_tds = metric.Cp
                # UF/MF는 생산수가 제품수가 아님 (다음 단계 Feed가 됨)
            else:
                next_flow = metric.Qc
                next_tds = metric.Cc
                # RO/NF/HRRO는 생산수가 제품수(Product)가 됨
                total_product_flow += metric.Qp

                # 평균 KPI 계산용 가중치 합산
                if metric.flux_lmh and metric.Qp > 0:
                    weighted_flux_sum += metric.flux_lmh * metric.Qp
                if metric.ndp_bar and metric.Qp > 0:
                    weighted_ndp_sum += metric.ndp_bar * metric.Qp

            # Feed 업데이트 (다음 루프용)
            current_feed = FeedInput(
                flow_m3h=next_flow,
                tds_mgL=next_tds,
                temperature_C=current_feed.temperature_C,
                ph=current_feed.ph,
            )

        # 3. 전체 시스템 KPI 계산
        feed_flow = request.feed.flow_m3h
        sys_recovery = (total_product_flow / feed_flow * 100) if feed_flow > 0 else 0.0
        sys_sec = (
            (total_power_kw / total_product_flow) if total_product_flow > 0 else 0.0
        )

        avg_flux = (
            (weighted_flux_sum / total_product_flow) if total_product_flow > 0 else 0.0
        )
        avg_ndp = (
            (weighted_ndp_sum / total_product_flow) if total_product_flow > 0 else 0.0
        )

        # 마지막 생산수 수질 (RO/NF/HRRO 중 마지막 단계의 생산수 농도)
        # (실제로는 모든 RO 단계의 혼합수질을 계산해야 하지만 여기선 마지막 값 or 0)
        final_permeate_tds = stage_metrics[-1].Cp if stage_metrics else 0.0

        final_kpi = KPIOut(
            recovery_pct=round(sys_recovery, 2),
            flux_lmh=round(avg_flux, 1),
            ndp_bar=round(avg_ndp, 2),
            sec_kwhm3=round(sys_sec, 3),
            feed_m3h=feed_flow,
            permeate_m3h=round(total_product_flow, 2),
            prod_tds=round(final_permeate_tds, 2),
        )

        # 4. 결과 반환
        return ScenarioOutput(
            scenario_id=request.simulation_id or str(UUID(int=0)),
            streams=[
                StreamOut(
                    label="Feed",
                    flow_m3h=feed_flow,
                    tds_mgL=request.feed.tds_mgL,
                    ph=request.feed.ph,
                    pressure_bar=0,
                ),
                StreamOut(
                    label="Product",
                    flow_m3h=total_product_flow,
                    tds_mgL=final_permeate_tds,
                    ph=7,
                    pressure_bar=0,
                ),
                StreamOut(
                    label="Brine",
                    flow_m3h=current_feed.flow_m3h,
                    tds_mgL=current_feed.tds_mgL,
                    ph=7,
                    pressure_bar=0,
                ),
            ],
            kpi=final_kpi,
            stage_metrics=stage_metrics,
            # HRRO 그래프용 시계열 데이터 (HRRO 모듈이 있으면 가져옴)
            time_history=next(
                (m.time_history for m in stage_metrics if m.time_history), None
            ),
            chemistry=self._get_chemistry(request.feed),
        )

    def _calc_power(
        self, flow_m3h: float, pressure_bar: float, eff: float = 0.8
    ) -> float:
        """펌프 동력 계산 (kW)"""
        return (flow_m3h * pressure_bar) / 36.0 / eff

    def _get_chemistry(self, feed: FeedInput) -> Optional[WaterChemistryOut]:
        """화학적 스케일 지수 계산 (옵션)"""
        if HAS_CHEMISTRY:
            try:
                # 간단한 Dummy Profile 생성 후 계산
                prof = ChemistryProfile(
                    tds_mgL=feed.tds_mgL, temperature_C=feed.temperature_C, ph=feed.ph
                )
                return WaterChemistryOut(feed=calc_scaling_indices(prof))
            except Exception:
                return None
        return None
