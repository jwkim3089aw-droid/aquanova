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

# Modules
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
        # [Strategy Pattern] 모듈 핸들러 매핑
        self.modules = {
            ModuleType.RO: ROModule(),
            ModuleType.HRRO: HRROModule(),
            ModuleType.NF: NFModule(),
            ModuleType.UF: UFModule(),
            ModuleType.MF: MFModule(),
        }

    def run(self, request: SimulationRequest) -> ScenarioOutput:
        """
        시뮬레이션 전체 실행 및 결과 집계 (Orchestrator)
        """

        # 1. 초기 상태 설정
        current_feed = request.feed
        stage_metrics: List[StageMetric] = []

        total_power_kw = 0.0
        total_product_flow = 0.0  # 단순 합산용 (RO/NF)

        # KPI 가중 평균용 변수
        weighted_flux_sum = 0.0
        weighted_ndp_sum = 0.0

        # 시스템에 HRRO가 포함되어 있는지 확인 (후처리 보정용)
        has_hrro = False
        hrro_recovery_val = 0.0

        # -----------------------------------------------------
        # 2. 스테이지 순차 실행 (Chaining Loop)
        # -----------------------------------------------------
        for idx, stage_conf in enumerate(request.stages):
            # (A) 모듈 핸들러 선택
            module_type = stage_conf.module_type
            handler = self.modules.get(module_type)

            if not handler:
                logger.warning(f"Unknown module type '{module_type}', fallback to RO.")
                handler = self.modules[ModuleType.RO]

            if module_type == ModuleType.HRRO:
                has_hrro = True

            # (B) 물리 연산 실행 (Compute)
            metric = handler.compute(stage_conf, current_feed)

            # (C) 메타데이터 주입
            metric.stage = idx + 1
            stage_metrics.append(metric)

            # (D) KPI 누적
            power_kw = self._calc_power(metric.Qf, metric.p_in_bar)
            total_power_kw += power_kw

            # (E) 유량 흐름 연결 (Mass Balance)
            if module_type in [ModuleType.UF, ModuleType.MF]:
                # 전처리(UF/MF): 생산수가 다음 단계 Feed가 됨
                next_flow = metric.Qp
                next_tds = metric.Cp
            else:
                # 농축(RO/NF/HRRO): 농축수(Brine)가 다음 단계 Feed가 됨
                next_flow = metric.Qc
                next_tds = metric.Cc

                # 제품수(Product) 누적
                total_product_flow += metric.Qp

                # 평균 Flux/NDP 계산을 위한 가중치 합산
                if metric.flux_lmh and metric.Qp > 0:
                    weighted_flux_sum += metric.flux_lmh * metric.Qp
                if metric.ndp_bar and metric.Qp > 0:
                    weighted_ndp_sum += metric.ndp_bar * metric.Qp

            # HRRO인 경우, 모듈이 계산한 '진짜 회수율'을 저장해둠
            if module_type == ModuleType.HRRO:
                hrro_recovery_val = metric.recovery_pct or 0.0

            # Feed 업데이트 (Chaining)
            current_feed = FeedInput(
                flow_m3h=next_flow,
                tds_mgL=next_tds,
                temperature_C=current_feed.temperature_C,
                ph=current_feed.ph,
            )

        # -----------------------------------------------------
        # 3. 전체 시스템 KPI 집계 (The Fix for 110%)
        # -----------------------------------------------------
        feed_flow = request.feed.flow_m3h

        # 기본 계산 (Continuous Process)
        sys_recovery = (total_product_flow / feed_flow * 100) if feed_flow > 0 else 0.0

        # ✅ [CRITICAL FIX] HRRO 110% 버그 수정
        # HRRO는 순간 유량(Qp)이 공급 유량보다 클 수 있으므로, 단순 나눗셈을 하면 100%를 초과함.
        # 따라서 HRRO 모듈이 정확하게 계산해준 'Batch Recovery' 값을 최종 시스템 회수율로 덮어씌움.
        if has_hrro and feed_flow > 0:
            # HRRO가 포함된 경우, 시스템 회수율은 HRRO의 배치 회수율을 따름 (단일단 가정)
            sys_recovery = hrro_recovery_val

            # 110% 오해를 막기 위해, '평균 생산 유량'도 회수율에 맞춰 재계산하여 표시
            # (표시되는 유량 = Feed * 정확한회수율)
            total_product_flow = feed_flow * (sys_recovery / 100.0)

        # 나머지 KPI 계산
        sys_sec = (
            (total_power_kw / total_product_flow) if total_product_flow > 0 else 0.0
        )

        avg_flux = (
            (weighted_flux_sum / total_product_flow) if total_product_flow > 0 else 0.0
        )
        # HRRO는 모듈에서 평균 Flux를 이미 잘 계산했으므로 그대로 사용 가능
        if has_hrro and stage_metrics:
            avg_flux = stage_metrics[0].flux_lmh or avg_flux

        avg_ndp = (
            (weighted_ndp_sum / total_product_flow) if total_product_flow > 0 else 0.0
        )

        # 최종 생산수 수질 (마지막 스테이지 기준)
        final_permeate_tds = stage_metrics[-1].Cp if stage_metrics else 0.0

        final_kpi = KPIOut(
            recovery_pct=round(sys_recovery, 2),  # ✅ 이제 60.98%가 들어갑니다.
            flux_lmh=round(avg_flux, 1),
            ndp_bar=round(avg_ndp, 2),
            sec_kwhm3=round(sys_sec, 3),
            feed_m3h=feed_flow,
            permeate_m3h=round(
                total_product_flow, 2
            ),  # ✅ 유량도 22m3/h가 아닌 ~12m3/h(평균)로 교정됨
            prod_tds=round(final_permeate_tds, 2),
        )

        # -----------------------------------------------------
        # 4. 결과 패키징 및 반환
        # -----------------------------------------------------
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
                    flow_m3h=total_product_flow,  # 보정된 평균 유량 사용
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
            # HRRO 시계열 데이터 추출
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
        """화학적 스케일 지수 계산"""
        if HAS_CHEMISTRY:
            try:
                prof = ChemistryProfile(
                    tds_mgL=feed.tds_mgL, temperature_C=feed.temperature_C, ph=feed.ph
                )
                return WaterChemistryOut(feed=calc_scaling_indices(prof))
            except Exception:
                return None
        return None
