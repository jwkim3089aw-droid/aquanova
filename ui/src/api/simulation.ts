// ui/src/api/simulation.ts
import { axiosInstance } from './client';
import { logger } from '../utils/logger';
import type {
  SimulationRequest,
  ScenarioOutput,
  ReportStatusResponse,
} from './types';

/**
 * 시뮬레이션 실행 (엔진 호출)
 */
export async function runSimulation(
  payload: SimulationRequest,
): Promise<ScenarioOutput> {
  // 🟢 [Fix] 원본 객체 직접 수정(Mutation) 방지!
  // 스프레드 연산자(...)를 사용해 안전한 복사본(safePayload)을 만들어 전송합니다.
  const safePayload: SimulationRequest = {
    ...payload,
    feed: payload.feed
      ? {
          ...payload.feed,
          dosing: payload.feed.dosing || {
            antiscalant_enabled: true,
            target_ph: payload.feed.ph ?? 7.0,
            acid_type: 'H2SO4',
            base_type: 'NaOH',
          },
        }
      : payload.feed,
  };

  logger.info('🚀 [API] POST /simulation/run', {
    id: safePayload.simulation_id,
    project: safePayload.project_id,
    stages: safePayload.stages?.map((s) => s.module_type),
    dosing: safePayload.feed?.dosing,
  });

  const response = await axiosInstance.post<ScenarioOutput>(
    '/simulation/run',
    safePayload,
  );

  return response.data;
}

/**
 * PDF 리포트 생성 작업 큐 등록
 */
export async function requestReportGeneration(
  scenarioId: string,
  outUnits: 'display' | 'metric' = 'display',
): Promise<string> {
  const response = await axiosInstance.post<{ job_id: string }>(
    '/reports/enqueue',
    { scenario_id: scenarioId },
    { params: { out_units: outUnits } },
  );
  return response.data.job_id;
}

/**
 * 리포트 생성 작업 상태 조회
 */
export async function getReportStatus(
  jobId: string,
): Promise<ReportStatusResponse> {
  const response = await axiosInstance.get<ReportStatusResponse>(
    `/reports/${jobId}`,
  );
  return response.data;
}

/**
 * 생성된 리포트 PDF 파일 다운로드 (Blob)
 */
export async function downloadReportBlob(jobId: string): Promise<Blob> {
  const response = await axiosInstance.get(`/reports/${jobId}/download`, {
    responseType: 'blob',
  });
  return response.data;
}

// ============================================================================
// 💾 Database Scenario Save & Load API
// ============================================================================

export interface CanvasSavePayload {
  scenario_id?: string;
  name: string;
  project_id?: string;
  canvas_state: any;
}

export interface ScenarioListItem {
  id: string;
  name: string;
  created_at: string;
  updated_at?: string;
}

/**
 * 1. 캔버스 상태를 DB에 저장 (또는 덮어쓰기)
 */
export async function saveScenarioToDB(
  payload: CanvasSavePayload,
): Promise<{ message: string; scenario_id: string }> {
  const response = await axiosInstance.post('/simulation/save', payload);
  return response.data;
}

/**
 * 2. DB에 저장된 시나리오 목록 불러오기
 */
export async function getScenariosFromDB(): Promise<ScenarioListItem[]> {
  const response = await axiosInstance.get('/simulation/scenarios');
  return response.data;
}

/**
 * 3. 특정 시나리오의 캔버스 데이터(JSON) 통째로 불러오기
 */
export async function getScenarioStateFromDB(
  id: string,
): Promise<{ id: string; name: string; canvas_state: any }> {
  const response = await axiosInstance.get(`/simulation/scenarios/${id}`);
  return response.data;
}

export async function deleteScenarioFromDB(
  id: string,
): Promise<{ message: string }> {
  const response = await axiosInstance.delete(`/simulation/scenarios/${id}`);
  return response.data;
}
