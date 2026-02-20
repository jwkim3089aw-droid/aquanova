// ui/src/features/simulation/model/types.ts
// AquaNova FlowBuilder — Types & Utilities

import type { CSSProperties, Dispatch, SetStateAction } from 'react';
import type { Node, Edge } from 'reactflow';
import type { TimeSeriesPoint } from '@/api/types';
import type { ChargeBalanceMode } from '../chemistry';

// ==========================================================
// 1) Core Unit Types
// ==========================================================

export type UnitKind = 'RO' | 'NF' | 'UF' | 'MF' | 'HRRO' | 'PUMP';

export type BaseMembraneConfig = {
  membrane_mode?: 'catalog' | 'custom';
  membrane_model?: string;
  custom_area_m2?: number;
  custom_A_lmh_bar?: number;
  custom_B_lmh?: number;
  custom_salt_rejection_pct?: number;

  enable_pump?: boolean;
  pump_pressure_bar?: number;
  pump_efficiency_pct?: number;
};

export type ROConfig = BaseMembraneConfig & {
  elements: number;
  mode: 'pressure' | 'recovery';
  pressure_bar?: number;
  recovery_target_pct?: number;
  [k: string]: any;
};

export type NFConfig = BaseMembraneConfig & {
  elements: number;
  mode: 'pressure' | 'recovery';
  pressure_bar?: number;
  recovery_target_pct?: number;
  [k: string]: any;
};

export type UFConfig = BaseMembraneConfig & {
  elements: number;
  filtrate_flux_lmh_25C?: number;
  backwash_flux_lmh?: number;
  filtration_duration_min?: number;
  uf_backwash_duration_s?: number;
  [k: string]: any;
};

export type MFConfig = BaseMembraneConfig & {
  elements: number;
  mode: 'pressure' | 'recovery';
  pressure_bar?: number;
  recovery_target_pct?: number;
  mf_filtration_duration_min?: number;
  mf_backwash_duration_s?: number;
  mf_filtrate_flux_lmh_25C?: number;
  mf_backwash_flux_lmh?: number;
  [k: string]: any;
};

export type HRROConfig = BaseMembraneConfig & {
  elements: number;
  p_set_bar: number;
  recirc_flow_m3h: number;
  bleed_m3h: number;
  loop_volume_m3: number;
  timestep_s: number;
  max_minutes: number;

  stop_permeate_tds_mgL: number | null;
  stop_recovery_pct: number | null;

  element_inch?: number;
  vessel_count?: number;
  elements_per_vessel?: number;

  feed_flow_m3h?: number;
  ccro_recovery_pct?: number;
  pf_feed_ratio_pct?: number;
  pf_recovery_pct?: number;
  cc_recycle_m3h_per_pv?: number;
  membrane_area_m2_per_element?: number;

  pump_eff?: number;
  mass_transfer?: Record<string, any>;
  spacer?: Record<string, any>;
  [k: string]: any;
};

export type PumpConfig = {
  mode: 'fixed_pressure' | 'boost_pressure';
  pressure_bar: number;
  pump_efficiency_pct: number;
};

export type OLConfig = ROConfig | NFConfig | UFConfig | MFConfig;
export type AnyUnitConfig = OLConfig | HRROConfig;

// ==========================================================
// 2) Flow Nodes
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

export type UnitMode = 'SI' | 'US';

export type UnitNode = Node<FlowData> & { data: UnitData };
export type UnitNodeRF = UnitNode;

export type ChainOk = { ok: true; chain: UnitNodeRF[] };
export type ChainErr = { ok: false; message: string };

export type SetNodesFn = Dispatch<SetStateAction<Node<FlowData>[]>>;
export type SetEdgesFn = Dispatch<SetStateAction<Edge[]>>;

// ==========================================================
// 3) Chemistry UI Model (Strict WAVE Ordering)
// ==========================================================

export type ChemistryInput = {
  // scaling inputs
  alkalinity_mgL_as_CaCO3: number | null;
  calcium_hardness_mgL_as_CaCO3: number | null;

  // --- Cations (+) ---
  nh4_mgL?: number | null;
  k_mgL?: number | null;
  na_mgL?: number | null;
  mg_mgL?: number | null;
  ca_mgL?: number | null;
  sr_mgL?: number | null;
  ba_mgL?: number | null;
  // Non-WAVE (kept for compatibility, UI will hide by default)
  fe_mgL?: number | null;
  mn_mgL?: number | null;

  // --- Anions (-) ---
  co3_mgL?: number | null;
  hco3_mgL?: number | null;
  no3_mgL?: number | null;
  cl_mgL?: number | null;
  f_mgL?: number | null;
  so4_mgL?: number | null;
  br_mgL?: number | null;
  po4_mgL?: number | null;

  // --- Neutrals ---
  sio2_mgL?: number | null;
  b_mgL?: number | null;
  co2_mgL?: number | null;

  // legacy support
  sulfate_mgL?: number | null;
  barium_mgL?: number | null;
  strontium_mgL?: number | null;
  silica_mgL_SiO2?: number | null;

  [k: string]: unknown;
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
  [k: string]: any;
};

export type ChemistrySummary = {
  feed?: ChemistrySI | null;
  final_brine?: ChemistrySI | null;
};

// ==========================================================
// 4) Persistence Model (Strict WAVE Feed Setup)
// ==========================================================

export type FeedState = {
  // Flow & Basic
  flow_m3h: number;
  tds_mgL: number;
  ph: number;
  pressure_bar?: number;

  // WAVE Temperature (3 points)
  temperature_C: number; // Design Temp
  temp_min_C: number | null;
  temp_max_C: number | null;

  // WAVE Water Meta
  water_type?: string | null;
  water_subtype?: string | null;

  // WAVE Solid Content
  turbidity_ntu: number | null;
  tss_mgL: number | null;
  sdi15: number | null;

  // WAVE Organic Content
  toc_mgL: number | null;

  // UI preference
  feed_note?: string | null;
  charge_balance_mode?: ChargeBalanceMode | null;

  [k: string]: unknown;
};

export type PersistModel = {
  nodes: Node<FlowData>[];
  edges: Edge[];
  feed: FeedState;
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
// 5) Units & Utilities
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

export const fmt = (n: number | undefined | null, d = 2): string =>
  n == null || !Number.isFinite(Number(n)) ? '-' : Number(n).toFixed(d);

export const pct = (n: number | undefined | null, d = 1): string =>
  n == null || !Number.isFinite(Number(n)) ? '-' : `${Number(n).toFixed(d)}%`;

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
// 6) Legacy HRRO-only result type (kept for compatibility)
// ==========================================================

export type HRRORunOutput = {
  minutes: number;
  recovery_pct: number;
  V_loop_final_m3: number;
  C_loop_final_mgL: number;
  Qp_total_m3: number;
  Cp_mix_mgL: number;
  flux_lmh: number;
  ndp_bar: number;
  sec_kwhm3: number;
  jw_avg_lmh?: number;
  p_set_bar: number;
  avg_delta_pi_bar: number;
  bleed_total_m3: number;
  time_history: TimeSeriesPoint[];
  stage_metrics: any[];
  kpi?: {
    flux_lmh: number;
    ndp_bar: number;
    sec_kwhm3: number;
    recovery_pct: number;
  };
};
