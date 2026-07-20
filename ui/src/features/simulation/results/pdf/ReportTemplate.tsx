// ui/src/features/simulation/results/pdf/ReportTemplate.tsx
import React from 'react';
import { ReportProps } from './types';
import { safeArr, safeObj, fmt, pct } from './utils';

import { Page, Section, StreamTable, StageSummaryTable } from './components';
import {
  TrainOverviewPanel,
  BalancePanel,
  SystemBalanceChart,
  StageWaterQualityPanel,
  SystemWarningsPanel,
  HRROCoreStatusTable,
  HRROProcessFlowPanel,
  HRROHistoryChart,
  HistoryStatsTable,
  BrineScalingPanel,
  UfDetailsPanel,
  ElementProfilePanel,
  ChemicalDosingPanel,
  OpexSummaryPanel, // 🟢 [NEW] 새로 만든 경제성 패널 임포트!
} from './panels';

type UnitBag = {
  flow: string;
  pressure: string;
  temperature: string;
  flux: string;
};

const upper = (v: any) => String(v ?? '').toUpperCase();

export const ReportTemplate = React.forwardRef<HTMLDivElement, ReportProps>(
  ({ data }, ref) => {
    const safeData = data || {};
    const kpi = safeObj(safeData.kpi);
    const stages = safeArr(safeData.stage_metrics);
    const unitLabels = safeObj(safeData.unit_labels);
    const economics = safeObj(safeData.economics);

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
    const brine = streamByLabel('Brine') || streamByLabel('Concentrate') || {};

    const firstStage = stages[0] || {};
    const system = {
      recovery_pct: kpi.recovery_pct ?? 0,
      sec_kwhm3: kpi.sec_kwhm3 ?? kpi.sec_kwh_m3 ?? 0,
      flux_lmh: kpi.flux_lmh || kpi.jw_avg_lmh || firstStage.flux_lmh || 0,
      ndp_bar: kpi.ndp_bar || firstStage.ndp_bar || firstStage.tmp_bar || 0,
    };

    const isMfUf = stages.some((s: any) =>
      ['MF', 'UF'].includes(upper(s?.module_type || s?.type)),
    );
    const pressureLabel = isMfUf ? '막간차압 (TMP)' : '순구동압력 (NDP)';

    const feedTemp = feed?.temperature_C ?? 25.0;
    const waterType = safeData?.feed?.water_type ?? 'Well Water';

    const totalElements = stages.reduce((sum: number, s: any) => {
      const elems =
        s.elements ||
        s.num_elements ||
        s.total_elements ||
        (s.vessel_count && s.elements_per_vessel
          ? s.vessel_count * s.elements_per_vessel
          : 0) ||
        0;
      return sum + Number(elems);
    }, 0);

    const totalPasses = stages.length;
    const title =
      safeData.customTitle || '시스템 예측 리포트 (System Projection Report)';
    const scenarioId = safeData.scenario_id || safeData.id || 'N/A';
    const createdAt = safeData.createdAtISO || safeData.created_at || null;
    const dateText = createdAt
      ? new Date(createdAt).toLocaleString()
      : new Date().toLocaleString();

    const thClass =
      'py-1.5 px-2 text-[10px] font-bold text-slate-800 border border-slate-300 bg-slate-100 text-left w-1/4';
    const tdClass =
      'py-1.5 px-2 text-[10px] text-slate-900 border border-slate-300 bg-white w-1/4 tabular-nums';

    // =========================
    // Page 1: System Overview (유량, 밸런스 등)
    // =========================
    const page1 = (
      <Page key="page-1">
        <div className="mb-5 border-b-2 border-slate-800 pb-4">
          <div className="flex justify-between items-start mb-3">
            <img
              src="/brand/logo.png"
              alt="Brand Logo"
              className="h-10 object-contain drop-shadow-sm"
              onError={(e) => {
                e.currentTarget.style.display = 'none';
              }}
            />
            <div className="text-right text-[10px] text-slate-500 font-mono mt-1">
              <div>시나리오 ID: {scenarioId}</div>
              <div>작성 일자: {dateText}</div>
            </div>
          </div>
          <div className="mt-2">
            <div className="text-[11px] font-bold text-slate-500 tracking-widest uppercase mb-1">
              Project Information
            </div>
            <h1 className="text-2xl font-black text-slate-900 uppercase tracking-tight leading-none">
              {title}
            </h1>
          </div>
        </div>

        <div className="mb-5 print:break-inside-avoid">
          <div className="text-[11px] font-bold text-slate-800 mb-1.5 pl-2 border-l-2 border-slate-800 uppercase tracking-wider">
            설계 기준 및 시스템 성능 (Design Basis & System Performance)
          </div>
          <table className="w-full border-collapse border-2 border-slate-400 shadow-sm">
            <tbody>
              <tr>
                <td className={thClass}>원수 종류 (Water Type)</td>
                <td className={tdClass}>{waterType}</td>
                <td className={thClass}>총 엘리먼트 수 (Total Elements)</td>
                <td className={tdClass}>
                  {totalElements > 0 ? totalElements : '-'}
                </td>
              </tr>
              <tr>
                <td className={thClass}>유입수 온도 (Feed Temp)</td>
                <td className={tdClass}>{fmt(feedTemp)} °C</td>
                <td className={thClass}>총 스테이지 수 (Total Stages)</td>
                <td className={tdClass}>{totalPasses}</td>
              </tr>
              <tr>
                <td className={thClass}>유입 유량 (Feed Flow)</td>
                <td className={tdClass}>
                  {fmt(feed?.flow_m3h)} {u.flow}
                </td>
                <td className={thClass}>시스템 총 회수율 (System Recovery)</td>
                <td
                  className={`${tdClass} font-bold text-blue-800 bg-blue-50/50`}
                >
                  {pct(system.recovery_pct)}
                </td>
              </tr>
              <tr>
                <td className={thClass}>생산 유량 (Permeate Flow)</td>
                <td
                  className={`${tdClass} font-bold text-blue-800 bg-blue-50/50`}
                >
                  {fmt(perm?.flow_m3h)} {u.flow}
                </td>
                <td className={thClass}>평균 플럭스 (Average Flux)</td>
                <td className={tdClass}>
                  {fmt(system.flux_lmh)} {u.flux}
                </td>
              </tr>
              <tr>
                <td className={thClass}>비에너지 (SEC)</td>
                <td className={tdClass}>{fmt(system.sec_kwhm3)} kWh/m³</td>
                <td className={thClass}>{pressureLabel}</td>
                <td className={tdClass}>
                  {fmt(system.ndp_bar)} {u.pressure}
                </td>
              </tr>
              {economics?.unit_cost > 0 && (
                <tr>
                  <td
                    className={`${thClass} bg-emerald-50 text-emerald-900 border-emerald-400`}
                  >
                    생산 단가 (Unit Cost)
                  </td>
                  <td
                    className={`${tdClass} font-black text-emerald-800 bg-emerald-50/50 border-emerald-400`}
                  >
                    {economics.currency || '$'} {fmt(economics.unit_cost, 3)}{' '}
                    /m³
                  </td>
                  <td
                    className={`${thClass} bg-emerald-50 text-emerald-900 border-emerald-400`}
                  >
                    일일 운영비 (Daily OPEX)
                  </td>
                  <td
                    className={`${tdClass} font-bold text-emerald-800 bg-emerald-50/50 border-emerald-400`}
                  >
                    {economics.currency || '$'}{' '}
                    {fmt(economics.daily_total_cost, 2)} /day
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        <Section title="공정 개요 (Train Overview)">
          <TrainOverviewPanel stages={stages} />
        </Section>
        <div className="h-3" />

        <Section title="스트림 성분 및 수질 (Stream Composition & Water Quality)">
          <StreamTable feed={feed} perm={perm} brine={brine} u={u} />
        </Section>
        <div className="h-3" />

        <Section title="질량 및 염분 밸런스 (Mass & Salt Balance)">
          <BalancePanel feed={feed} perm={perm} brine={brine} kpi={kpi} u={u} />
        </Section>
      </Page>
    );

    // =========================
    // Page 2: Hydraulics & Performance (물리 엔진 성능)
    // =========================
    const page2 = (
      <Page key="page-2" breakBefore>
        <div className="mb-4 border-b-2 border-slate-800 pb-2 flex justify-between items-start">
          <div>
            <div className="text-[10px] font-bold text-slate-500 tracking-widest uppercase mb-1">
              HYDRAULICS & PERFORMANCE
            </div>
            <h2 className="text-lg font-black text-slate-900 uppercase leading-none">
              수력학적 성능 요약 (Hydraulic Performance Summary)
            </h2>
          </div>
          <div className="text-[9px] text-slate-400 font-mono mt-1">
            AquaNova Simulation Engine
          </div>
        </div>

        <Section title="스테이지/패스 상세 성능 (Stage Performance Details)">
          <StageSummaryTable stages={stages} u={u} />
        </Section>
        <div className="h-3" />

        <Section title="스테이지별 수질 (Stage Water Quality)">
          <StageWaterQualityPanel stages={stages} u={u} />
        </Section>
        <div className="h-3" />

        <Section title="스테이지 밸런스 차트 (Stage Balance Chart)">
          <SystemBalanceChart
            stageData={stages.map((s: any, idx: number) => ({
              stage: s?.stage ?? idx + 1,
              flux: s?.flux_lmh ?? s?.jw_avg_lmh ?? null,
              ndp: s?.ndp_bar ?? null,
              type: s?.module_type ?? 'RO',
            }))}
            u={u}
          />
        </Section>
      </Page>
    );

    // =========================
    // Page 3: Chemistry, OPEX & Warnings (화학 및 경제성)
    // =========================
    const page3 = (
      <Page key="page-3" breakBefore>
        <div className="mb-4 border-b-2 border-slate-800 pb-2 flex justify-between items-start">
          <div>
            <div className="text-[10px] font-bold text-slate-500 tracking-widest uppercase mb-1">
              CHEMISTRY & ECONOMICS
            </div>
            <h2 className="text-lg font-black text-slate-900 uppercase leading-none">
              화학 및 경제성 평가 (Chemistry & Economics)
            </h2>
          </div>
          <div className="text-[9px] text-slate-400 font-mono mt-1">
            AquaNova Simulation Engine
          </div>
        </div>

        {safeData?.chemistry?.final_brine && (
          <>
            <Section title="스케일링 및 막 오염 지수 (Scaling & Fouling Indices)">
              <BrineScalingPanel chemistry={safeData.chemistry} />
            </Section>
            <div className="h-3" />
          </>
        )}

        {safeData?.dosing && (
          <>
            <Section title="지능형 약품 투입 제어 (Intelligent Chemical Dosing)">
              <ChemicalDosingPanel dosing={safeData.dosing} u={u} />
            </Section>
            <div className="h-3" />
          </>
        )}

        {/* 🟢 [NEW] 백엔드에서 받아온 OPEX 데이터를 전용 패널에 렌더링 */}
        {economics?.unit_cost > 0 && (
          <>
            <OpexSummaryPanel economics={economics} />
            <div className="h-4" />
          </>
        )}

        <Section title="시스템 경고 및 진단 (System Warnings & Diagnostics)">
          <SystemWarningsPanel
            stages={stages}
            globalWarnings={safeArr(safeData.warnings)}
          />
        </Section>
      </Page>
    );

    // =========================
    // Page 4~: Stage Detail Pages Builder (모듈별 상세)
    // =========================
    const buildUfPage = (s: any, stageNo: number) => {
      const type = upper(s?.module_type || s?.type || 'UF');
      return (
        <Page key={`filter-${stageNo}`} breakBefore>
          <div className="mb-4 border-b-2 border-slate-800 pb-2 flex justify-between items-start">
            <div>
              <div className="text-[10px] font-bold text-slate-500 tracking-widest uppercase mb-1">
                {type} DETAILS
              </div>
              <h2 className="text-lg font-black text-slate-900 uppercase leading-none">
                {type} 스테이지 {stageNo} ({type} Stage {stageNo})
              </h2>
            </div>
          </div>
          <Section title="핵심 성능 지표 (Key Performance Indicators)">
            <UfDetailsPanel
              stage={s}
              systemKpi={kpi}
              feedFlow={s?.Qf}
              permFlow={s?.Qp}
              u={u}
            />
          </Section>
          <div className="h-3" />
          <Section title="스테이지별 수질 (Stage Water Quality)">
            <StageWaterQualityPanel stages={[s]} u={u} />
          </Section>
        </Page>
      );
    };

    const buildRoPages = (s: any, stageNo: number) => {
      const type = upper(s?.module_type || s?.type || 'RO');
      return [
        <Page key={`ro-${stageNo}-a`} breakBefore>
          <div className="mb-4 border-b-2 border-slate-800 pb-2 flex justify-between items-start">
            <div>
              <div className="text-[10px] font-bold text-slate-500 tracking-widest uppercase mb-1">
                {type} DETAILS
              </div>
              <h2 className="text-lg font-black text-slate-900 uppercase leading-none">
                {type} 스테이지 {stageNo} ({type} Stage {stageNo})
              </h2>
            </div>
          </div>
          <Section title="엘리먼트 프로파일 (Element Profile)">
            <ElementProfilePanel
              elementProfile={safeArr(
                s?.chemistry?.elements || s?.element_profiles || s?.elements,
              )}
              u={u}
            />
          </Section>
        </Page>,
      ];
    };

    const buildHrroPages = (s: any, stageNo: number) => {
      const history = safeArr(s?.time_history);
      return [
        <Page key={`hrro-${stageNo}-a`} breakBefore>
          <div className="mb-4 border-b-2 border-slate-800 pb-2 flex justify-between items-start">
            <div>
              <div className="text-[10px] font-bold text-slate-500 tracking-widest uppercase mb-1">
                HRRO DETAILS
              </div>
              <h2 className="text-lg font-black text-slate-900 uppercase leading-none">
                HRRO 스테이지 {stageNo} (HRRO Stage {stageNo})
              </h2>
            </div>
          </div>
          <Section title="운전 상태 (Target vs Achieved)">
            <HRROCoreStatusTable stage={s} u={u} />
          </Section>

          {s?.chemistry?.ccro_cycle && (
            <>
              <div className="h-3" />
              <Section title="CC/PF 공정 흐름 및 운전점 (Process Flow & Operating Points)">
                <HRROProcessFlowPanel
                  stage={s}
                  unitLabels={u}
                />
              </Section>
            </>
          )}
        </Page>,
        ...(history.length > 0
          ? [
              <Page key={`hrro-${stageNo}-b`} breakBefore>
                <Section title="배치 사이클 시계열 데이터">
                  <HRROHistoryChart history={history} unitLabels={u} />
                </Section>
                <div className="h-3" />
                <Section title="통계 요약">
                  <HistoryStatsTable history={history} u={u} />
                </Section>
              </Page>,
            ]
          : []),
      ];
    };

    const stageDetailPages = stages
      .map((s: any, idx: number) => ({
        stageNo: Number(s?.stage ?? idx + 1),
        s,
      }))
      .sort((a, b) => a.stageNo - b.stageNo)
      .flatMap(({ stageNo, s }) => {
        const type = upper(s?.module_type || s?.type || s?.membrane_model);
        if (type === 'UF' || type === 'MF') return [buildUfPage(s, stageNo)];
        if (type === 'RO' || type === 'NF') return buildRoPages(s, stageNo);
        if (type === 'HRRO') return buildHrroPages(s, stageNo);
        return [];
      });

    return (
      <div
        ref={ref}
        className="print:w-full font-sans text-slate-800 bg-white [-webkit-print-color-adjust:exact] print:color-adjust-exact"
      >
        {page1}
        {page2}
        {page3}
        {stageDetailPages}
      </div>
    );
  },
);

ReportTemplate.displayName = 'ReportTemplate';
