// ui/src/features/simulation/results/pdf/ReportTemplate.tsx
import React from 'react';
import {
  Activity,
  Droplets,
  Zap,
  Gauge,
  FlaskConical,
  ShieldAlert,
  Clock,
  Database,
  FileText,
  GitBranch,
  AlertTriangle,
  BarChart3,
  ListChecks,
  Layers,
  Waves,
} from 'lucide-react';

import { ReportProps } from './types';
import { THEME } from './theme';
import { safeArr, safeObj } from './utils';

import {
  Page,
  Section,
  Badge,
  KPI,
  KVGrid,
  JsonDetails,
  StreamTable,
  StageSummaryTable,
  ViolationsTable,
  ViolationsSummary,
} from './components';

import {
  TrainOverviewPanel,
  BalancePanel,
  SystemBalanceChart,
  StageWaterQualityPanel,
  DistributionSummaryPanel,
  SystemWarningsPanel,
  ElementProfilePanel,
  HRROCoreStatusTable,
  HRROHistoryChart,
  HistoryStatsTable,
  TimeHistoryTable,
  BrineScalingPanel, // ✅ 새로 추가된 패널 Import
} from './panels';

type UnitBag = {
  flow: string;
  pressure: string;
  temperature: string;
  flux: string;
};

const upper = (v: any) => String(v ?? '').toUpperCase();
const notNil = (v: any) => v !== null && v !== undefined;

