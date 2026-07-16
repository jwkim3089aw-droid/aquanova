// ui/src/features/simulation/model/types.ts

import type { CSSProperties, Dispatch, SetStateAction } from 'react';
import type { Node, Edge } from 'reactflow';
import type { TimeSeriesPoint } from '@/api/types';
import type { ChargeBalanceMode } from '../chemistry';

export type UnitKind = 'RO' | 'NF' | 'UF' | 'MF' | 'HRRO' | 'PUMP';

export type WaterType =
  | 'RO/NF Well Water'
  | 'RO/NF Surface Water'
  | 'SD Seawater (Open Intake)'
  | 'SD Seawater (Well)'
  | 'WW Wastewater'
  | 'City Water';

export type BaseMembraneConfig = {
  membrane_mode?: 'catalog' | 'custom';
  membrane_model?: string;
  custom_area_m2?: number;
  custom_A_lmh_bar?: number;
  custom_B_lmh?: number;
  custom_salt_rejection_pct?: number;
  enable_pump?: boolean;
  pump_pressure_bar?: number;
  pump_eff?: number;
};

export type MembraneStageConfig = {
  stage_idx: number;
  vessel_count: number;
  elements_per_vessel: number;
  elements: number;
  flow_factor: number;
  spi: number;
  pre_stage_dp_bar: number;
  isbp_pressure_bar: number;
  isbp_eff_pct: number;
  [k: string]: any;
};

export type ROConfig = BaseMembraneConfig & {
  num_stages: number;
  stages: MembraneStageConfig[];
  mode: 'pressure' | 'recovery' | 'flow';
  pressure_bar?: number;
  recovery_target_pct?: number;
  flow_target_m3h?: number;
  permeate_back_pressure_bar?: number;
  max_tmp_bar?: number;
  age_years?: number;
  elements?: number;
  vessel_count?: number;
  elements_per_vessel?: number;
  flow_factor?: number;
  spi?: number;
  pre_stage_dp_bar?: number;
  [k: string]: any;
};

export type NFConfig = BaseMembraneConfig & {
  num_stages: number;
  stages: MembraneStageConfig[];
  mode: 'pressure' | 'recovery' | 'flow';
  pressure_bar?: number;
  recovery_target_pct?: number;
  flow_target_m3h?: number;
  permeate_back_pressure_bar?: number;
  max_tmp_bar?: number;
  age_years?: number;
  elements?: number;
  vessel_count?: number;
  elements_per_vessel?: number;
  flow_factor?: number;
  spi?: number;
  pre_stage_dp_bar?: number;
  [k: string]: any;
};

export type UFMaintenanceConfig = {
  filtration_duration_min?: number;
  acid_ceb_interval_h?: number;
  alkali_ceb_interval_h?: number;
  cip_interval_d?: number;
  mini_cip_interval_d?: number;

  backwash_duration_sec?: number;
  drain_duration_sec?: number;
  top_backwash_duration_sec?: number;
  bottom_backwash_duration_sec?: number;
  air_scour_duration_sec?: number;
  forward_flush_duration_sec?: number;

  backwash_flux_lmh?: number;
  ceb_flux_lmh?: number;
  forward_flush_flow_m3h_per_mod?: number;
  air_flow_nm3h_per_mod?: number;

  ceb_soaking_min?: number;
  cip_heating_min?: number;

  power_plc_kw?: number;
  power_valve_kw?: number;
  valves_per_train?: number;
  valve_action_sec?: number;

  air_scour_pressure_bar?: number;
  filtrate_pressure_bar?: number;
  filtration_piping_dp_bar?: number;
  strainer_dp_bar?: number;
  backwash_piping_dp_bar?: number;
  cip_piping_dp_bar?: number;

  integrity_test_min_day?: number;
};

export type UFConfig = BaseMembraneConfig & {
  elements: number;
  design_flux_lmh?: number;
  recovery_target_pct?: number;
  max_tmp_bar?: number;
  uf_permeability_25c_lmh_bar?: number;
  uf_p_out_bar?: number;
  uf_header_loss_bar?: number;
  uf_maintenance?: UFMaintenanceConfig;
  [k: string]: any;
};

