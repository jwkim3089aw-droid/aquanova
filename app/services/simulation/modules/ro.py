# app\services\simulation\modules\ro.py
import math
from typing import Optional

from app.services.simulation.modules.base import SimulationModule
from app.api.v1.schemas import StageConfig, FeedInput, StageMetric, ModuleType

# 상수 정의
P_PERM_BAR = 0.0  # 처리수 배압 (대기압)


class ROModule(SimulationModule):
    """
    [RO/NF 통합 모듈]
    - 기존 solvers/ro.py (공정 레벨)와 strategies/ro.py (멤브레인 레벨) 통합
    - Solution-Diffusion 모델 사용
    - 농도 분극(CP) 및 물질 수지(Mass Balance) 동시 계산
    """

    def compute(self, config: StageConfig, feed: FeedInput) -> StageMetric:
        # 1. 입력 파라미터 추출 (Safe Extraction)
        Qf_m3h = feed.flow_m3h
        Cf_mgL = feed.tds_mgL
        T_C = feed.temperature_C

        # 멤브레인 물성
        elements = config.elements
        area_per_element = config.membrane_area_m2 or 40.0
        total_area = elements * area_per_element

        A = config.membrane_A_lmh_bar or 3.0  # 투수 계수 (기본값)
        B_lmh = config.membrane_B_lmh or 0.1  # 염 투과 계수

        # 운전 조건
        p_in_bar = config.pressure_bar or 15.0  # 입력 없으면 기본값
        target_recovery = config.recovery_target_pct

        # 압력 손실 가정 (모듈당 0.2 bar)
        dp_module = 0.2
        dp_total = elements * dp_module

        # 2. 반복 계산 (Iterative Calculation for Flux & Recovery)
        # RO는 공급 압력(Pin)이 주어지면 Flux가 결정되고,
        # Flux가 결정되면 농도분극(CP)이 바뀌어 다시 Flux에 영향을 줌.

        # 초기 가정값
        avg_pressure = p_in_bar - (dp_total / 2)
        avg_conc = Cf_mgL * 1.2  # 평균 농도 가정

        flux_lmh = 0.0
        permeate_tds = 0.0

        # 수렴 루프 (최대 10회)
        for _ in range(10):
            # (1) 삼투압 계산 (Van't Hoff 근사: 1000ppm ~= 0.7 bar)
            temp_K = T_C + 273.15
            pi_avg = (avg_conc / 1000.0) * 0.75 * (temp_K / 298.15)

            # (2) 유효 구동 압력 (NDP)
            ndp = avg_pressure - P_PERM_BAR - pi_avg
            if ndp < 0.1:
                ndp = 0.1

            # (3) Flux 계산 (J = A * NDP)
            flux_lmh = A * ndp

            # (4) 염 투과 계산 (Cp = B * Cm / (J + B))
            # 농도 분극 계수(Beta) 약식 계산: exp(J/k) 형태
            # 여기서는 간단히 Flux에 비례하여 표면 농도(Cm)가 벌크 농도보다 높다고 가정
            cp_factor = math.exp(flux_lmh / 150.0)  # k=150 lmh 가정
            cm = avg_conc * cp_factor
            permeate_tds = (B_lmh * cm) / (flux_lmh + B_lmh)

            # (5) 회수율 계산에 따른 평균 농도 업데이트
            # Qp = J * Area
            qp_m3h = (flux_lmh * total_area) / 1000.0

            # Max Recovery 제한 (물리적 한계)
            if qp_m3h > Qf_m3h * 0.95:
                qp_m3h = Qf_m3h * 0.95
                flux_lmh = (qp_m3h * 1000.0) / total_area

            recovery = qp_m3h / Qf_m3h

            # 로그 평균 농도 (Log Mean Concentration) 근사
            qc_m3h = Qf_m3h - qp_m3h
            concentrate_tds = (Qf_m3h * Cf_mgL - qp_m3h * permeate_tds) / qc_m3h

            new_avg_conc = (Cf_mgL + concentrate_tds) / 2

            # 수렴 판정 (농도 변화가 1% 미만이면 종료)
            if abs(new_avg_conc - avg_conc) / avg_conc < 0.01:
                avg_conc = new_avg_conc
                break

            avg_conc = new_avg_conc

        # 3. 최종 결과 정리
        qp_m3h = (flux_lmh * total_area) / 1000.0
        qc_m3h = Qf_m3h - qp_m3h

        # 에너지 소비 (SEC)
        pump_eff = 0.8
        power_kw = (Qf_m3h * p_in_bar) / 36.0 / pump_eff
        sec_kwhm3 = power_kw / qp_m3h if qp_m3h > 0 else 0.0

        return StageMetric(
            stage=0,  # Engine에서 설정
            module_type=config.module_type,  # RO or HRRO or NF
            # Performance
            recovery_pct=recovery,
            flux_lmh=flux_lmh,
            sec_kwhm3=sec_kwhm3,
            ndp_bar=ndp,
            # Pressures
            p_in_bar=p_in_bar,
            p_out_bar=p_in_bar - dp_total,
            # Mass Balance
            Qf=Qf_m3h,
            Qp=qp_m3h,
            Qc=qc_m3h,
            Cf=Cf_mgL,
            Cp=permeate_tds,
            Cc=concentrate_tds,
        )
