// ui\src\api\membranes.ts

import { axiosInstance } from './client';
import { MembraneSpec } from './types'; // types.ts에 MembraneSpec 정의가 필요합니다.

/**
 * [API] 멤브레인 목록 조회
 * GET /api/v1/membranes
 * @param stageType (선택) "RO", "NF", "UF" 등으로 필터링
 */
export const fetchMembranes = async (
  stageType?: string,
): Promise<MembraneSpec[]> => {
  const params: any = {};
  if (stageType) {
    // 백엔드는 "RO", "HRRO" 등을 받아서 family로 자동 변환함
    params.stage_type = stageType;
  }

  const response = await axiosInstance.get<MembraneSpec[]>('/membranes', {
    params,
  });
  return response.data;
};

/**
 * [API] 특정 멤브레인 상세 조회
 */
export const fetchMembraneDetail = async (
  id: string,
): Promise<MembraneSpec> => {
  const response = await axiosInstance.get<MembraneSpec>(`/membranes/${id}`);
  return response.data;
};
