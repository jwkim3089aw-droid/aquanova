// ui/src/features/simulation/FlowBuilder.utils.ts
import { Node } from 'reactflow';
import { StageConfig } from '../../api/types';
import { UnitKind, UnitData, FlowData } from './model/types';

export function defaultConfig(k: UnitKind): StageConfig {
  const baseConfig: Partial<StageConfig> = {
    module_type: k as any,
    element_inch: 8,
    vessel_count: 10,
    elements_per_vessel: 5,
    elements: 50,
    membrane_area_m2: 40.9,
    flow_factor: 0.85,
    permeate_back_pressure_bar: 0.0,
    burst_pressure_limit_bar: 83.0,
  };

  if (k === 'HRRO') {
    return {
      ...baseConfig,
      module_type: 'HRRO',
      membrane_model: 'filmtec-soar-5000i',
      membrane_A_lmh_bar: 5.5,
      membrane_B_lmh: 0.06,
      membrane_salt_rejection_pct: 99.5,
      pressure_bar: 50.0,
      recovery_target_pct: 90.0,
      stop_recovery_pct: 90.0,
      loop_volume_m3: 1.36,
      recirc_flow_m3h: 120.0,
      max_minutes: 60.0,
      timestep_s: 5,
      hrro_engine: 'physics', // 🔥 스모킹 건 해결: 진짜 물리화학 엔진(physics) 풀가동!!
      cc_recycle_m3h_per_pv: 4.33,
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
    return {
      ...baseConfig,
      module_type: 'RO',
      membrane_model: 'filmtec-bw30-400',
      membrane_A_lmh_bar: 4.0,
      membrane_B_lmh: 0.5,
      pressure_bar: 15.0,
      recovery_target_pct: 50.0,
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

  return {
    ...baseConfig,
    module_type: 'UF',
    pressure_bar: 2.0,
    filtration_cycle_min: 30,
    backwash_duration_sec: 60,
  } as StageConfig;
}

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
