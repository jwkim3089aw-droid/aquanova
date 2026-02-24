// ui/src/api/types.ts
// AquaNova API Contract (Synced with Backend Schema)

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

  enqueued_at?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
}

// ======================
// Sub-Models (Physics & Geometry)
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

  k_mt_multiplier?: number | null;
  k_mt_min_m_s?: number | null;
  segments_total?: number | null;

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
  // Cations
  NH4?: number | null;
  K?: number | null;
  Na?: number | null;
  Mg?: number | null;
  Ca?: number | null;
  Sr?: number | null;
  Ba?: number | null;

  // Anions
  CO2?: number | null;
  HCO2?: number | null;
  HCO3?: number | null;
  NO2?: number | null;
  NO3?: number | null;
  Cl?: number | null;
  F?: number | null;
  SO4?: number | null;
  PO4?: number | null;
  Br?: number | null;
  CO3?: number | null;

  // Neutrals
  SiO2?: number | null;
  B?: number | null;

  // Metals
  Fe?: number | null;
  Mn?: number | null;
  Al?: number | null; // 백엔드 매칭

  [k: string]: any;
}

// 🛑 [UF PATCH] WAVE 유지보수 및 세정 사이클 스펙 추가
export interface UFMaintenanceConfig {
  filtration_duration_min?: number | null;
  acid_ceb_interval_h?: number | null;
  alkali_ceb_interval_h?: number | null;
  cip_interval_d?: number | null;
  mini_cip_interval_d?: number | null;

  backwash_duration_sec?: number | null;
  air_scour_duration_sec?: number | null;
  forward_flush_duration_sec?: number | null;

  backwash_flux_lmh?: number | null;
  ceb_flux_lmh?: number | null;
  forward_flush_flow_m3h_per_mod?: number | null;
  air_flow_nm3h_per_mod?: number | null;

  integrity_test_min_day?: number | null;
}

// ======================
// 🛑 [WAVE FEED PATCH] Feed Water Types & Fouling Sub-Models
// ======================
export type WAVEWaterType =
  | 'RO/NF Well Water'
  | 'RO/NF Surface Water'
  | 'SD Seawater (Open Intake)'
  | 'SD Seawater (Well)'
  | 'WW Wastewater'
  | 'City Water'
  | (string & {});

export interface FoulingIndicators {
  tss_mgL?: number | null;
  turbidity_ntu?: number | null;
  sdi15?: number | null;
  toc_mgL?: number | null;
  cod_mgL?: number | null;
  bod_mgL?: number | null;
}

// ======================
// Main Configuration Inputs
// ======================

export interface FeedInput {
  // 1. Physical Properties
  water_type?: WAVEWaterType | null;
  flow_m3h: number;
  temperature_C: number;
  temp_min_C?: number | null;
  temp_max_C?: number | null;
  ph: number;
  pressure_bar?: number | null;

  // 2. Fouling & Organics
  fouling?: FoulingIndicators;

  // 3. Detailed Chemical Composition (이동 완료!)
  ions?: IonCompositionInput;
  tds_mgL: number;
  chemistry?: Record<string, any> | null;
}

export interface StageConfig {
  stage_id?: string | null;
  module_type: ModuleType;

  // --- 1. Physical Configuration (Hardware) ---
  element_inch?: number | null; // Default: 8
  vessel_count?: number | null; // Pressure Vessels per stage
  elements_per_vessel?: number | null; // Elements per PV
  elements: number; // Total Elements (vessel * per_vessel)

  // --- 2. Membrane Specifications ---
  membrane_model?: string | null;
  membrane_area_m2?: number | null;

  membrane_A_lmh_bar?: number | null; // Clean water permeability
  membrane_B_lmh?: number | null; // Salt passage
  membrane_salt_rejection_pct?: number | null;

  // Membrane Fouling / Aging
  flow_factor?: number | null; // Default: 0.85 (Aging Factor)

  // 🛑 [UF PATCH] Strainer Settings
  strainer_recovery_pct?: number | null;
  strainer_size_micron?: number | null;

  // --- 3. Operating Conditions ---
  feed_flow_m3h?: number | null;
  pressure_bar?: number | null; // Operating Pressure
  dp_module_bar?: number | null;

  // Recovery Targets
  recovery_target_pct?: number | null; // RO: Recovery / HRRO: Stop Recovery

  // Back Pressure & Safety Limits
  permeate_back_pressure_bar?: number | null;
  burst_pressure_limit_bar?: number | null;

  flux_lmh?: number | null; // Target Flux (Alternative control)
  design_flux_lmh?: number | null; // Target Filtrate Flux (UF)