export const ReportTemplate = React.forwardRef<HTMLDivElement, ReportProps>(
  ({ data, mode, elementProfile }, ref) => {
    const safeData = data || {};
    const kpi = safeObj(safeData.kpi);
    const stages = safeArr(safeData.stage_metrics);

    const unitLabels = safeObj(safeData.unit_labels);
    const u: UnitBag = {
      flow: unitLabels.flow ?? 'm³/h',
      pressure: unitLabels.pressure ?? 'bar',
      temperature: unitLabels.temperature ?? '°C',
      flux: unitLabels.flux ?? 'LMH',
    };

    const streams = safeArr(safeData.streams);
    const streamByLabel = (label: string) =>
      streams.find(
        (s) => String(s?.label ?? '').toLowerCase() === label.toLowerCase(),
      ) || {};

    const feed = streamByLabel('Feed');
    const perm = streamByLabel('Product') || streamByLabel('Permeate');
    const brine = streamByLabel('Brine') || streamByLabel('Concentrate');

    const system = {
      recovery_pct: kpi.recovery_pct ?? 0,
      sec_kwhm3: kpi.sec_kwhm3 ?? kpi.sec_kwh_m3 ?? 0,
      flux_lmh: kpi.flux_lmh ?? kpi.jw_avg_lmh ?? 0,
      ndp_bar: kpi.ndp_bar ?? 0,
      prod_tds: kpi.prod_tds ?? null,
      feed_m3h: kpi.feed_m3h ?? null,
      permeate_m3h: kpi.permeate_m3h ?? null,
    };

    const stageData = stages.map((s: any, idx: number) => {
      const flux = s?.flux_lmh ?? s?.jw_avg_lmh ?? null;
      return {
        stage: s?.stage ?? idx + 1,
        flux,
        ndp: s?.ndp_bar ?? null,
        type: s?.module_type ?? 'RO',
      };
    });

    const title = safeData.customTitle || 'AquaNova Report';
    const scenarioId = safeData.scenario_id || safeData.id || 'N/A';
    const createdAt = safeData.createdAtISO || safeData.created_at || null;
    const dateText = createdAt
      ? new Date(createdAt).toLocaleString()
      : new Date().toLocaleString();
    const schemaVersion = safeData.schema_version ?? null;

    // --- stage type counts (for cover note) ---
    const countByType = stages.reduce<Record<string, number>>((acc, s) => {
      const t = upper(s?.module_type || 'UNKNOWN');
      acc[t] = (acc[t] ?? 0) + 1;
      return acc;
    }, {});
    const ufCount = countByType['UF'] ?? 0;
    const hrroCount = countByType['HRRO'] ?? 0;

    // =========================
    // Page 1 (Cover)
    // =========================
    const page1 = (
      <Page key="page-1">
        <div className="flex items-end justify-between mb-6">
          <div>
            <div className={THEME.H2}>DETAILED REPORT</div>
            <h1 className={THEME.H1}>{title}</h1>
          </div>

          <div className="text-right text-[10px] text-slate-500 font-mono">
            Scenario: {scenarioId}
            <br />
            Date: {dateText}
            {schemaVersion != null ? (
              <>
                <br />
                Schema: {schemaVersion}
              </>
            ) : null}
          </div>
        </div>

        <div className="grid grid-cols-4 gap-3 mb-6">
          <KPI
            labelKo="회수율"
            valueText={`${system.recovery_pct}%`}
            hint="Recovery (%)"
            icon={<Droplets className="w-6 h-6" />}
            tone="blue"
          />
          <KPI
            labelKo="비에너지"
            valueText={`${system.sec_kwhm3} kWh/m³`}
            hint="Specific Energy"
            icon={<Zap className="w-6 h-6" />}
            tone="amber"
          />
          <KPI
            labelKo="평균 플럭스"
            valueText={`${system.flux_lmh} ${u.flux}`}
            hint="Flux"
            icon={<Activity className="w-6 h-6" />}
            tone="emerald"
          />
          <KPI
            labelKo="NDP"
            valueText={`${system.ndp_bar} ${u.pressure}`}
            hint="Net Driving Pressure"
            icon={<Gauge className="w-6 h-6" />}
            tone="slate"
          />
        </div>

        <Section
          title="Train Overview"
          icon={<GitBranch className="w-4 h-4 opacity-70" />}
          right={
            <Badge
              text={`${stages.length} stages`}
              tone={stages.length ? 'blue' : 'slate'}
            />
          }
        >
          <TrainOverviewPanel stages={stages} />
        </Section>

        <div className="h-4" />

        <Section
          title="추가 KPI"
          icon={<FlaskConical className="w-4 h-4 opacity-70" />}
        >
          <KVGrid
            cols={3}
            items={[
              { k: '제품 TDS', v: system.prod_tds, unit: 'mg/L' },
              { k: 'Feed 유량', v: system.feed_m3h, unit: u.flow },
              { k: '생산수 유량', v: system.permeate_m3h, unit: u.flow },
            ]}
          />
        </Section>

        <div className="h-4" />

        <Section
          title="스트림 요약"
          icon={<Droplets className="w-4 h-4 opacity-70" />}
          right={
            <div className={THEME.MUTED}>
              units: flow={u.flow}, pressure={u.pressure}, flux={u.flux}
            </div>
          }
        >
          <StreamTable feed={feed} perm={perm} brine={brine} u={u} />
        </Section>

        <div className="h-4" />

        <Section
          title="Mass & Salt Balance"
          icon={<ListChecks className="w-4 h-4 opacity-70" />}
        >
          {/* ✅ 백엔드에서 받아온 kpi.mass_balance를 BalancePanel로 넘겨줌 */}
          <BalancePanel feed={feed} perm={perm} brine={brine} kpi={kpi} u={u} />
        </Section>

        <div className="mt-4 text-[10px] text-slate-500">
          UF 스테이지 {ufCount}개 / HRRO 스테이지 {hrroCount}개 포함되어
          있습니다. (아래 페이지에 스테이지별 상세 표시)
        </div>
      </Page>
    );

    // =========================
    // Page 2 (System detail)
    // =========================
    const page2 = (
      <Page key="page-2" breakBefore>
        <div className="flex items-end justify-between mb-4">
          <div>
            <div className={THEME.H2}>SYSTEM DETAILS</div>
            <div className="text-2xl font-black text-slate-900">
              스테이지 성능(요약)
            </div>
          </div>
          <div className="text-right text-[10px] text-slate-500 font-mono">
            Scenario: {scenarioId}
          </div>
        </div>

        <Section
          title="스테이지 테이블"
          icon={<Activity className="w-4 h-4 opacity-70" />}
          right={
            <Badge
              text={`${stages.length} stages`}
              tone={stages.length ? 'blue' : 'slate'}
            />
          }
        >
          {!stages.length ? (
            <div className="text-[10px] text-slate-500">No stage data.</div>
          ) : (
            <StageSummaryTable stages={stages} u={u} />
          )}
        </Section>

        <div className="h-4" />

        <Section
          title="Stage Water Quality"
          icon={<Droplets className="w-4 h-4 opacity-70" />}
          right={
            <span className={THEME.MUTED}>
              Wave-style quality table (best effort)
            </span>
          }
        >
          <StageWaterQualityPanel stages={stages} u={u} />
        </Section>

        <div className="h-4" />

        <Section
          title="스테이지 밸런스 차트"
          icon={<BarChart3 className="w-4 h-4 opacity-70" />}
        >
          <SystemBalanceChart stageData={stageData} u={u} />
        </Section>

        <div className="h-4" />

        <Section
          title="Stage Distribution Summary"
          icon={<Layers className="w-4 h-4 opacity-70" />}
        >
          <DistributionSummaryPanel stages={stages} u={u} />
        </Section>

        <div className="h-4" />

        <Section
          title="System Warnings"
          icon={<AlertTriangle className="w-4 h-4 opacity-70" />}
          right={<span className={THEME.MUTED}>Global System Guidelines</span>}
        >
          {/* ✅ 백엔드에서 집계된 globalWarnings를 Panel에 전달 */}
          <SystemWarningsPanel
            stages={stages}
            globalWarnings={safeArr(safeData.warnings)}
          />
        </Section>

        {/* ✅ 새로 추가된 Brine Scaling Panel 렌더링 영역 */}
        {safeObj(safeData.chemistry)?.final_brine && (
          <>
            <div className="h-4" />
            <Section
              title="Brine Scaling & Solubility"
              icon={<FlaskConical className="w-4 h-4 opacity-70" />}
              right={
                <span className={THEME.MUTED}>
                  Concentrate Stream (100% Limit)
                </span>
              }
            >
              <BrineScalingPanel chemistry={safeObj(safeData.chemistry)} />
            </Section>
          </>
        )}

        {mode === 'STAGE' ? (
          <div className="mt-4 text-[10px] text-slate-500">
            Mode=STAGE: 스테이지별 상세 페이지(UF/HRRO)는 아래에
            포함됩니다(존재하는 경우).
          </div>
        ) : null}
      </Page>
    );

    // =========================
    // Page 3 (Element profile)
    // =========================
    const elementProfileArr = safeArr(
      elementProfile ??
        safeData?.elementProfile ??
        safeData?.element_profile ??
        [],
    );

    const page3 =
      elementProfileArr.length > 0 ? (
        <Page key="page-3" breakBefore>
          <div className="flex items-end justify-between mb-4">
            <div>
              <div className={THEME.H2}>ELEMENT DETAILS</div>
              <div className="text-2xl font-black text-slate-900">
                Element Performance (Wave-like)
              </div>
              <div className="mt-2 flex items-center gap-2">
                <Badge
                  text={`elements n=${elementProfileArr.length}`}
                  tone="blue"
                />
              </div>
            </div>
            <div className="text-right text-[10px] text-slate-500 font-mono">
              Scenario: {scenarioId}
            </div>
          </div>

          <Section
            title="Element Profile"
            icon={<Layers className="w-4 h-4 opacity-70" />}
            right={<span className={THEME.MUTED}>auto columns</span>}
          >
            <ElementProfilePanel elementProfile={elementProfileArr} u={u} />
          </Section>
        </Page>
      ) : null;

    // ==========================================================
    // Stage Detail Page Builders
    // ==========================================================
    const buildUfPage = (s: any, stageNo: number) => {
      const moduleType = upper(s?.module_type) || 'UF';
      const chem = safeObj(s?.chemistry);
      const violations = safeArr(chem?.violations ?? []);

      const recovery = s?.recovery_pct ?? null;
      const flux = s?.flux_lmh ?? s?.jw_avg_lmh ?? null;
      const tmp = s?.tmp_bar ?? s?.tmp ?? null;
      const dp = s?.dp_bar ?? null;
      const sec = s?.sec_kwhm3 ?? s?.sec_kwh_m3 ?? null;

      const items = [
        { k: '회수율', v: recovery, unit: '%' },
        { k: '평균 Flux', v: flux, unit: u.flux },
        {
          k: tmp != null ? 'TMP' : 'ΔP',
          v: tmp != null ? tmp : dp,
          unit: u.pressure,
        },
        { k: '비에너지', v: sec, unit: 'kWh/m³' },

        { k: 'Qf', v: s?.Qf ?? null, unit: u.flow },
        { k: 'Qp', v: s?.Qp ?? null, unit: u.flow },
        { k: 'Qc', v: s?.Qc ?? null, unit: u.flow },

        { k: 'Cf', v: s?.Cf ?? null, unit: 'mg/L' },
        { k: 'Cp', v: s?.Cp ?? null, unit: 'mg/L' },
        { k: 'Cc', v: s?.Cc ?? null, unit: 'mg/L' },

        { k: 'Pin', v: s?.p_in_bar ?? null, unit: u.pressure },
        { k: 'Pout', v: s?.p_out_bar ?? null, unit: u.pressure },
      ].filter((it) => notNil(it.v));

      return (
        <Page key={`uf-${stageNo}`} breakBefore>
          <div className="flex items-end justify-between mb-4">
            <div>
              <div className={THEME.H2}>UF DETAILS</div>
              <div className="text-2xl font-black text-slate-900">
                UF 스테이지 {stageNo}
              </div>
              <div className="mt-2 flex items-center gap-2">
                <Badge text={`module_type=${moduleType}`} tone="blue" />
                {violations.length ? (
                  <ViolationsSummary violations={violations} />
                ) : (
                  <Badge text="No violations" tone="slate" />
                )}
              </div>
            </div>
            <div className="text-right text-[10px] text-slate-500 font-mono">
              Scenario: {scenarioId}
            </div>
          </div>

          <Section
            title="핵심 KPI (best-effort)"
            icon={<Waves className="w-4 h-4 opacity-70" />}
            right={
              <span className={THEME.MUTED}>있으면 표시 / 없으면 생략</span>
            }
          >
            {!items.length ? (
              <div className="text-[10px] text-slate-500">
                표시 가능한 KPI가 없습니다. (Raw Stage를 확인하세요)
              </div>
            ) : (
              <KVGrid cols={3} items={items} />
            )}
          </Section>

          <div className="h-4" />

          <Section
            title="Stage Water Quality"
            icon={<Droplets className="w-4 h-4 opacity-70" />}
            right={<span className={THEME.MUTED}>single-stage view</span>}
          >
            <StageWaterQualityPanel stages={[s]} u={u} />
          </Section>

          <div className="h-4" />

          <Section
            title="Warnings (chemistry.violations)"
            icon={<ShieldAlert className="w-4 h-4 opacity-70" />}
          >
            {!violations.length ? (
              <div className="text-[10px] text-slate-500">
                위반 사항이 없습니다.
              </div>
            ) : (
              <ViolationsTable violations={violations} />
            )}

            <div className="mt-3">
              <JsonDetails
                titleKo="Raw UF chemistry (접기)"
                obj={chem}
                maxChars={12000}
              />
            </div>
          </Section>

          <div className="h-4" />

          <Section
            title="Raw Stage Object (접기)"
            icon={<Database className="w-4 h-4 opacity-70" />}
            right={<span className={THEME.MUTED}>debug / audit</span>}
          >
            <JsonDetails
              titleKo="Raw UF stage (접기)"
              obj={s}
              maxChars={12000}
            />
          </Section>
        </Page>
      );
    };

    const buildHrroPages = (s: any, stageNo: number) => {
      const chem = safeObj(s?.chemistry);

      const design = safeObj(
        chem?.design_excel ?? chem?.designExcel ?? chem?.design ?? {},
      );

      const inputs = safeObj(design?.inputs ?? {});
      const ccro = safeObj(design?.ccro ?? {});
      const pf = safeObj(design?.pf ?? {});
      const cc = safeObj(design?.cc ?? {});
      const membrane = safeObj(design?.membrane ?? {});

      const physics = safeObj(design?.physics ?? chem?.physics ?? {});
      const guideline = safeObj(chem?.guideline ?? {});
      const checks = safeObj(
        chem?.guideline_checks ?? chem?.guidelineChecks ?? {},
      );
      const violations = safeArr(chem?.violations ?? []);
      const history = safeArr(s?.time_history);

      const physicsHydraulics = safeObj(physics?.hydraulics ?? {});
      const physicsDebug = safeObj(physics?.debug ?? {});

      const pageA = (
        <Page key={`hrro-${stageNo}-a`} breakBefore>
          <div className="flex items-end justify-between mb-4">
            <div>
              <div className={THEME.H2}>HRRO DETAILS</div>
              <div className="text-2xl font-black text-slate-900">
                HRRO 스테이지 {stageNo}
              </div>
              <div className="mt-2 flex items-center gap-2">
                <Badge text="module_type=HRRO" tone="violet" />
                <ViolationsSummary violations={violations} />
              </div>
            </div>
            <div className="text-right text-[10px] text-slate-500 font-mono">
              Scenario: {scenarioId}
            </div>
          </div>

          <Section
            title="핵심 결과(Wave-style status)"
            icon={<Gauge className="w-4 h-4 opacity-70" />}
            right={
              <span className={THEME.MUTED}>Target/Achieved/Limit/Status</span>
            }
          >
            <HRROCoreStatusTable physics={physics} u={u} />
          </Section>

          <div className="h-4" />

          <Section
            title="가이드라인/체크"
            icon={<ShieldAlert className="w-4 h-4 opacity-70" />}
          >
            {!violations.length ? (
              <div className="text-[10px] text-slate-500">
                위반 사항이 없습니다.
              </div>
            ) : (
              <ViolationsTable violations={violations} />
            )}

            <div className="mt-3 grid grid-cols-2 gap-3">
              <JsonDetails titleKo="Guideline Profile (접기)" obj={guideline} />
              <JsonDetails titleKo="Guideline Checks (접기)" obj={checks} />
            </div>
          </Section>

          <div className="h-4" />

          <Section
            title="상세 데이터(접기)"
            icon={<Database className="w-4 h-4 opacity-70" />}
            right={<span className={THEME.MUTED}>기본은 요약만 표시</span>}
          >
            <div className="grid grid-cols-2 gap-3">
              <JsonDetails titleKo="Excel Inputs (접기)" obj={inputs} />
              <JsonDetails titleKo="Excel CCRO Results (접기)" obj={ccro} />
              <JsonDetails titleKo="Excel PF Results (접기)" obj={pf} />
              <JsonDetails titleKo="Excel CC/Recycle (접기)" obj={cc} />
              <JsonDetails titleKo="Membrane / Array (접기)" obj={membrane} />
              <JsonDetails
                titleKo="Physics Hydraulics (접기)"
                obj={physicsHydraulics}
              />
              <JsonDetails titleKo="Physics Debug (접기)" obj={physicsDebug} />
            </div>

            <div className="mt-3">
              <JsonDetails
                titleKo="Raw HRRO chemistry (접기)"
                obj={chem}
                maxChars={12000}
              />
            </div>
          </Section>
        </Page>
      );

      const pageB =
        history.length > 0 ? (
          <Page key={`hrro-${stageNo}-b`} breakBefore>
            <div className="flex items-end justify-between mb-4">
              <div>
                <div className={THEME.H2}>HRRO TIME HISTORY</div>
                <div className="text-2xl font-black text-slate-900">
                  HRRO 스테이지 {stageNo} · 배치 사이클
                </div>
                <div className="mt-2 flex items-center gap-2">
                  <Badge text={`history n=${history.length}`} tone="blue" />
                  <Badge text="MIN/AVG/MAX/END" tone="slate" />
                </div>
              </div>
              <div className="text-right text-[10px] text-slate-500 font-mono">
                Scenario: {scenarioId}
              </div>
            </div>

            <Section
              title="배치 사이클 차트"
              icon={<Clock className="w-4 h-4 opacity-70" />}
            >
              <HRROHistoryChart history={history} unitLabels={u} />
            </Section>

            <div className="h-4" />

            <Section
              title="Time History 요약 통계"
              icon={<ListChecks className="w-4 h-4 opacity-70" />}
            >
              <HistoryStatsTable history={history} u={u} />
            </Section>

            <div className="h-4" />

            <Section
              title="Time History 테이블(일부)"
              icon={<FileText className="w-4 h-4 opacity-70" />}
            >
              <TimeHistoryTable history={history} maxRows={12} />
            </Section>
          </Page>
        ) : null;

      return [pageA, ...(pageB ? [pageB] : [])];
    };

    // ==========================================================
    // Stage detail pages: stage order 유지 (UF->HRRO 순서 보장)
    // ==========================================================
    const stageDetailPages = stages
      .map((s: any, idx: number) => {
        const stageNo = Number(s?.stage ?? idx + 1);
        return {
          stageNo: Number.isFinite(stageNo) ? stageNo : idx + 1,
          moduleType: upper(s?.module_type),
          s,
        };
      })
      .sort((a, b) => a.stageNo - b.stageNo)
      .flatMap(({ stageNo, moduleType, s }) => {
        if (moduleType === 'UF') return [buildUfPage(s, stageNo)];
        if (moduleType === 'HRRO') return buildHrroPages(s, stageNo);
        return [];
      });

    return (
      <div ref={ref} className="print:w-full">
        {page1}
        {page2}
        {page3}
        {stageDetailPages}
      </div>
    );
  },
);

ReportTemplate.displayName = 'ReportTemplate';
