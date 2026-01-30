# app\services\simulation\modules\mf.py
from app.services.simulation.modules.base import SimulationModule
from app.api.v1.schemas import StageConfig, FeedInput, StageMetric, ModuleType


class MFModule(SimulationModule):
    """
    [MF 모듈]
    - UF와 유사하나 더 큰 기공(Pore Size)을 가짐
    - 더 높은 투수율(Permeability) 및 Flux 특성 반영
    - 염 제거율 0% (SS, 박테리아 제거용)
    """

    def compute(self, config: StageConfig, feed: FeedInput) -> StageMetric:
        # 1. 입력 파라미터 (MF 특화 기본값 적용)
        feed_flow = feed.flow_m3h
        # MF는 보통 모듈당 면적이 큽니다 (기본값 60m2 가정)
        total_area = config.elements * (config.membrane_area_m2 or 60.0)

        # 운전 Flux (설정값 없으면 80 LMH, 역세척은 2배)
        flux_lmh = config.flux_lmh or 80.0
        bw_flux_lmh = config.backwash_flux_lmh or (flux_lmh * 2.0)

        # 주기 설정
        filt_min = config.filtration_cycle_min or 20.0
        bw_sec = config.backwash_duration_sec or 60.0

        # 유지관리 손실 계수 (CIP, CEB 등을 포괄적으로 2%로 가정)
        # 더 정밀한 계산이 필요하면 UFModule처럼 일별 시간을 계산할 수도 있으나,
        # 여기서는 StageMetric 스키마에 맞춰 핵심 결과만 산출합니다.
        cip_loss_factor = 0.98

        # 2. 시간 밸런스 (Cycle Analysis)
        cycle_time_min = filt_min + (bw_sec / 60.0)
        cycles_per_hour = 60.0 / cycle_time_min

        filt_time_per_hour_min = cycles_per_hour * filt_min
        bw_time_per_hour_min = cycles_per_hour * (bw_sec / 60.0)

        # 3. 물량 밸런스 (Mass Balance)
        gross_prod_m3h = (flux_lmh * total_area) / 1000.0

        # [Reality Check] Feed Flow보다 많이 생산할 수 없음
        if gross_prod_m3h > feed_flow:
            gross_prod_m3h = feed_flow
            # 실제 가능한 Flux로 역산
            flux_lmh = (gross_prod_m3h * 1000.0) / total_area

        # 역세척 소모량
        bw_flow_rate_m3h = (bw_flux_lmh * total_area) / 1000.0
        bw_loss_m3h = bw_flow_rate_m3h * (bw_time_per_hour_min / 60.0)

        # 순 생산량 (Net Production)
        net_prod_m3h = (
            gross_prod_m3h * (filt_time_per_hour_min / 60.0) - bw_loss_m3h
        ) * cip_loss_factor

        if net_prod_m3h < 0:
            net_prod_m3h = 0.0

        # 회수율 (Recovery)
        recovery_pct = (net_prod_m3h / feed_flow) * 100.0 if feed_flow > 0 else 0.0

        # 4. 압력 계산 (TMP)
        # MF는 투수율이 매우 높음 (Permeability: 500 LMH/bar @ 25C)
        temp_corr = 1.0 + 0.025 * (feed.temperature_C - 25.0)
        permeability_25c = 500.0
        permeability_corr = permeability_25c * temp_corr

        tmp_bar = flux_lmh / permeability_corr

        # P_in = P_out + TMP
        p_out = 0.5
        p_in = p_out + tmp_bar

        # 5. 결과 반환
        return StageMetric(
            stage=1,
            module_type=ModuleType.MF,
            # KPI
            recovery_pct=round(recovery_pct, 2),
            flux_lmh=round(flux_lmh, 1),
            ndp_bar=round(tmp_bar, 2),  # TMP
            sec_kwhm3=0.04,  # 초저압 운전
            # Pressures
            p_in_bar=round(p_in, 2),
            p_out_bar=p_out,
            # Mass Balance
            Qf=feed_flow,
            Qp=net_prod_m3h,
            Qc=feed_flow - net_prod_m3h,
            # Chemistry (제거 없음)
            Cf=feed.tds_mgL,
            Cp=feed.tds_mgL,
            Cc=feed.tds_mgL,
        )
