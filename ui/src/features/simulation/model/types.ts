// src/features/flow-builder/model/types.ts
// AquaNova FlowBuilder — Type Definitions & Utilities

import type { CSSProperties, Dispatch, SetStateAction } from 'react';
import type { Node, Edge } from 'reactflow';
import type { TimeSeriesPoint } from '../../../api/types'; // Backend Contract

// ==========================================================
// 1. Core Configuration Types (Membranes & Units)
// ==========================================================

export type UnitKind = 'RO' | 'NF' | 'UF' | 'MF' | 'HRRO' | 'PUMP';

export type BaseMembraneConfig = {
  membrane_mode?: 'catalog' | 'custom';
  membrane_model?: string;
  custom_area_m2?: number;

  // Custom Physics
  custom_A_lmh_bar?: number;
  custom_B_lmh?: number;
  custom_salt_rejection_pct?: number;

  // Integrated Pump
  enable_pump?: boolean;
  pump_pressure_bar?: number;
  pump_efficiency_pct?: number;
};

export type ROConfig = BaseMembraneConfig & {
  elements: number;
  mode: 'pressure' | 'recovery';
  pressure_bar?: number;
  recovery_target_pct?: number;

  // Details
  ro_n_stages?: number;
  ro_flow_factor?: number;
  ro_temp_mode?: 'Design' | 'Operating';
  ro_temp_C?: number;
  ro_pass_permeate_back_pressure_bar?: number;
  ro_stage_pv_per_stage?: number;
  ro_stage_els_per_pv?: number;
  ro_stage_element_type?: string;
  ro_stage_total_els_per_stage?: number;
  ro_stage_pre_delta_p_bar?: number;
  ro_stage_back_pressure_bar?: number;
  ro_stage_boost_press_bar?: number | null;
  ro_stage_feed_press_bar?: number;
  ro_stage_percent_conc_to_feed_pct?: number;
  ro_stage_flow_factor?: number;
};

export type NFConfig = BaseMembraneConfig & {
  elements: number;
  mode: 'pressure' | 'recovery';
  pressure_bar?: number;
  recovery_target_pct?: number;

  // Details
  nf_temp_mode?: 'Design' | 'Operating';
  nf_temp_C?: number;
  nf_pass_permeate_back_pressure_bar?: number;
  nf_design_flux_lmh_25C?: number;
  nf_max_flux_lmh?: number;
  nf_rejection_divalent_pct?: number;
  nf_rejection_monovalent_pct?: number;
  nf_rejection_toc_pct?: number;
  nf_max_delta_p_bar?: number;
  nf_max_feed_pressure_bar?: number;
  nf_max_feed_flow_m3h?: number;
  nf_stage_pv_per_stage?: number;
  nf_stage_els_per_pv?: number;
  nf_stage_element_type?: string;
  nf_stage_total_els_per_stage?: number;
  nf_feed_flow_m3h?: number;
  nf_permeate_flow_m3h?: number;
  nf_flux_lmh_25C?: number;
  nf_salt_rejection_pct?: number;
  // ... (Other specific NF params omitted for brevity, but can be added back if needed)
};

export type UFConfig = BaseMembraneConfig & {
  elements: number;

  // Flux & Flow
  filtrate_flux_lmh_25C?: number;
  backwash_flux_lmh?: number;

  // Cycle Intervals
  filtration_duration_min?: number;
  uf_backwash_duration_s?: number;

  // Details
  uf_feed_flow_m3h?: number;
  ceb_flux_lmh?: number;
  acid_ceb_interval_h?: number;
  alkali_ceb_interval_h?: number;
  cip_interval_d?: number;
  uf_module_model?: string;
  pump_eff?: number;
};

export type MFConfig = BaseMembraneConfig & {
  elements: number;
  mode: 'pressure' | 'recovery';
  pressure_bar?: number;
  recovery_target_pct?: number;

  // Cycle
  mf_filtration_duration_min?: number;
  mf_backwash_duration_s?: number;
  mf_filtrate_flux_lmh_25C?: number;
  mf_backwash_flux_lmh?: number;

  // Details
  mf_design_flux_lmh_25C?: number;
  mf_operating_tmp_bar?: number;
  mf_module_model?: string;
};

