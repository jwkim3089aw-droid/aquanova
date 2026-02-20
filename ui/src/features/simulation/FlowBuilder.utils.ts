// ui/src/features/simulation/FlowBuilder.utils.ts
import { Node } from 'reactflow';
import { StageConfig } from '../../api/types';
import { UnitKind, UnitData, FlowData } from './model/types';

// =========================================================
// Default Configuration Generator
// - Aligned with Backend Schema (Hardware & Physics Defaults)
// =========================================================

export function defaultConfig(k: UnitKind): StageConfig {
  // 공통 기본값 정의
  const baseConfig: Partial<StageConfig> = {
    module_type: k as any,
    element_inch: 8,
    // 🛑 [WAVE 일치화] 하드웨어 그릇 크기 동기화
    vessel_count: 10, // Default: 10 Pressure Vessels
    elements_per_vessel: 5, // Default: 5 Elements per Vessel
    elements: 50, // Total = 10 * 5 = 50

    // Membrane Defaults (Clean)
    membrane_area_m2: 40.9,
    flow_factor: 0.85, // Aging Factor (Standard 3-year equivalent)

    // Safety & Back Pressure
    permeate_back_pressure_bar: 0.0,
    burst_pressure_limit_bar: 83.0, // approx 1200 psi
  };

  if (k === 'HRRO') {
    // HRRO: High Recovery, Closed Circuit Logic
    return {
      ...baseConfig,
      module_type: 'HRRO',
      membrane_model: 'FilmTec SOAR 6000i',

      // HRRO Performance Specs
      membrane_A_lmh_bar: 6.35,
      membrane_B_lmh: 0.058,
      membrane_salt_rejection_pct: 99.5,

      // Operation Targets
      pressure_bar: 50.0, // High pressure assumption for high recovery
      recovery_target_pct: 90.0, // Batch Stop Recovery
      stop_recovery_pct: 90.0, // Explicit Stop Condition

      // Loop & Cycle
      loop_volume_m3: 2.0,
      recirc_flow_m3h: 120.0, // High crossflow
      max_minutes: 60.0,
      timestep_s: 5,
      hrro_engine: 'excel_only',

      // 🛑 [WAVE 일치화] 농축수 순환 기본값 추가
      cc_recycle_m3h_per_pv: 4.33,

      // Advanced Physics
      mass_transfer: {
        feed_channel_area_m2: 0.015,
        rho_kg_m3: 998.0,
        mu_pa_s: 0.001,
        diffusivity_m2_s: 1.5e-9,
      },
      spacer: {
        thickness_mm: 0.864,
        filament_diameter_mm: 0.35,
        voidage: 0.88,
      },
    } as StageConfig;
  }

  if (k === 'RO') {
    // Standard RO Logic
    return {
      ...baseConfig,
      module_type: 'RO',
      membrane_model: 'FilmTec BW30-400',

      membrane_A_lmh_bar: 4.0,
      membrane_B_lmh: 0.5,

      pressure_bar: 15.0,
      recovery_target_pct: 50.0, // Standard Single Pass Recovery
    } as StageConfig;
  }

  if (k === 'NF') {
    return {
      ...baseConfig,
      module_type: 'NF',
      pressure_bar: 10.0,
      recovery_target_pct: 75.0,
    } as StageConfig;
  }

  if (k === 'MF') {
    return {
      ...baseConfig,
      module_type: 'MF',
      pressure_bar: 1.0,
      recovery_target_pct: 95.0,
      filtration_cycle_min: 30,
      backwash_duration_sec: 60,
    } as StageConfig;
  }

  // UF Defaults
  return {
    ...baseConfig,
    module_type: 'UF',
    pressure_bar: 2.0,
    filtration_cycle_min: 30,
    backwash_duration_sec: 60,
  } as StageConfig;
}

// ---------------------------------------------------------
// Helper: Ensure Unit Config exists on nodes
// ---------------------------------------------------------
export function ensureUnitCfg(nodes: Node<FlowData>[]): Node<FlowData>[] {
  return nodes.map((n) => {
    const d: any = n.data;
    if (d?.type === 'unit' && !d.cfg) {
      const kind = d.kind as UnitKind;
      return {
        ...n,
        data: {
          ...d,
          cfg: defaultConfig(kind),
        } as UnitData,
      } as Node<FlowData>;
    }
    return n;
  });
}
