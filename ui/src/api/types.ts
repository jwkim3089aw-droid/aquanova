// ui\src\api\types.ts
// ui/src/api/types.ts

// ==========================================
// 1. Request Types (Client -> Server)
// ==========================================

export interface StageConfig {
  stage_id?: string;
  module_type: string; // "RO" | "HRRO" | "NF" | "UF" | "MF"
  elements: number;

  // Basic Operating Conditions
  pressure_bar?: number;
  recovery_target_pct?: number;

  // Membrane Specs
  membrane_model?: string;
  membrane_area_m2?: number;
  membrane_A_lmh_bar?: number;
  membrane_B_lmh?: number;
  membrane_salt_rejection_pct?: number;

  // ✅ [FIX] HRRO Critical Control Parameters
  // 110% 폭주 방지를 위한 종료 트리거 명시
  stop_recovery_pct?: number;
  stop_permeate_tds_mgL?: number;
  loop_volume_m3?: number;
  recirc_flow_m3h?: number;
  bleed_m3h?: number;
  max_minutes?: number;
  timestep_s?: number;

  // UF/MF Specifics
  filtration_cycle_min?: number;
  backwash_duration_sec?: number;
  flux_lmh?: number;
  backwash_flux_lmh?: number;

  // Allow extra props for flexibility
  [key: string]: any;
}

export interface FeedInput {
  flow_m3h: number;
  tds_mgL: number;
  temperature_C: number;
  ph: number;
}

export interface SimulationRequest {
  simulation_id: string;
  project_id?: string;
  feed: FeedInput;
  stages: StageConfig[];
}

// ==========================================
// 2. Response Types (Server -> Client)
// ==========================================

export interface TimeSeriesPoint {
  time_min: number;
  recovery_pct: number;
  pressure_bar: number;
  tds_mgL: number;
  flux_lmh?: number;
  ndp_bar?: number;
  permeate_flow_m3h?: number;
  permeate_tds_mgL?: number;
}

export interface StageMetric {
  stage: number;
  module_type: string;

  // Key Performance Indicators
  p_in_bar?: number;
  p_out_bar?: number;
  sec_kwhm3?: number;
  jw_avg_lmh?: number;
  ndp_bar?: number;
  recovery_pct?: number;

  // Mass Balance
  Qf?: number;
  Qp?: number;
  Qc?: number;
  Cf?: number;
  Cp?: number;
  Cc?: number;

  // UF/MF Metrics
  gross_flow_m3h?: number;
  net_flow_m3h?: number;
  backwash_loss_m3h?: number;
  net_recovery_pct?: number;

  // Time Series Data
  time_history?: TimeSeriesPoint[];
}

export interface ScenarioOutput {
  scenario_id: string;
  streams: any[];
  kpi: {
    recovery_pct: number;
    flux_lmh: number;
    ndp_bar: number;
    sec_kwhm3: number;
    prod_tds?: number;
    permeate_m3h?: number;
  };
  stage_metrics?: StageMetric[];
  time_history?: TimeSeriesPoint[];
  chemistry?: any;
}

export interface MembraneSpec {
  id: string;
  name: string;
  vendor?: string;
  area_m2?: number;
  A_lmh_bar?: number;
  B_mps?: number;
  salt_rejection_pct?: number;
}