export type HRROConfig = BaseMembraneConfig & {
  elements: number;
  p_set_bar: number;
  recirc_flow_m3h: number;
  bleed_m3h: number;
  loop_volume_m3: number;
  makeup_tds_mgL: number | null;
  timestep_s: number;
  max_minutes: number;
  stop_permeate_tds_mgL: number | null;
  stop_recovery_pct: number | null;

  // Advanced Inputs
  mass_transfer?: {
    crossflow_velocity_m_s?: number;
    recirc_flow_m3h?: number;
    feed_channel_area_m2?: number;
    rho_kg_m3?: number;
    mu_pa_s?: number;
    diffusivity_m2_s?: number;
    cp_exp_max?: number;
    cp_rel_tol?: number;
    cp_abs_tol_lmh?: number;
    cp_relax?: number;
    cp_max_iter?: number;
    [k: string]: any;
  };

  spacer?: {
    thickness_mm?: number;
    filament_diameter_mm?: number;
    mesh_size_mm?: number;
    voidage?: number;
    voidage_fallback?: number;
    hydraulic_diameter_m?: number;
    [k: string]: any;
  };
};

export type PumpConfig = {
  mode: 'fixed_pressure' | 'boost_pressure';
  pressure_bar: number;
  pump_efficiency_pct: number;
};

export type OLConfig = ROConfig | NFConfig | UFConfig | MFConfig;
export type AnyUnitConfig = OLConfig | HRROConfig;

// ==========================================================
// 2. Flow Nodes & Data Structures
// ==========================================================

export type Chip = {
  label: string;
  value: string;
  warn?: boolean;
  tip?: string;
};

export type UnitData =
  | { type: 'unit'; kind: 'RO'; cfg: ROConfig; chips?: Chip[] }
  | { type: 'unit'; kind: 'NF'; cfg: NFConfig; chips?: Chip[] }
  | { type: 'unit'; kind: 'UF'; cfg: UFConfig; chips?: Chip[] }
  | { type: 'unit'; kind: 'MF'; cfg: MFConfig; chips?: Chip[] }
  | { type: 'unit'; kind: 'HRRO'; cfg: HRROConfig; chips?: Chip[] }
  | { type: 'unit'; kind: 'PUMP'; cfg: PumpConfig; chips?: Chip[] };

export type FlowData =
  | { type: 'endpoint'; role: 'feed' | 'product'; label: string }
  | UnitData;

export type EndpointData = Extract<FlowData, { type: 'endpoint' }>;

export type Snapshot = { nodes: Node<FlowData>[]; edges: Edge[] };

export type NodeKind =
  | 'FEED'
  | 'PRODUCT'
  | 'RO'
  | 'NF'
  | 'UF'
  | 'MF'
  | 'HRRO'
  | 'MBR'
  | 'PUMP';
export type StageKind = 'RO' | 'NF' | 'UF' | 'MF';

export type NodeData = {
  kind: NodeKind;
  type?: StageKind;
  label?: string;
  cfg?: any;
};

export type UnitMode = 'SI' | 'US';
export type UnitNode = Node<FlowData> & { data: UnitData };
export type UnitNodeRF = UnitNode;

export type ChainOk = { ok: true; chain: UnitNodeRF[] };
export type ChainErr = { ok: false; message: string };

export type SetNodesFn = Dispatch<SetStateAction<Node<FlowData>[]>>;
export type SetEdgesFn = Dispatch<SetStateAction<Edge[]>>;

// ==========================================================
// 3. Chemistry Types
// ==========================================================

export type ChemistryInput = {
  alkalinity_mgL_as_CaCO3: number | null;
  calcium_hardness_mgL_as_CaCO3: number | null;
  nh4_mgL?: number | null;
  k_mgL?: number | null;
  na_mgL?: number | null;
  mg_mgL?: number | null;
  ca_mgL?: number | null;
  sr_mgL?: number | null;
  ba_mgL?: number | null;
  fe_mgL?: number | null;
  mn_mgL?: number | null;
  hco3_mgL?: number | null;
  no3_mgL?: number | null;
  cl_mgL?: number | null;
  f_mgL?: number | null;
  so4_mgL?: number | null;
  br_mgL?: number | null;
  po4_mgL?: number | null;
  co3_mgL?: number | null;
  sio2_mgL?: number | null;
  b_mgL?: number | null;
  co2_mgL?: number | null;

  // Legacy support
  sulfate_mgL?: number | null;
  barium_mgL?: number | null;
  strontium_mgL?: number | null;
  silica_mgL_SiO2?: number | null;
};

export type ChemistrySI = {
  lsi: number | null;
  rsi: number | null;
  s_dsi: number | null;
  caco3_si: number | null;
  caso4_si: number | null;
  baso4_si: number | null;
  srso4_si: number | null;
  sio2_si: number | null;
};

export type ChemistrySummary = {
  feed?: ChemistrySI | null;
  final_brine?: ChemistrySI | null;
};

