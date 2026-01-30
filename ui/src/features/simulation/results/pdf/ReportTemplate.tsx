import React from 'react';
import {
  ComposedChart,
  Line,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
} from 'recharts';
import { Activity, Droplets, Zap, Gauge } from 'lucide-react';
import { fmt, pct } from '../../model/types';

// PDF 스타일 상수
const THEME = {
  PAGE: 'w-[210mm] min-h-[297mm] bg-white text-slate-800 font-sans p-10 mx-auto shadow-2xl mb-10 relative print:shadow-none print:mb-0 print:p-8',
  TABLE: {
    ROOT: 'w-full text-[10px] border-collapse',
    HEAD: 'bg-slate-100 text-slate-500 font-bold uppercase tracking-tight text-left py-2 px-3 border-b border-slate-200',
    ROW: 'border-b border-slate-100 last:border-0 hover:bg-slate-50',
    CELL: 'py-1.5 px-3 text-slate-700 font-mono',
    CELL_LABEL: 'py-1.5 px-3 text-slate-600 font-sans font-semibold',
  },
};

interface ReportProps {
  data: any;
  mode: 'SYSTEM' | 'STAGE';
}

export const ReportTemplate = React.forwardRef<HTMLDivElement, ReportProps>(
  ({ data }, ref) => {
    // 1. 데이터 추출 (안전하게)
    const safeData = data || {};
    const kpi = safeData.kpi || {};
    const stages = safeData.stage_metrics || [];
    const feed = safeData.streams?.[0] || {};
    const perm = safeData.streams?.[1] || {};
    const conc = safeData.streams?.[2] || {};

    // 2. 시스템 KPI (표준 키)
    const system = {
      recovery_pct: kpi.recovery_pct || 0,
      sec_kwhm3: kpi.sec_kwhm3 || 0,
      jw_avg_lmh: kpi.flux_lmh || 0,
    };

    // 3. 차트용 데이터 변환
    const stageData = stages.map((s: any) => ({
      stage: s.stage,
      rec: s.recovery_pct,
      flux: s.jw_avg_lmh,
      ndp: s.ndp_bar,
      type: s.module_type,
    }));

    return (
      <div ref={ref} className="print:w-full">
        <div className={THEME.PAGE}>
          {/* 헤더 */}
          <div className="flex justify-between items-end mb-6">
            <h1 className="text-3xl font-black text-slate-900 tracking-tighter">
              AquaNova <span className="text-blue-600">Report</span>
            </h1>
            <div className="text-right text-[10px] text-slate-400 font-mono">
              ID: {safeData.scenario_id || 'N/A'} <br />
              Date: {new Date().toLocaleDateString()}
            </div>
          </div>

          {/* 상단 KPI 카드 */}
          <div className="grid grid-cols-3 gap-4 mb-8">
            <KPICard
              label="Recovery"
              value={pct(system.recovery_pct)}
              icon={Droplets}
              color="bg-blue-50 text-blue-700"
            />
            <KPICard
              label="Specific Energy"
              value={`${fmt(system.sec_kwhm3)} kWh/m³`}
              icon={Zap}
              color="bg-yellow-50 text-yellow-700"
            />
            <KPICard
              label="Avg Flux"
              value={`${fmt(system.jw_avg_lmh)} LMH`}
              icon={Activity}
              color="bg-emerald-50 text-emerald-700"
            />
          </div>

          {/* 스트림 테이블 */}
          <SectionTitle title="Stream Data" />
          <div className="rounded border border-slate-200 mb-8">
            <table className={THEME.TABLE.ROOT}>
              <thead>
                <tr>
                  <th className={THEME.TABLE.HEAD}>Stream</th>
                  <th className={THEME.TABLE.HEAD}>Flow (m³/h)</th>
                  <th className={THEME.TABLE.HEAD}>TDS (mg/L)</th>
                  <th className={THEME.TABLE.HEAD}>Pressure (bar)</th>
                </tr>
              </thead>
              <tbody>
                <Row label="Feed" data={feed} />
                <Row label="Permeate" data={perm} highlight />
                <Row label="Concentrate" data={conc} />
              </tbody>
            </table>
          </div>

          {/* 스테이지별 상세 테이블 */}
          <SectionTitle title="Stage Performance" />
          <div className="rounded border border-slate-200 mb-8">
            <table className={THEME.TABLE.ROOT}>
              <thead>
                <tr>
                  <th className={THEME.TABLE.HEAD}>Stage</th>
                  <th className={THEME.TABLE.HEAD}>Type</th>
                  <th className={THEME.TABLE.HEAD}>Recovery</th>
                  <th className={THEME.TABLE.HEAD}>Flux (LMH)</th>
                  <th className={THEME.TABLE.HEAD}>NDP (bar)</th>
                </tr>
              </thead>
              <tbody>
                {stages.map((s: any, i: number) => (
                  <tr key={i} className={THEME.TABLE.ROW}>
                    <td className={THEME.TABLE.CELL_LABEL}>Stage {s.stage}</td>
                    <td className={THEME.TABLE.CELL}>{s.module_type}</td>
                    <td className={THEME.TABLE.CELL}>{pct(s.recovery_pct)}</td>
                    <td className={THEME.TABLE.CELL}>{fmt(s.jw_avg_lmh)}</td>
                    <td className={THEME.TABLE.CELL}>{fmt(s.ndp_bar)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* 차트 영역 (Flux & NDP) */}
          <SectionTitle title="System Balance Chart" />
          <div className="h-60 border border-slate-100 bg-slate-50 rounded p-4">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart
                data={stageData}
                margin={{ top: 20, right: 20, bottom: 20, left: 20 }}
              >
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis
                  dataKey="stage"
                  label={{ value: 'Stage', position: 'bottom' }}
                />
                <YAxis
                  yAxisId="left"
                  label={{
                    value: 'Flux (LMH)',
                    angle: -90,
                    position: 'insideLeft',
                  }}
                />
                <YAxis
                  yAxisId="right"
                  orientation="right"
                  label={{
                    value: 'NDP (bar)',
                    angle: 90,
                    position: 'insideRight',
                  }}
                />
                <Tooltip />
                <Bar
                  yAxisId="left"
                  dataKey="flux"
                  fill="#3b82f6"
                  name="Flux (LMH)"
                  barSize={40}
                />
                <Line
                  yAxisId="right"
                  type="monotone"
                  dataKey="ndp"
                  stroke="#10b981"
                  name="NDP (bar)"
                  strokeWidth={2}
                />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
    );
  },
);

// --- 리포트용 UI 헬퍼 ---
const KPICard = ({ label, value, color, icon: Icon }: any) => (
  <div
    className={`p-4 rounded border flex items-center justify-between ${color}`}
  >
    <div>
      <div className="text-[10px] font-bold uppercase opacity-70">{label}</div>
      <div className="text-xl font-mono font-bold">{value}</div>
    </div>
    <Icon className="w-6 h-6 opacity-50" />
  </div>
);

const SectionTitle = ({ title }: { title: string }) => (
  <div className="border-b border-slate-200 pb-2 mb-4 mt-8 font-bold text-sm text-slate-800 uppercase tracking-wider">
    {title}
  </div>
);

const Row = ({ label, data, highlight }: any) => (
  <tr className={`${THEME.TABLE.ROW} ${highlight ? 'bg-slate-50' : ''}`}>
    <td className={THEME.TABLE.CELL_LABEL}>{label}</td>
    <td className={THEME.TABLE.CELL}>{fmt(data?.flow_m3h)}</td>
    <td className={THEME.TABLE.CELL}>{fmt(data?.tds_mgL)}</td>
    <td className={THEME.TABLE.CELL}>{fmt(data?.pressure_bar)}</td>
  </tr>
);

ReportTemplate.displayName = 'ReportTemplate';