export type MFConfig = BaseMembraneConfig & {
  elements: number;
  flux_lmh?: number;
  recovery_target_pct?: number;
  max_tmp_bar?: number;
  filtration_cycle_min?: number;
  backwash_duration_sec?: number;
  backwash_flux_lmh?: number;
  mf_cip_loss_factor?: number;
  mf_permeability_25c_lmh_bar?: number;
  mf_p_out_bar?: number;
  mf_header_loss_bar?: number;
  [k: string]: any;
};

export type HRROSpacerIn = {
  thickness_mm?: number;
  voidage?: number;
  hydraulic_diameter_m?: number;
};

export type HRROMassTransferIn = {
  feed_channel_area_m2?: number;
  diffusivity_m2_s?: number;
};

export type HRROPFMode =
  | 'wave_true_plug_flow'
  | 'smart_partial_drain'
  | 'field_optimized_low_fr';

export type HRROConfig = BaseMembraneConfig & {
  elements: number;
  vessel_count?: number;
  elements_per_vessel?: number;
  ccro_recovery_pct?: number;
  recirc_flow_m3h?: number;
  cc_recycle_m3h_per_pv?: number;
  loop_volume_m3?: number;
  timestep_s?: number;
  max_minutes?: number;
  max_tmp_bar?: number;
  hrro_B_sal_slope?: number;
  hrro_A_compaction_k?: number;
  permeate_back_pressure_bar?: number;

  // V83: UI-facing controls for V82 smart partial-drain PF/adaptive cycle model
  pf_mode?: HRROPFMode;
  brine_valve_mode?: 'full_open' | 'partial_pid' | string;
  pf_feed_ratio_pct?: number;
  pf_recovery_pct?: number;
  p3_recycle_capacity_m3h_per_pv?: number;
  pf_cp_assist_enabled?: boolean;
  pf_cp_assist_flow_m3h_per_pv?: number;
  adaptive_recovery_enabled?: boolean;
  brine_conductivity_limit_mgL?: number;
  brine_tds_limit_mgL?: number;
  hpp_safe_pressure_limit_bar?: number;
  hpp_sizing_mode?: 'base' | 'step1' | 'step2';
  hpp_count?: number;
  p3_generated_head_bar?: number;
  p3_casing_pressure_rating_bar?: number;

  spacer?: HRROSpacerIn;
  mass_transfer?: HRROMassTransferIn;
  [k: string]: any;
};

export type PumpConfig = {
  mode: 'fixed_pressure' | 'boost_pressure';
  pressure_bar: number;
  pump_eff?: number;
};

export type OLConfig = ROConfig | NFConfig | UFConfig | MFConfig;
export type AnyUnitConfig = OLConfig | HRROConfig;

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
  co3_mgL?: number | null;
  hco3_mgL?: number | null;
  no3_mgL?: number | null;
  cl_mgL?: number | null;
  f_mgL?: number | null;
  so4_mgL?: number | null;
  br_mgL?: number | null;
  po4_mgL?: number | null;
  sio2_mgL?: number | null;
  b_mgL?: number | null;
  co2_mgL?: number | null;
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

export type FeedState = {
  flow_m3h: number;
  tds_mgL: number;
  ph: number;
  pressure_bar?: number;
  temperature_C: number;
  temp_min_C: number | null;
  temp_max_C: number | null;
  water_type?: WaterType | null;
  water_subtype?: string | null;
  fouling: {
    turbidity_ntu: number | null;
    tss_mgL: number | null;
    sdi15: number | null;
    toc_mgL: number | null;
    cod_mgL: number | null;
    bod_mgL: number | null;
  };
  feed_note?: string | null;
  charge_balance_mode?: ChargeBalanceMode | null;
  [k: string]: unknown;
};

export type OpexState = {
  electricity_price_kwh: number;
  antiscalant_price_kg: number;
  acid_base_price_kg: number;
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
  opex?: OpexState;
};

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
