// ui/src/api/simulation.ts
import { axiosInstance } from './client';
import type {
  SimulationRequest,
  ScenarioOutput,
  ReportStatusResponse,
} from './types';

export async function runSimulation(
  payload: SimulationRequest,
): Promise<ScenarioOutput> {
  console.log('🚀 [API] POST /simulation/run', {
    simulation_id: payload.simulation_id,
    project_id: payload.project_id,
    scenario_name: payload.scenario_name,
    stages: payload.stages?.map((s) => s.module_type),
  });

  const response = await axiosInstance.post<ScenarioOutput>(
    '/simulation/run',
    payload,
  );
  return response.data;
}

// ============================================================
// Report Generation & Download
// ============================================================

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

export async function getReportStatus(
  jobId: string,
): Promise<ReportStatusResponse> {
  const response = await axiosInstance.get<ReportStatusResponse>(
    `/reports/${jobId}`,
  );
  return response.data;
}

export async function downloadReportBlob(jobId: string): Promise<Blob> {
  const response = await axiosInstance.get(`/reports/${jobId}/download`, {
    responseType: 'blob',
  });
  return response.data;
}