  temp_mode?: 'Minimum' | 'Design' | 'Maximum' | null;
  bypass_flow_m3h?: number | null;
  pre_stage_dp_bar?: number | null;

  // --- 4. HRRO / CCRO Specifics ---
  loop_volume_m3?: number | null;
  recirc_flow_m3h?: number | null; // Concentrate Recycle Flow
  bleed_m3h?: number | null;

  // Batch Cycle Control
  timestep_s?: number | null;
  max_minutes?: number | null;
  stop_permeate_tds_mgL?: number | null;
  stop_recovery_pct?: number | null; // Explicit stop condition

  // Physics Sub-models
  mass_transfer?: HRROMassTransferIn | null;
  spacer?: HRROSpacerIn | null;

  // 🛑 [UF PATCH] Maintenance Nested Model
  uf_maintenance?: UFMaintenanceConfig | null;

  // --- 5. Other / Legacy ---
  pf_feed_ratio_pct?: number | null;
  pf_recovery_pct?: number | null;
  cc_recycle_m3h_per_pv?: number | null;
  membrane_area_m2_per_element?: number | null;
  pump_eff?: number | null;
  ccro_recovery_pct?: number | null;

  // UF/MF Backwash (Legacy, kept for fallback)
  filtration_cycle_min?: number | null;
  backwash_duration_sec?: number | null;
  backwash_flux_multiplier?: number | null;
  backwash_flux_lmh?: number | null;

  chemistry?: Record<string, any> | null;

  [k: string]: any;
}

export interface SimulationRequest {
  simulation_id: string;
  project_id?: string;
  scenario_name?: string;

  feed: FeedInput; // 이제 ions와 fouling이 feed 내부에 모두 포함됨
  stages: StageConfig[];

  options?: Record<string, any>;
  chemistry?: WaterChemistryInput | null;
}

// ======================
// Outputs & Results
// ======================

export interface SimulationWarning {
  stage?: string | null;
  module_type?: string | null;
  key: string;
  message: string;
  value?: number | null;
  limit?: any | null;
  unit: string;
  level: string;
}

export interface MassBalanceOut {
  flow_error_m3h: number;
  flow_error_pct: number;
  salt_error_kgh: number;
  salt_error_pct: number;
  system_rejection_pct?: number | null;
  is_balanced: boolean;
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
  specific_energy_kwh_m3?: number | null;
}

export interface ScalingIndexOut {
  lsi?: number | null;
  rsi?: number | null;
  s_dsi?: number | null;
  caco3_si?: number | null;
  caso4_si?: number | null;
  baso4_si?: number | null;
  srso4_si?: number | null;
  caf2_si?: number | null;
  sio2_si?: number | null;
  caso4_sat_pct?: number | null;
  baso4_sat_pct?: number | null;
  sio2_sat_pct?: number | null;
  [k: string]: any;
}

export interface WaterChemistryOut {
  feed?: ScalingIndexOut | null;
  final_brine?: ScalingIndexOut | null;
}

export interface StageMetric {
  stage: number;
  module_type: ModuleType;

  // KPIs
  recovery_pct?: number | null;
  flux_lmh?: number | null;

  // 🛑 [UF PATCH] Extended Flux metrics
  design_flux_lmh?: number | null;
  instantaneous_flux_lmh?: number | null;
  average_flux_lmh?: number | null;

  sec_kwhm3?: number | null;
  ndp_bar?: number | null;

  // Pressures
  p_in_bar?: number | null;
  p_out_bar?: number | null;
  dp_bar?: number | null;
  tmp_bar?: number | null;
  delta_pi_bar?: number | null;

  // Flows
  Qf?: number | null;
  Qp?: number | null;
  Qc?: number | null;

  gross_flow_m3h?: number | null;
  net_flow_m3h?: number | null;
  backwash_loss_m3h?: number | null;
  net_recovery_pct?: number | null;

  // Concentration
  Cf?: number | null;
  Cp?: number | null;
  Cc?: number | null;

  time_history?: TimeSeriesPoint[] | null;
  chemistry?: any;
  warnings?: SimulationWarning[] | null;

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

  batchcycle?: number | null;
  prod_tds?: number | null;
  feed_m3h?: number | null;
  permeate_m3h?: number | null;
  mass_balance?: MassBalanceOut | null;
}

export interface ScenarioOutput {
  scenario_id: string;

  streams: StreamOut[];
  kpi: KPIOut;

  stage_metrics?: StageMetric[] | null;
  unit_labels?: Record<string, string> | null;

  chemistry?: WaterChemistryOut | any;
  time_history?: TimeSeriesPoint[] | null;
  warnings?: SimulationWarning[] | null;

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
