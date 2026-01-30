# app\services\simulation\modules\nf.py
import math
from typing import Optional

from app.services.simulation.modules.base import SimulationModule
from app.api.v1.schemas import StageConfig, FeedInput, StageMetric, ModuleType

# 상수 정의
P_PERM_BAR = 0.0  # 처리수 배압


class NFModule(SimulationModule):
    """
    [NF 모듈]
    - 나노여과(Nanofiltration)
    - Solution-Diffusion Model과 Rejection Model 혼합 사용
    - 특징: RO 대비 낮은 운전압력, 선택적 이온 제거 (1가 이온 투과 높음)
    """

    def compute(self, config: StageConfig, feed: FeedInput) -> StageMetric:
        # 1. 입력 파라미터 (NF 특화 기본값 적용)
        Qf_m3h = feed.flow_m3h
        Cf_mgL = feed.tds_mgL
        T_C = feed.temperature_C

        elements = config.elements
        area_per_element = config.membrane_area_m2 or 37.0
        total_area = elements * area_per_element

        # NF Membrane Parameters (RO보다 A값 크고 B값 큼)
        A_lmh_bar = config.membrane_A_lmh_bar or 7.0
        # NF는 보통 B값(확산계수)보다는 Rejection(제거율)으로 모델링하는 경우가 많음
        # 하지만 스키마 통일성을 위해 입력값 사용하되, 없으면 Rejection Rate 모델 사용
        rejection_rate = (config.membrane_salt_rejection_pct or 90.0) / 100.0

        p_in_bar = config.pressure_bar or 5.0  # NF는 저압 운전 (기본 5bar)

        dp_module = 0.2
        dp_total = elements * dp_module

        # 2. 반복 계산 (Iterative Calculation)
        avg_pressure = p_in_bar - (dp_total / 2)
        avg_conc = Cf_mgL * 1.1  # 초기 가정

        flux_lmh = 0.0
        permeate_tds = 0.0
        recovery = 0.0

        for _ in range(10):
            # (1) 삼투압 계산 (Van't Hoff)
            # NF는 1가 이온 투과가 많아 유효 삼투압 차이가 RO보다 작음 (Reflection Coefficient < 1)
            # 여기서는 편의상 전체 TDS 기준 삼투압 계산 후 Sigma(반사계수) 적용
            sigma = rejection_rate  # 근사적으로 제거율과 비례

            temp_K = T_C + 273.15
            pi_bulk = (avg_conc / 1000.0) * 0.75 * (temp_K / 298.15)
            pi_effective = pi_bulk * sigma  # 유효 삼투압

            # (2) 유효 구동 압력 (NDP)
            ndp = avg_pressure - P_PERM_BAR - pi_effective
            if ndp < 0.1:
                ndp = 0.1

            # (3) Flux (J = A * NDP)
            flux_lmh = A_lmh_bar * ndp

            # (4) 염 투과 (Cp 계산)
            # 농도분극(CP) 고려
            if flux_lmh > 0:
                cp_factor = math.exp(flux_lmh / 150.0)  # k=150
            else:
                cp_factor = 1.0

            cm = avg_conc * cp_factor

            # [NF 핵심 로직] Cp = Cm * (1 - Rejection)
            # 기존 Strategy 코드의 로직을 그대로 계승
            permeate_tds = cm * (1.0 - rejection_rate)

            # (5) 물질 수지 업데이트
            qp_m3h = (flux_lmh * total_area) / 1000.0

            # Max Recovery Limit (NF는 95%까지 가능)
            if qp_m3h > Qf_m3h * 0.95:
                qp_m3h = Qf_m3h * 0.95
                flux_lmh = (qp_m3h * 1000.0) / total_area

            recovery = qp_m3h / Qf_m3h

            # 평균 농도 재계산
            qc_m3h = Qf_m3h - qp_m3h
            concentrate_tds = (Qf_m3h * Cf_mgL - qp_m3h * permeate_tds) / qc_m3h

            new_avg_conc = (Cf_mgL + concentrate_tds) / 2

            if abs(new_avg_conc - avg_conc) / avg_conc < 0.01:
                avg_conc = new_avg_conc
                break

            avg_conc = new_avg_conc

        # 3. 최종 결과 반환
        qp_m3h = (flux_lmh * total_area) / 1000.0
        qc_m3h = Qf_m3h - qp_m3h

        # 에너지 소비
        pump_eff = 0.8
        power_kw = (Qf_m3h * p_in_bar) / 36.0 / pump_eff
        sec_kwhm3 = power_kw / qp_m3h if qp_m3h > 0 else 0.0

        return StageMetric(
            stage=1,
            module_type=ModuleType.NF,
            recovery_pct=round(recovery, 2),
            flux_lmh=round(flux_lmh, 1),
            sec_kwhm3=round(sec_kwhm3, 2),
            ndp_bar=round(ndp, 2),
            p_in_bar=p_in_bar,
            p_out_bar=p_in_bar - dp_total,
            Qf=Qf_m3h,
            Qp=qp_m3h,
            Qc=qc_m3h,
            Cf=Cf_mgL,
            Cp=round(permeate_tds, 2),
            Cc=round(concentrate_tds, 2),
        )