// ==========================================================
// 4. Persistence Model
// ==========================================================

export type PersistModel = {
  nodes: Node<FlowData>[];
  edges: Edge[];
  feed: {
    flow_m3h: number;
    tds_mgL: number;
    temperature_C: number;
    ph: number;
    water_type?: string;
  };
  opt: {
    auto: boolean;
    membrane: string;
    segments: number;
    pump_eff: number;
    erd_eff: number;
  };
  name?: string;
  chemistry?: ChemistryInput;
};

// ==========================================================
// 5. Units & Utilities (Constants)
// ==========================================================

export const GPM_PER_M3H = 4.402867;
export const PSI_PER_BAR = 14.5037738;
export const GFD_PER_LMH = 0.408734974;

export const HANDLE_STYLE: CSSProperties = {
  width: 10,
  height: 10,
  borderRadius: '9999px',
  background: '#2563eb',
  zIndex: 30,
  top: '50%',
  transform: 'translateY(-50%)',
};

export const MAX_FLUX_BY_KIND: Record<UnitKind, number> = {
  RO: 40,
  HRRO: 40,
  NF: 50,
  UF: 220,
  MF: 300,
  PUMP: 0,
};

export const DEFAULT_CHEMISTRY: ChemistryInput = {
  alkalinity_mgL_as_CaCO3: null,
  calcium_hardness_mgL_as_CaCO3: null,
  sulfate_mgL: null,
  barium_mgL: null,
  strontium_mgL: null,
  silica_mgL_SiO2: null,
};

// ==========================================================
// 6. Utility Functions
// ==========================================================

export function convFlow(v: number, from: UnitMode, to: UnitMode): number {
  if (from === to) return v;
  return from === 'SI' ? v * GPM_PER_M3H : v / GPM_PER_M3H;
}

export function convTemp(v: number, from: UnitMode, to: UnitMode): number {
  if (from === to) return v;
  return from === 'SI' ? (v * 9) / 5 + 32 : ((v - 32) * 5) / 9;
}

export function convPress(v: number, from: UnitMode, to: UnitMode): number {
  if (from === to) return v;
  return from === 'SI' ? v * PSI_PER_BAR : v / PSI_PER_BAR;
}

export function convFlux(v: number, from: UnitMode, to: UnitMode): number {
  if (from === to) return v;
  return from === 'SI' ? v * GFD_PER_LMH : v / GFD_PER_LMH;
}

export function unitLabel(
  kind: 'flow' | 'temp' | 'press' | 'flux',
  mode: UnitMode,
): string {
  if (kind === 'flow') return mode === 'SI' ? 'm³/h' : 'gpm';
  if (kind === 'temp') return mode === 'SI' ? '°C' : '°F';
  if (kind === 'press') return mode === 'SI' ? 'bar' : 'psi';
  return mode === 'SI' ? 'LMH' : 'gfd';
}

export const fmt = (n: number | undefined, d = 2): string =>
  n == null ? '-' : Number(n).toFixed(d);

export const pct = (n: number | undefined, d = 1): string =>
  n == null ? '-' : `${Number(n).toFixed(d)}%`;

export function clampf(n: any, lo: number, hi: number): number {
  const x = Number(n);
  if (!Number.isFinite(x)) return lo;
  return Math.max(lo, Math.min(hi, x));
}

export function num(v: any, d: number): number {
  const n = Number(v);
  return Number.isFinite(n) ? n : d;
}

export function clampInt(v: any, lo: number, hi: number): number {
  const n = Math.round(Number(v));
  if (!Number.isFinite(n)) return lo;
  return Math.max(lo, Math.min(hi, n));
}

// ==========================================================
// 7. Simulation Result Types (Synced with Backend)
// ==========================================================

// ✅ HRRO/Process Result Type (Standardized)
export type HRRORunOutput = {
  minutes: number;
  recovery_pct: number;

  // Loop status
  V_loop_final_m3: number;
  C_loop_final_mgL: number;

  // Totals
  Qp_total_m3: number;
  Cp_mix_mgL: number;

  // [Standardized Keys] Backend StageMetric과 일치
  jw_avg_lmh: number; // flux
  ndp_bar: number;
  sec_kwhm3: number;

  p_set_bar: number;
  avg_delta_pi_bar: number;
  bleed_total_m3: number;

  // [Graph Data] Shared TimeSeriesPoint
  time_history: TimeSeriesPoint[];
  stage_metrics: any[];

  kpi?: {
    flux_lmh: number;
    ndp_bar: number;
    sec_kwhm3: number;
    recovery_pct: number;
  };
};
