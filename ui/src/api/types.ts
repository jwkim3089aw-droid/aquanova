// ui/src/api/types.ts

// ==========================================
// 1. Request Types (보내는 데이터)
// ==========================================

export interface StageConfig {
  stage_id?: string;
  // 백엔드 Enum: "RO" | "HRRO" | "NF" | "UF" | "MF"
  module_type: string;
  elements: number;
  pressure_bar?: number;
  recovery_target_pct?: number;

  // 막(Membrane) 정보
  membrane_model?: string;
  membrane_area_m2?: number;
  membrane_A_lmh_bar?: number;
  membrane_B_lmh?: number;
  membrane_salt_rejection_pct?: number;

  // 기타 속성 (HRRO, UF 등)
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
// 2. Response Types (받는 데이터)
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

  // 주요 운전 지표
  p_in_bar?: number;
  p_out_bar?: number;
  sec_kwhm3?: number;
  jw_avg_lmh?: number; // flux
  ndp_bar?: number;
  recovery_pct?: number;

  // 유량 밸런스
  Qf?: number;
  Qp?: number;
  Qc?: number;
  Cf?: number;
  Cp?: number;
  Cc?: number;

  // 그래프 데이터
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
  time_history?: TimeSeriesPoint[]; // Root level history
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
