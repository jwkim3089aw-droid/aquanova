// ui/src/features/simulation/results/pdf/types.ts
export type ReportMode = 'SYSTEM' | 'STAGE';

export interface ReportProps {
  data: any;
  mode: ReportMode;
  elementProfile?: any[] | null;
}

export type UnitLabels = Partial<{
  flow: string;
  pressure: string;
  flux: string;
  temperature: string;
}>;
