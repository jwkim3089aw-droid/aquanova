// ui/src/features/simulation/results/pdf/types.ts
import { ScenarioOutput, StageMetric } from '../../../../../api/types';

export type ReportMode = 'SYSTEM' | 'STAGE';

export interface ReportProps {
  // ScenarioOutput 타입을 사용하여 데이터 구조 명확화
  data: ScenarioOutput | any;
  mode: ReportMode;
  elementProfile?: any[] | null;
}

export type UnitLabels = Partial<{
  flow: string;
  pressure: string;
  flux: string;
  temperature: string;
  power: string;
  concentration: string;
}>;
