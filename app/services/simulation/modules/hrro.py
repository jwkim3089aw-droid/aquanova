# app/services/simulation/modules/hrro.py

from __future__ import annotations
import math
from typing import List, Tuple, Optional, Any, TYPE_CHECKING
from dataclasses import dataclass

from app.services.simulation.modules.base import SimulationModule

# 런타임 순환 참조 방지를 위한 Type Hinting 가드
if TYPE_CHECKING:
    from app.schemas.simulation import (
        StageConfig,
        FeedInput,
        StageMetric,
        TimeSeriesPoint,
        HRROMassTransferIn,
        HRROSpacerIn,
    )

# -----------------------------------------------------------------------------
# Optional Dependency: Water Chemistry (있으면 쓰고, 없으면 물리 공식만 사용)
# -----------------------------------------------------------------------------
try:
    from app.services.water_chemistry import (
        ChemistryProfile,
        scale_profile_for_tds,
        calculate_osmotic_pressure_bar,
    )

    HAS_CHEMISTRY = True
except ImportError:
    HAS_CHEMISTRY = False
    ChemistryProfile = Any

# -----------------------------------------------------------------------------
# Constants & Helpers
# -----------------------------------------------------------------------------
LMH_TO_MPS = 1e-3 / 3600.0


def _clamp(val: float, min_val: float, max_val: float) -> float:
    return max(min_val, min(val, max_val))


def _mm_to_m(val_mm: float) -> float:
    return float(val_mm) / 1000.0


@dataclass
class PhysicsResult:
    pressure_bar: float
    flux_lmh: float
    perm_flow_m3h: float
    perm_tds_mgL: float
    cp_factor: float
    ndp_bar: float
    osmotic_pressure_bar: float


