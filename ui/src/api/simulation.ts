// ui/src/api/simulation.ts
import { axiosInstance } from './client';
import { SimulationRequest, ScenarioOutput } from './types';

// ============================================================
// 1. Simulation Execution
// ============================================================

/**
 * [통합 시뮬레이션 실행]
 * RO, HRRO, NF, UF, MF 구분 없이 이 함수 하나만 사용합니다.
 * 백엔드 엔드포인트: POST /api/v1/simulation/run
 */
export const runSimulation = async (
  payload: SimulationRequest,
): Promise<ScenarioOutput> => {
  // 디버깅용 로그
  console.log('🚀 [API] Sending Request:', {
    id: payload.simulation_id,
    type: payload.stages[0]?.module_type,
    payload,
  });

  const response = await axiosInstance.post<ScenarioOutput>(
    '/simulation/run',
    payload,
  );

  return response.data;
};

// ============================================================
// 2. Report Generation & Download
// ============================================================

export interface ReportStatusResponse {
  job_id: string;
  status: 'queued' | 'started' | 'succeeded' | 'failed';
  error_message?: string | null;
  artifact_path?: string | null;
  finished_at?: string | null;
}

/**
 * [리포트 생성 요청]
 * 백엔드 큐(Redis)에 작업을 등록하고 Job ID를 받습니다.
 */
export const requestReportGeneration = async (
  scenarioId: string,
  outUnits: 'display' | 'metric' = 'display', // display: LMH, bar / metric: m/s, Pa
): Promise<string> => {
  const response = await axiosInstance.post<{ job_id: string }>(
    '/reports/enqueue',
    { scenario_id: scenarioId }, // Body
    { params: { out_units: outUnits } }, // Query Params
  );
  return response.data.job_id;
};

/**
 * [리포트 상태 폴링]
 * 작업이 완료되었는지 확인합니다.
 */
export const getReportStatus = async (
  jobId: string,
): Promise<ReportStatusResponse> => {
  const response = await axiosInstance.get<ReportStatusResponse>(
    `/reports/${jobId}`,
  );
  return response.data;
};

/**
 * [PDF 파일 다운로드]
 * Blob 형태로 바이너리 데이터를 받아옵니다.
 */
export const downloadReportBlob = async (jobId: string): Promise<Blob> => {
  const response = await axiosInstance.get(`/reports/${jobId}/download`, {
    responseType: 'blob', // ⚠️ 중요: PDF 바이너리를 받기 위한 설정
  });
  return response.data;
};
