# app\services\simulation\modules\uf.py
from app.services.simulation.modules.base import SimulationModule
from app.api.v1.schemas import StageConfig, FeedInput, StageMetric, ModuleType


class UFModule(SimulationModule):
    """
    [UF/MF 통합 모듈]
    - 정주기 역세척(Backwash)을 고려한 Net Recovery 계산
    - 삼투압 무시 (Sieving Model)
    - Darcy's Law 기반 TMP 계산
    """

    def compute(self, config: StageConfig, feed: FeedInput) -> StageMetric:
        # 1. 입력 파라미터 및 기본값 설정
        feed_flow = feed.flow_m3h
        total_area = config.elements * (config.membrane_area_m2 or 50.0)

        # 운전 Flux (설정값 없으면 60 LMH 가정)
        flux_lmh = config.flux_lmh or 60.0
        bw_flux_lmh = config.backwash_flux_lmh or (flux_lmh * 1.5)

        # 주기 설정
        filt_min = config.filtration_cycle_min or 30.0
        bw_sec = config.backwash_duration_sec or 60.0

        # 기타 손실 (CEB, CIP 등은 하루 기준 평균 손실로 약식 반영)
        cip_loss_factor = 0.98  # CIP 등으로 인한 가동률 저하 (2% 가정)

        # 2. 시간 밸런스 (Cycle Analysis)
        cycle_time_min = filt_min + (bw_sec / 60.0)
        cycles_per_hour = 60.0 / cycle_time_min

        # 시간당 여과 시간(분) 및 역세 시간(분)
        filt_time_per_hour_min = cycles_per_hour * filt_min
        bw_time_per_hour_min = cycles_per_hour * (bw_sec / 60.0)

        # 3. 물량 밸런스 (Mass Balance)
        # 총 생산량 (Gross)
        gross_prod_m3h = (flux_lmh * total_area) / 1000.0

        # 현실적인 공급량 제한 (공급량보다 더 생산할 순 없음)
        if gross_prod_m3h > feed_flow:
            gross_prod_m3h = feed_flow
            flux_lmh = (gross_prod_m3h * 1000.0) / total_area

        # 역세척 소모량
        bw_flow_rate_m3h = (bw_flux_lmh * total_area) / 1000.0
        bw_loss_m3h = bw_flow_rate_m3h * (bw_time_per_hour_min / 60.0)

        # 순 생산량 (Net Production)
        # 가동률(CIP Loss) 반영
        net_prod_m3h = (
            gross_prod_m3h * (filt_time_per_hour_min / 60.0) - bw_loss_m3h
        ) * cip_loss_factor

        if net_prod_m3h < 0:
            net_prod_m3h = 0.0

        # 회수율 (Recovery)
        # UF는 보통 공급량 기준보다는 Gross 생산량 대비 Net 생산량 비율로 봄 (Process Recovery)
        # 하지만 전체 시스템 관점에서는 Feed 대비 Net이 중요
        recovery_pct = (net_prod_m3h / feed_flow) * 100.0 if feed_flow > 0 else 0.0

        # 4. 압력 계산 (TMP)
        # J = Permeability * TMP  => TMP = J / Permeability
        # 온도 보정: 점성 계수 활용 (간이식: 2.5% per degC)
        temp_corr = 1.0 + 0.025 * (feed.temperature_C - 25.0)
        permeability_25c = 250.0  # LMH/bar (일반적 UF 막)
        permeability_corr = permeability_25c * temp_corr

        tmp_bar = flux_lmh / permeability_corr

        # P_in = P_out + TMP (단순화)
        p_out = 0.5  # 대기압 + 배관손실
        p_in = p_out + tmp_bar

        # 5. 결과 반환
        return StageMetric(
            stage=1,
            module_type=ModuleType.UF,  # or MF
            # KPI
            recovery_pct=round(recovery_pct, 2),
            flux_lmh=round(flux_lmh, 1),
            ndp_bar=round(tmp_bar, 2),  # UF에서는 TMP를 NDP 자리에 매핑
            sec_kwhm3=0.05,  # 저압이라 낮음
            # Pressures
            p_in_bar=round(p_in, 2),
            p_out_bar=p_out,
            # Mass Balance
            Qf=feed_flow,
            Qp=net_prod_m3h,  # 순 생산수
            Qc=feed_flow - net_prod_m3h,  # 폐수 (역세수 등)
            # Chemistry (UF는 염 제거 없음)
            Cf=feed.tds_mgL,
            Cp=feed.tds_mgL,
            Cc=feed.tds_mgL,
        )