# =============================================================================
# HRRO (Closed Circuit RO) Simulation Module
# =============================================================================
class HRROModule(SimulationModule):
    """
    [HRRO / CCRO Module]
    Semi-Batch RO 프로세스 시뮬레이션 엔진.
    설정된 회수율(Recovery)에 도달하면 배수(Flush) 단계로 간주하고 루프를 종료합니다.
    """

    def compute(self, config: StageConfig, feed: FeedInput) -> StageMetric:
        # Local Import (순환 참조 방지)
        from app.schemas.simulation import StageMetric, TimeSeriesPoint
        from app.schemas.common import ModuleType

        # -----------------------------------------------------
        # 1. Configuration Setup
        # -----------------------------------------------------
        loop_vol_m3 = float(config.loop_volume_m3 or 2.0)
        limit_pressure_bar = float(config.pressure_bar or 60.0)
        max_time_min = float(config.max_minutes or 60.0)
        recirc_flow = config.recirc_flow_m3h or 12.0

        # ✅ [CRITICAL FIX] 목표 회수율 설정 (종료 트리거)
        # 1순위: stop_recovery_pct (명시적 종료값)
        # 2순위: recovery_target_pct (호환성)
        # 기본값: 95.0 (설정 누락 시 안전장치)
        target_recovery_pct = config.stop_recovery_pct or config.recovery_target_pct
        if target_recovery_pct is None or target_recovery_pct <= 0:
            target_recovery_pct = 95.0

        # Time Step 설정 (정밀도: 0.5분)
        dt_min = 0.5
        dt_hour = dt_min / 60.0

        # Membrane & System Spec
        elements = config.elements
        area_per_element = config.membrane_area_m2 or 37.0
        total_area_m2 = elements * area_per_element
        A_lmh_bar = config.membrane_A_lmh_bar or 4.0
        B_lmh = config.membrane_B_lmh or 0.1

        spacer_conf = config.spacer
        mt_conf = config.mass_transfer

        # -----------------------------------------------------
        # 2. State Initialization
        # -----------------------------------------------------
        current_tds = float(feed.tds_mgL)
        current_time = 0.0
        total_perm_vol_m3 = 0.0

        current_chem = self._create_initial_chem_profile(feed)
        history: List[TimeSeriesPoint] = []

        # -----------------------------------------------------
        # 3. Batch Simulation Loop
        # -----------------------------------------------------
        while current_time <= max_time_min:

            # (A) Physics Calculation (물리 연산)
            physics = self._calc_physics(
                current_tds_mgL=current_tds,
                feed_temp_C=feed.temperature_C,
                limit_pressure_bar=limit_pressure_bar,
                chem_profile=current_chem,
                total_area_m2=total_area_m2,
                A_lmh_bar=A_lmh_bar,
                B_lmh=B_lmh,
                spacer=spacer_conf,
                mt=mt_conf,
                recirc_flow=recirc_flow,
            )

            # (B) Mass Balance (물질 수지)
            q_p = physics.perm_flow_m3h
            c_p = physics.perm_tds_mgL

            # 루프 내 농도 증가 계산 (Semi-Batch: 물만 빠져나가고 염분은 농축됨)
            # 근사식: dC = (Qp / V) * (C_feed - Cp) * dt
            delta_tds = (q_p / loop_vol_m3) * (feed.tds_mgL - c_p) * dt_hour
            current_tds = max(current_tds + delta_tds, feed.tds_mgL)

            total_perm_vol_m3 += q_p * dt_hour

            # 회수율 갱신
            denom = total_perm_vol_m3 + loop_vol_m3
            current_recovery = (total_perm_vol_m3 / denom * 100.0) if denom > 0 else 0.0

            # (C) Water Chemistry Scaling (선택 사항)
            if HAS_CHEMISTRY and current_chem:
                try:
                    current_chem = scale_profile_for_tds(
                        base_profile=self._create_initial_chem_profile(feed),
                        target_tds=current_tds,
                    )
                except Exception:
                    pass

            # (D) History Recording
            history.append(
                TimeSeriesPoint(
                    time_min=round(current_time, 2),
                    recovery_pct=round(current_recovery, 2),
                    pressure_bar=round(physics.pressure_bar, 2),
                    tds_mgL=round(current_tds, 1),
                    flux_lmh=round(physics.flux_lmh, 2),
                    ndp_bar=round(physics.ndp_bar, 2),
                    permeate_flow_m3h=round(q_p, 4),
                    permeate_tds_mgL=round(c_p, 2),
                )
            )

            # -----------------------------------------------------
            # ✅ [CRITICAL FIX] Loop Termination Trigger
            # -----------------------------------------------------
            # 1. 목표 회수율 도달 시 즉시 종료 (110% 폭주 방지)
            if current_recovery >= target_recovery_pct:
                break

            # 2. 물리적 한계 도달 시 종료 (압력 Max & 유량 0)
            if (
                physics.pressure_bar >= (limit_pressure_bar - 0.5)
                and physics.flux_lmh < 1.0
            ):
                break

            # 3. 수질 한계 도달 시 종료 (옵션)
            if config.stop_permeate_tds_mgL and c_p >= config.stop_permeate_tds_mgL:
                break

            current_time += dt_min

        # -----------------------------------------------------
        # 4. Result Aggregation
        # -----------------------------------------------------
        last_pt = history[-1] if history else None
        avg_flux = sum(p.flux_lmh for p in history) / len(history) if history else 0.0

        # 에너지 소모량(SEC) 계산
        sec = 0.0
        if total_perm_vol_m3 > 0:
            total_energy_kwh = 0.0
            for pt in history:
                # Power (kW) = (Flow(m3/h) * Pressure(bar)) / 36 / Efficiency
                p_kw = (pt.permeate_flow_m3h * pt.pressure_bar) / 36.0 / 0.80
                total_energy_kwh += p_kw * dt_hour
            sec = total_energy_kwh / total_perm_vol_m3

        return StageMetric(
            stage=1,
            module_type=ModuleType.HRRO,
            recovery_pct=round(last_pt.recovery_pct if last_pt else 0.0, 2),
            flux_lmh=round(avg_flux, 1),
            sec_kwhm3=round(sec, 2),
            ndp_bar=round(last_pt.ndp_bar if last_pt else 0.0, 1),
            p_in_bar=limit_pressure_bar,
            p_out_bar=limit_pressure_bar - 1.0,  # Loop Pressure Drop
            Qf=feed.flow_m3h,
            Qp=last_pt.permeate_flow_m3h if last_pt else 0.0,
            Qc=loop_vol_m3 / dt_hour if dt_hour > 0 else 0,  # Virtual Reject Flow
            Cf=feed.tds_mgL,
            Cp=(
                round(sum(p.permeate_tds_mgL for p in history) / len(history), 1)
                if history
                else 0.0
            ),
            Cc=last_pt.tds_mgL if last_pt else 0.0,
            time_history=history,
            chemistry=None,
        )

    # -------------------------------------------------------------------------
    # Internal Physics Helpers
    # -------------------------------------------------------------------------
    def _create_initial_chem_profile(self, feed: FeedInput) -> Optional[Any]:
        if HAS_CHEMISTRY:
            try:
                return ChemistryProfile(
                    tds_mgL=feed.tds_mgL,
                    temperature_C=feed.temperature_C,
                    ph=feed.ph,
                )
            except Exception:
                return None
        return None

    def _calc_physics(
        self,
        *,
        current_tds_mgL,
        feed_temp_C,
        limit_pressure_bar,
        chem_profile,
        total_area_m2,
        A_lmh_bar,
        B_lmh,
        spacer,
        mt,
        recirc_flow,
    ) -> PhysicsResult:
        """
        주어진 상태에서의 순간 물리량(압력, Flux, 수질)을 계산합니다.
        """
        # 1. 삼투압(Osmotic Pressure) 계산
        if HAS_CHEMISTRY and chem_profile:
            try:
                pi_bulk = float(calculate_osmotic_pressure_bar(chem_profile))
            except:
                pi_bulk = self._vant_hoff(current_tds_mgL, feed_temp_C)
        else:
            pi_bulk = self._vant_hoff(current_tds_mgL, feed_temp_C)

        # 2. 유체 역학 (Mass Transfer)
        epsilon, dh_m = self._resolve_spacer(spacer)
        channel_area = (
            mt.feed_channel_area_m2 if (mt and mt.feed_channel_area_m2) else 0.015
        )

        # Crossflow Velocity
        if channel_area > 0:
            u_mps = (recirc_flow / 3600.0) / (channel_area * epsilon)
        else:
            u_mps = 0.15

        k_mps = self._calc_k(u_mps, dh_m, mt)

        # 3. 용액 확산 모델 (Solution Diffusion Model)
        hydraulic_loss = 1.5  # Loop friction loss
        applied_p = limit_pressure_bar

        # 농도 분극(CP) 1차 추정
        ndp_guess = max(applied_p - pi_bulk - hydraulic_loss, 0.0)
        flux_guess = A_lmh_bar * ndp_guess

        # CP Factor 계산
        if k_mps > 1e-9:
            flux_mps = flux_guess * LMH_TO_MPS
            cp_exponent = min(
                flux_mps / k_mps, 4.0
            )  # Limit exponential to avoid overflow
            cp_factor = math.exp(cp_exponent)
        else:
            cp_factor = 1.0

        # 실제 표면 삼투압 및 Flux 재계산
        pi_surface = pi_bulk * cp_factor
        ndp_real = max(applied_p - pi_surface - hydraulic_loss, 0.1)
        flux_real = A_lmh_bar * ndp_real

        # 4. 용질 이동 (Solute Transport)
        c_surface = current_tds_mgL * cp_factor
        # Cp = B * C_wall / (Jw + B)
        perm_tds = (B_lmh * c_surface) / (flux_real + B_lmh) if flux_real > 0 else 0.0
        perm_flow = (flux_real * total_area_m2) / 1000.0

        return PhysicsResult(
            pressure_bar=applied_p,
            flux_lmh=flux_real,
            perm_flow_m3h=perm_flow,
            perm_tds_mgL=perm_tds,
            cp_factor=cp_factor,
            ndp_bar=ndp_real,
            osmotic_pressure_bar=pi_bulk,
        )

    def _vant_hoff(self, tds: float, temp_c: float) -> float:
        """Van't Hoff 방정식을 이용한 간이 삼투압 계산"""
        temp_k = temp_c + 273.15
        # 근사식: 1000ppm NaCl ~= 0.75 bar (at 25C)
        return (tds / 1000.0) * 0.75 * (temp_k / 298.15)

    def _resolve_spacer(self, sp) -> Tuple[float, float]:
        """스페이서 형상 정보 파싱 (공극률, 수력직경)"""
        # 기본값
        default_voidage = 0.85
        default_dh = 0.001

        if not sp:
            return default_voidage, default_dh

        epsilon = sp.voidage if sp.voidage else sp.voidage_fallback
        epsilon = _clamp(epsilon or default_voidage, 0.3, 0.98)

        if sp.hydraulic_diameter_m:
            dh_m = sp.hydraulic_diameter_m
        else:
            # 수력 직경 추정
            delta_m = _mm_to_m(sp.thickness_mm)
            d_fil_m = _mm_to_m(sp.filament_diameter_mm)

            denom = (2.0 / delta_m) + (1.0 - epsilon) * (4.0 / d_fil_m)
            dh_m = (4.0 * epsilon) / denom if denom > 0 else delta_m

        return epsilon, dh_m

    def _calc_k(self, u: float, dh: float, mt) -> float:
        """물질 전달 계수(k) 계산 (Sherwood Correlation)"""
        if not mt:
            return 1e-5

        rho = mt.rho_kg_m3
        mu = mt.mu_pa_s
        D = mt.diffusivity_m2_s

        if mu <= 0 or D <= 0:
            return 1e-5

        Re = (rho * u * dh) / mu
        Sc = mu / (rho * D)

        # 일반적인 스페이서 상관식 (Sh = 0.065 * Re^0.875 * Sc^0.25)
        Sh = 0.065 * (Re**0.875) * (Sc**0.25)
        k = (Sh * D) / dh
        return k
