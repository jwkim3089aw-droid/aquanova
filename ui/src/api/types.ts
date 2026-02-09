// ui/src/api/types.ts
// AquaNova API Contract (synced with backend schemas 2026-02-03)

export type ModuleType =
  | 'RO'
  | 'NF'
  | 'UF'
  | 'MF'
  | 'HRRO'
  | 'PRO'
  | (string & {});

// ======================
// Report Job Status
// ======================
export type ReportJobStatus = 'queued' | 'started' | 'succeeded' | 'failed';

export interface ReportStatusResponse {
  job_id: string;
  status: ReportJobStatus;

  error_message?: string | null;
  artifact_path?: string | null;

  // ✅ backend schema와 맞추기 (있어도 되고 없어도 됨)
  enqueued_at?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
}

// ======================
// (이하 기존 너가 올린 타입들 그대로 유지)
// ======================

export interface HRROMassTransferIn {
  crossflow_velocity_m_s?: number | null;
  recirc_flow_m3h?: number | null;
  feed_channel_area_m2?: number | null;
  rho_kg_m3?: number | null;
  mu_pa_s?: number | null;
  diffusivity_m2_s?: number | null;
  cp_exp_max?: number | null;
  cp_rel_tol?: number | null;
  cp_abs_tol_lmh?: number | null;
  cp_relax?: number | null;
  cp_max_iter?: number | null;
  [k: string]: any;
}

export interface HRROSpacerIn {
  thickness_mm?: number | null;
  filament_diameter_mm?: number | null;
  mesh_size_mm?: number | null;
  voidage?: number | null;
  voidage_fallback?: number | null;
  hydraulic_diameter_m?: number | null;
  [k: string]: any;
}

export interface WaterChemistryInput {
  alkalinity_mgL_as_CaCO3?: number | null;
  calcium_hardness_mgL_as_CaCO3?: number | null;
  sulfate_mgL?: number | null;
  barium_mgL?: number | null;
  strontium_mgL?: number | null;
  silica_mgL_SiO2?: number | null;
}

export interface IonCompositionInput {
  NH4?: number | null;
  K?: number | null;
  Na?: number | null;
  Mg?: number | null;
  Ca?: number | null;
  Sr?: number | null;
  Ba?: number | null;

  CO2?: number | null;
  HCO2?: number | null;
  HCO3?: number | null;

  NO3?: number | null;
  CO3?: number | null;

  NO2?: number | null;

  Cl?: number | null;
  F?: number | null;
  SO4?: number | null;
  PO4?: number | null;
  Br?: number | null;

  SiO2?: number | null;
  B?: number | null;

  Fe?: number | null;
  Mn?: number | null;

  [k: string]: any;
}

export interface FeedInput {
  flow_m3h: number;
  tds_mgL: number;
  temperature_C: number;
  ph: number;
  pressure_bar?: number | null;

  water_type?: string | null;
  water_subtype?: string | null;
  turbidity_ntu?: number | null;
  tss_mgL?: number | null;
  sdi15?: number | null;
  toc_mgL?: number | null;

  chemistry?: Record<string, any> | null;
}

export interface StageConfig {
  stage_id?: string | null;
  module_type: ModuleType;
  elements: number;

  pressure_bar?: number | null;
  recovery_target_pct?: number | null;
  flux_lmh?: number | null;

  membrane_model?: string | null;
  membrane_area_m2?: number | null;
  membrane_A_lmh_bar?: number | null;
  membrane_B_lmh?: number | null;
  membrane_salt_rejection_pct?: number | null;

  loop_volume_m3?: number | null;
  recirc_flow_m3h?: number | null;
  bleed_m3h?: number | null;
  timestep_s?: number | null;
  max_minutes?: number | null;
  stop_permeate_tds_mgL?: number | null;
  stop_recovery_pct?: number | null;

  mass_transfer?: HRROMassTransferIn | null;
  spacer?: HRROSpacerIn | null;

  filtration_cycle_min?: number | null;
  backwash_duration_sec?: number | null;
  backwash_flux_multiplier?: number | null;
  backwash_flux_lmh?: number | null;

  chemistry?: Record<string, any> | null;

  hrro_engine?: 'excel_only' | 'excel_physics';
  hrro_excel_only_cp_mode?: 'min_model' | 'none' | 'fixed_rejection';
  hrro_excel_only_fixed_rejection_pct?: number | null;
  hrro_excel_only_min_model_rejection_pct?: number | null;

  element_inch?: number | null;
  vessel_count?: number | null;
  elements_per_vessel?: number | null;

  feed_flow_m3h?: number | null;
  ccro_recovery_pct?: number | null;

  pf_feed_ratio_pct?: number | null;
  pf_recovery_pct?: number | null;

  cc_recycle_m3h_per_pv?: number | null;
  membrane_area_m2_per_element?: number | null;

  pump_eff?: number | null;

  [k: string]: any;
}

export interface SimulationRequest {
  simulation_id: string;
  project_id?: string;
  scenario_name?: string;

  feed: FeedInput;
  stages: StageConfig[];

  options?: Record<string, any>;

  chemistry?: WaterChemistryInput | null;
  ions?: IonCompositionInput | null;
}

export interface TimeSeriesPoint {
  time_min: number;
  recovery_pct: number;

  pressure_bar: number;
  tds_mgL: number;

  flux_lmh?: number | null;
  ndp_bar?: number | null;
  permeate_flow_m3h?: number | null;
  permeate_tds_mgL?: number | null;
}

export interface ScalingIndexOut {
  lsi?: number | null;
  rsi?: number | null;
  s_dsi?: number | null;
  caco3_si?: number | null;
  caso4_si?: number | null;
  sio2_si?: number | null;
  [k: string]: any;
}

export interface WaterChemistryOut {
  feed?: ScalingIndexOut | null;
  final_brine?: ScalingIndexOut | null;
}

export interface StageMetric {
  stage: number;
  module_type: ModuleType;

  recovery_pct?: number | null;

  flux_lmh?: number | null;
  sec_kwhm3?: number | null;

  ndp_bar?: number | null;
  p_in_bar?: number | null;
  p_out_bar?: number | null;
  delta_pi_bar?: number | null;

  Qf?: number | null;
  Qp?: number | null;
  Qc?: number | null;

  Cf?: number | null;
  Cp?: number | null;
  Cc?: number | null;

  gross_flow_m3h?: number | null;
  net_flow_m3h?: number | null;
  backwash_loss_m3h?: number | null;
  net_recovery_pct?: number | null;

  time_history?: TimeSeriesPoint[] | null;

  chemistry?: any;

  [k: string]: any;
}

export interface StreamOut {
  label: 'Feed' | 'Product' | 'Brine' | (string & {});
  flow_m3h: number;
  tds_mgL: number;
  ph: number;
  pressure_bar: number;
}

export interface KPIOut {
  recovery_pct: number;
  flux_lmh: number;
  ndp_bar: number;
  sec_kwhm3: number;

  prod_tds?: number | null;
  feed_m3h?: number | null;
  permeate_m3h?: number | null;
}

export interface ScenarioOutput {
  scenario_id: string;

  streams: StreamOut[];
  kpi: KPIOut;

  stage_metrics?: StageMetric[] | null;
  unit_labels?: Record<string, string> | null;

  chemistry?: WaterChemistryOut | any;
  time_history?: TimeSeriesPoint[] | null;

  schema_version?: number;
}

export interface MembraneSpec {
  id: string;
  name?: string;
  vendor?: string;
  area_m2?: number;
  A_lmh_bar?: number;
  B_mps?: number;
  salt_rejection_pct?: number;
}
