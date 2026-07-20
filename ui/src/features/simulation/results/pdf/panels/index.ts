// ui/src/features/simulation/results/pdf/panels/index.ts

// --- 1. 시스템 개요 및 밸런스 (System Overview & Balance) ---
export * from './TrainOverviewPanel';
export * from './BalancePanel';
export * from './SystemBalanceChart';
export * from './StageWaterQualityPanel';
export * from './DistributionSummaryPanel';
export * from './SystemWarningsPanel';

// --- 2. HRRO 특화 데이터 (HRRO Specific) ---
export * from './HRROCoreStatusTable';
export * from './HRROProcessFlowPanel';
export * from './HRROHistoryChart';
export * from './HistoryStatsTable';
export * from './TimeHistoryTable';

// --- 3. 스테이지 및 엘리먼트 상세 (Stage & Element Details) ---
export * from './ElementProfilePanel';
export * from './UfDetailsPanel';

// --- 4. 수화학, 스케일링 및 약품 투입 (Chemistry, Scaling & Dosing) ---
export * from './BrineScalingPanel';
export * from './ChemicalDosingPanel';

// --- 5. 경제성 평가 (Economics & OPEX) ---
export * from './OpexSummaryPanel';
