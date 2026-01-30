# app\services\simulation\modules\hrro.py
# app/services/simulation/modules/hrro.py

from __future__ import annotations  # ✅ [핵심 1] 타입 힌트 순환 참조 방지
import math
from typing import List, Tuple, Optional, Any, TYPE_CHECKING
from dataclasses import dataclass

from app.services.simulation.modules.base import SimulationModule

# ✅ [핵심 2] 런타임에는 import 하지 않고, IDE에서만 보이게 가둠
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
# Optional Dependency: Water Chemistry
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
    Simulates a Semi-Batch Reverse Osmosis process (Closed Circuit).
    """

    def compute(self, config: StageConfig, feed: FeedInput) -> StageMetric:
        # ✅ [핵심 3] 함수 안에서 import (Local Import) -> 순환 참조 완벽 해결
        from app.schemas.simulation import (
            StageMetric,
            TimeSeriesPoint,
            HRROMassTransferIn,
            HRROSpacerIn,
        )
        from app.schemas.common import ModuleType

        # -----------------------------------------------------
        # 1. Configuration
        # -----------------------------------------------------
        loop_vol_m3 = float(config.loop_volume_m3 or 2.0)
        limit_pressure_bar = float(config.pressure_bar or 60.0)
        max_time_min = float(config.max_minutes or 60.0)

        # Target Recovery
        target_recovery_pct = config.stop_recovery_pct or config.recovery_target_pct
        if target_recovery_pct is None or target_recovery_pct <= 0:
            target_recovery_pct = 95.0

        dt_min = 0.5
        dt_hour = dt_min / 60.0

        elements = config.elements
        area_per_element = config.membrane_area_m2 or 37.0
        total_area_m2 = elements * area_per_element
        A_lmh_bar = config.membrane_A_lmh_bar or 4.0
        B_lmh = config.membrane_B_lmh or 0.1

        spacer_conf = config.spacer or HRROSpacerIn()
        mt_conf = config.mass_transfer or HRROMassTransferIn()
        recirc_flow = config.recirc_flow_m3h or 12.0

        # State Init
        current_tds = float(feed.tds_mgL)
        current_time = 0.0
        total_perm_vol_m3 = 0.0

        current_chem = self._create_initial_chem_profile(feed)
        history: List[TimeSeriesPoint] = []

        # -----------------------------------------------------
        # 2. Loop
        # -----------------------------------------------------
        while current_time <= max_time_min:

            # (A) Physics
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

            # (B) Mass Balance
            q_p = physics.perm_flow_m3h
            c_p = physics.perm_tds_mgL

            delta_tds = (q_p / loop_vol_m3) * (feed.tds_mgL - c_p) * dt_hour
            current_tds = max(current_tds + delta_tds, feed.tds_mgL)

            step_perm_vol = q_p * dt_hour
            total_perm_vol_m3 += step_perm_vol

            # Recovery Calc
            denom = total_perm_vol_m3 + loop_vol_m3
            current_recovery = (total_perm_vol_m3 / denom * 100.0) if denom > 0 else 0.0

            # (C) Chem Scaling
            if HAS_CHEMISTRY and current_chem:
                try:
                    current_chem = scale_profile_for_tds(
                        base_profile=self._create_initial_chem_profile(feed),
                        target_tds=current_tds,
                    )
                except Exception:
                    pass

            # (D) History
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

            # (E) ✅ [FIX] Trigger Check (종료 조건)
            if current_recovery >= target_recovery_pct:
                break

            if (
                physics.pressure_bar >= (limit_pressure_bar - 0.5)
                and physics.flux_lmh < 1.0
            ):
                break

            current_time += dt_min

        # -----------------------------------------------------
        # 3. Finalize
        # -----------------------------------------------------
        last_pt = history[-1] if history else None
        avg_flux = sum(p.flux_lmh for p in history) / len(history) if history else 0.0

        if total_perm_vol_m3 > 0:
            total_energy_kwh = 0.0
            for pt in history:
                p_kw = (pt.permeate_flow_m3h * pt.pressure_bar) / 36.0 / 0.80
                total_energy_kwh += p_kw * dt_hour
            sec = total_energy_kwh / total_perm_vol_m3
        else:
            sec = 0.0

        return StageMetric(
            stage=1,
            module_type=ModuleType.HRRO,
            recovery_pct=round(last_pt.recovery_pct if last_pt else 0.0, 2),
            flux_lmh=round(avg_flux, 1),
            sec_kwhm3=round(sec, 2),
            ndp_bar=round(last_pt.ndp_bar if last_pt else 0.0, 1),
            p_in_bar=limit_pressure_bar,
            p_out_bar=limit_pressure_bar - 1.0,
            Qf=feed.flow_m3h,
            Qp=last_pt.permeate_flow_m3h if last_pt else 0.0,
            Qc=loop_vol_m3 / dt_hour if dt_hour > 0 else 0,
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

    # ... (Internal Methods) ...
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
    ):
        # 1. Osmotic Pressure
        if HAS_CHEMISTRY and chem_profile:
            try:
                pi_bulk = float(calculate_osmotic_pressure_bar(chem_profile))
            except:
                pi_bulk = self._vant_hoff(current_tds_mgL, feed_temp_C)
        else:
            pi_bulk = self._vant_hoff(current_tds_mgL, feed_temp_C)

        # 2. Hydrodynamics
        epsilon, dh_m = self._resolve_spacer(spacer)
        channel_area = mt.feed_channel_area_m2 or 0.015
        if channel_area > 0:
            u_mps = (recirc_flow / 3600.0) / (channel_area * epsilon)
        else:
            u_mps = 0.15
        k_mps = self._calc_k(u_mps, dh_m, mt)

        # 3. Solution Diffusion
        hydraulic_loss = 1.5
        applied_p = limit_pressure_bar

        ndp_guess = max(applied_p - pi_bulk - hydraulic_loss, 0.0)
        flux_guess = A_lmh_bar * ndp_guess

        if k_mps > 1e-9:
            flux_mps = flux_guess * LMH_TO_MPS
            cp_exponent = min(flux_mps / k_mps, 4.0)
            cp_factor = math.exp(cp_exponent)
        else:
            cp_factor = 1.0

        pi_surface = pi_bulk * cp_factor
        ndp_real = max(applied_p - pi_surface - hydraulic_loss, 0.1)
        flux_real = A_lmh_bar * ndp_real

        # 4. Solute Transport
        c_surface = current_tds_mgL * cp_factor
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
        temp_k = temp_c + 273.15
        return (tds / 1000.0) * 0.75 * (temp_k / 298.15)

    def _resolve_spacer(self, sp) -> Tuple[float, float]:
        delta_m = _mm_to_m(sp.thickness_mm)
        d_fil_m = _mm_to_m(sp.filament_diameter_mm)
        epsilon = sp.voidage if sp.voidage else sp.voidage_fallback
        epsilon = _clamp(epsilon, 0.3, 0.98)

        if sp.hydraulic_diameter_m:
            dh_m = sp.hydraulic_diameter_m
        else:
            denom = (2.0 / delta_m) + (1.0 - epsilon) * (4.0 / d_fil_m)
            dh_m = (4.0 * epsilon) / denom if denom > 0 else delta_m
        return epsilon, dh_m

    def _calc_k(self, u: float, dh: float, mt) -> float:
        rho = mt.rho_kg_m3
        mu = mt.mu_pa_s
        D = mt.diffusivity_m2_s
        if mu <= 0 or D <= 0:
            return 1e-5
        Re = (rho * u * dh) / mu
        Sc = mu / (rho * D)
        Sh = 0.065 * (Re**0.875) * (Sc**0.25)
        k = (Sh * D) / dh
        return k
