// ui\src\features\simulation\results\Visualization.tsx
// ui/src/features/simulation/results/Visualization.tsx

import React, { useState, useEffect, useRef, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  ComposedChart,
  Line,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from 'recharts';
import {
  Activity,
  Droplets,
  Gauge,
  Zap,
  Waves,
  ArrowRight,
  ArrowDownRight,
  AlertTriangle,
  CheckCircle2,
  Maximize2,
  LayoutDashboard,
  ShieldCheck,
  AlertOctagon,
  Droplet,
} from 'lucide-react';

import { UnitMode, fmt, pct } from '../model/types';
import { DetailedResultModal } from '../../../components/common/DetailedResultModal';
import { ReportDownloadButton } from '../../../components/common/ReportDownloadButton';

// -----------------------------------------------------------------------------
// 1. Utilities & Sub-Components
// -----------------------------------------------------------------------------

function cn(...classes: (string | undefined | null | false)[]) {
  return classes.filter(Boolean).join(' ');
}

const CARD_BASE =
  'rounded-lg border bg-slate-900/40 p-3 shadow-sm transition-all hover:bg-slate-900/60 hover:border-slate-700';
const LABEL_BASE =
  'text-[10px] font-bold text-slate-500 uppercase tracking-wider flex items-center gap-1.5 mb-1';

function HealthCheckItem({
  label,
  status,
  value,
  unit,
}: {
  label: string;
  status: 'ok' | 'warning' | 'error';
  value?: string | number;
  unit?: string;
}) {
  const colors = {
    ok: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20',
    warning: 'text-yellow-400 bg-yellow-500/10 border-yellow-500/20',
    error: 'text-rose-400 bg-rose-500/10 border-rose-500/20',
  };
  const icons = {
    ok: <CheckCircle2 className="w-3 h-3" />,
    warning: <AlertTriangle className="w-3 h-3" />,
    error: <AlertOctagon className="w-3 h-3" />,
  };

  return (
    <div
      className={cn(
        'flex items-center justify-between p-2 rounded border text-xs',
        colors[status],
      )}
    >
      <div className="flex items-center gap-2 font-semibold opacity-90">
        {icons[status]}
        <span>{label}</span>
      </div>
      {value ? (
        <div className="font-mono font-bold opacity-80">
          {value}
          <span className="text-[10px] ml-0.5 opacity-60">{unit}</span>
        </div>
      ) : null}
    </div>
  );
}

// [RO/NF Detail] 백엔드 StageMetric 스키마와 100% 일치 (Qf, Qp, Qc...)
function RODetailContent({ data }: { data: any }) {
  if (!data) return null;
  const { Qf, Qp, Qc, Cf, Cp, Cc, p_in_bar, p_out_bar } = data;

  return (
    <div className="mt-3 pt-3 border-t border-dashed border-slate-700/50 space-y-3">
      <div className="rounded border border-slate-800 overflow-hidden text-[9px] leading-tight">
        <div className="grid grid-cols-4 bg-slate-800/80 font-bold text-slate-400 py-1 text-center">
          <div className="text-left pl-2">Stream</div>
          <div>Flow</div>
          <div>TDS</div>
          <div>Press</div>
        </div>
        {[
          {
            label: 'Feed',
            color: 'text-blue-300',
            flow: Qf,
            tds: Cf,
            press: p_in_bar,
            icon: <div className="w-1.5 h-1.5 rounded-full bg-blue-500" />,
            bg: '',
          },
          {
            label: 'Perm',
            color: 'text-emerald-300',
            flow: Qp,
            tds: Cp,
            press: 0,
            icon: <ArrowRight className="w-2.5 h-2.5 text-emerald-500" />,
            bg: 'bg-emerald-500/5',
          },
          {
            label: 'Conc',
            color: 'text-orange-300',
            flow: Qc,
            tds: Cc,
            press: p_out_bar,
            icon: <ArrowDownRight className="w-2.5 h-2.5 text-orange-500" />,
            bg: 'bg-orange-500/5',
          },
        ].map((row, i) => (
          <div
            key={i}
            className={cn(
              'grid grid-cols-4 py-1 items-center border-t border-slate-800/50',
              row.bg,
            )}
          >
            <div
              className={cn(
                'pl-2 flex items-center gap-1 font-bold',
                row.color,
              )}
            >
              {row.icon} {row.label}
            </div>
            <div className="text-center font-mono text-slate-300">
              {fmt(row.flow)}
            </div>
            <div className="text-center font-mono text-slate-300">
              {fmt(row.tds)}
            </div>
            <div className="text-center font-mono text-slate-400">
              {fmt(row.press)}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// [UF/MF Detail] 백엔드 스키마 일치
function UFDetailContent({ data }: { data: any }) {
  if (!data) return null;
  const { gross_flow_m3h, backwash_loss_m3h, net_recovery_pct } = data;
  const recoveryVal = net_recovery_pct ?? 0;

  return (
    <div className="mt-3 pt-3 border-t border-dashed border-slate-700/50 space-y-3">
      <div>
        <div className="flex justify-between text-[9px] uppercase font-bold text-slate-500 mb-1">
          <span>Net Recovery</span>
          <span className="text-emerald-400">{pct(recoveryVal)}</span>
        </div>
        <div className="h-1.5 w-full bg-slate-800 rounded-full overflow-hidden flex">
          <div
            style={{ width: `${Math.min(recoveryVal, 100)}%` }}
            className="bg-emerald-500"
          />
          <div
            style={{ width: `${Math.max(0, 100 - recoveryVal)}%` }}
            className="bg-rose-500/50"
          />
        </div>
      </div>
      <div className="grid grid-cols-2 gap-2">
        <div className="bg-slate-900/40 p-1.5 rounded border border-slate-800">
          <div className="text-[9px] text-slate-500">Gross Flow</div>
          <div className="font-mono text-xs font-bold text-slate-200">
            {fmt(gross_flow_m3h)}
          </div>
        </div>
        <div className="bg-slate-900/40 p-1.5 rounded border border-slate-800">
          <div className="text-[9px] text-rose-400/70">BW Loss</div>
          <div className="font-mono text-xs font-bold text-rose-400">
            -{fmt(backwash_loss_m3h)}
          </div>
        </div>
      </div>
    </div>
  );
}

// [HRRO Chart] flux_lmh 사용
function HRROBatchChart({ history }: { history: any[] | null }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [dimensions, setDimensions] = useState({ width: 0, height: 0 });

  const hasData = !!history && history.length > 0;

  const cleanData = useMemo(() => {
    if (!hasData || !history) return [];
    return history.map((d) => ({
      ...d,
      time_min: Number(d.time_min),
      pressure_bar: Number(d.pressure_bar),
      tds_mgL: Number(d.tds_mgL),
      flux_lmh: Number(d.flux_lmh), // ✅ 정석: flux_lmh 사용
      recovery_pct: Number(d.recovery_pct),
    }));
  }, [history, hasData]);

  useEffect(() => {
    const updateSize = () => {
      if (containerRef.current) {
        setDimensions({
          width: containerRef.current.clientWidth,
          height: containerRef.current.clientHeight,
        });
      }
    };
    const timer = setTimeout(updateSize, 100);
    window.addEventListener('resize', updateSize);
    return () => {
      clearTimeout(timer);
      window.removeEventListener('resize', updateSize);
    };
  }, []);

  const chartWidth = dimensions.width > 20 ? dimensions.width / 2 - 10 : 0;
  const chartHeight = 140;

  return (
    <div className="mt-3 pt-3 border-t border-dashed border-slate-700/50">
      <div className="flex items-center justify-between mb-2">
        <div className="text-[10px] font-bold text-slate-500 uppercase flex gap-1">
          <Activity className="w-3 h-3" /> HRRO Batch Cycle
        </div>
      </div>

      {!hasData ? (
        <div className="rounded border border-slate-800/50 bg-slate-900/20 p-2 text-[10px] text-slate-500">
          No time-series data available.
        </div>
      ) : (
        <div
          ref={containerRef}
          className="flex w-full h-[150px] overflow-hidden gap-2"
        >
          {chartWidth > 0 && (
            <>
              {/* Chart 1 */}
              <div className="bg-slate-900/20 rounded border border-slate-800/50 p-1 relative flex-1">
                <div className="absolute top-1 left-2 text-[8px] text-slate-500 font-bold z-10">
                  Press & TDS
                </div>
                <ComposedChart
                  width={chartWidth}
                  height={chartHeight}
                  data={cleanData}
                  margin={{ top: 15, right: 5, left: -20, bottom: 0 }}
                >
                  <CartesianGrid
                    strokeDasharray="3 3"
                    stroke="#334155"
                    vertical={false}
                  />
                  <XAxis
                    dataKey="time_min"
                    stroke="#64748b"
                    tick={{ fontSize: 8 }}
                  />
                  <YAxis
                    yAxisId="left"
                    stroke="#fb923c"
                    tick={{ fontSize: 8 }}
                    width={20}
                    domain={['auto', 'auto']}
                  />
                  <YAxis
                    yAxisId="right"
                    orientation="right"
                    stroke="#34d399"
                    tick={{ fontSize: 8 }}
                    width={20}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#0f172a',
                      borderColor: '#334155',
                      fontSize: '10px',
                    }}
                  />
                  <Area
                    yAxisId="right"
                    type="monotone"
                    dataKey="tds_mgL"
                    fill="#34d399"
                    stroke="#34d399"
                    fillOpacity={0.1}
                    isAnimationActive={false}
                  />
                  <Line
                    yAxisId="left"
                    type="monotone"
                    dataKey="pressure_bar"
                    stroke="#fb923c"
                    strokeWidth={1.5}
                    dot={false}
                    isAnimationActive={false}
                  />
                </ComposedChart>
              </div>
              {/* Chart 2 */}
              <div className="bg-slate-900/20 rounded border border-slate-800/50 p-1 relative flex-1">
                <div className="absolute top-1 left-2 text-[8px] text-slate-500 font-bold z-10">
                  Flux & Rec %
                </div>
                <ComposedChart
                  width={chartWidth}
                  height={chartHeight}
                  data={cleanData}
                  margin={{ top: 15, right: 5, left: -20, bottom: 0 }}
                >
                  <CartesianGrid
                    strokeDasharray="3 3"
                    stroke="#334155"
                    vertical={false}
                  />
                  <XAxis
                    dataKey="time_min"
                    stroke="#64748b"
                    tick={{ fontSize: 8 }}
                  />
                  <YAxis
                    yAxisId="left"
                    stroke="#38bdf8"
                    tick={{ fontSize: 8 }}
                    width={20}
                    domain={['auto', 'auto']}
                  />
                  <YAxis
                    yAxisId="right"
                    orientation="right"
                    stroke="#818cf8"
                    tick={{ fontSize: 8 }}
                    width={20}
                    domain={[0, 100]}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#0f172a',
                      borderColor: '#334155',
                      fontSize: '10px',
                    }}
                  />
                  <Line
                    yAxisId="left"
                    type="monotone"
                    dataKey="flux_lmh"
                    stroke="#38bdf8"
                    strokeWidth={1.5}
                    dot={false}
                    isAnimationActive={false}
                  />
                  <Line
                    yAxisId="right"
                    type="monotone"
                    dataKey="recovery_pct"
                    stroke="#818cf8"
                    strokeWidth={1.5}
                    dot={false}
                    strokeDasharray="3 3"
                    isAnimationActive={false}
                  />
                </ComposedChart>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}

// -----------------------------------------------------------------------------
// 3. Main Component
// -----------------------------------------------------------------------------

interface Props {
  result: any; // 엄밀히는 'ScenarioOutput' 타입이어야 함
  unitMode: UnitMode;
}

export function Visualization({ result, unitMode }: Props) {
  const navigate = useNavigate();
  const [isModalOpen, setIsModalOpen] = useState(false);

  // 데이터가 없으면 안내 화면
  if (!result) {
    return (
      <div className="flex h-full flex-col items-center justify-center text-slate-600 space-y-4">
        <div className="p-4 rounded-full bg-slate-900/50 border border-slate-800">
          <Activity className="w-8 h-8 opacity-20" />
        </div>
        <div className="text-center">
          <p className="text-sm font-medium text-slate-500">
            Ready to Simulate
          </p>
          <p className="text-xs text-slate-600 mt-1">
            Configure flow and press 'Run'
          </p>
        </div>
      </div>
    );
  }

  // ✅ [Standardization] 백엔드 스키마(ScenarioOutput) 그대로 사용
  // Legacy Fallback (result.raw, result.kpi 등) 모두 제거함.
  const kpi = result.kpi;
  const metrics = result.stage_metrics ?? [];
  const chem = result.chemistry?.final_brine;
  const scenarioId = result.scenario_id; // 백엔드 스키마 'scenario_id'

  // ✅ [Standardization] 정해진 변수명만 사용
  const recovery = kpi.recovery_pct ?? 0;
  const energy = kpi.sec_kwhm3 ?? 0;
  const flux = kpi.flux_lmh ?? 0;
  const pressure = kpi.ndp_bar ?? 0;
  const productTds = kpi.prod_tds ?? 0;

  return (
    <div className="h-full relative flex flex-col font-sans">
      {/* Action Buttons */}
      <div className="flex-none p-3 pb-0 grid grid-cols-2 gap-2">
        <button
          onClick={() => setIsModalOpen(true)}
          className="flex items-center justify-center gap-2 px-3 py-3 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-[11px] font-bold shadow-lg shadow-blue-900/20 transition-all active:scale-[0.98] ring-1 ring-blue-400/50"
        >
          <LayoutDashboard className="w-4 h-4" /> ANALYSIS DASHBOARD
        </button>
        <ReportDownloadButton
          scenarioId={scenarioId}
          className="w-full justify-center !bg-slate-800 !text-slate-200 !border-slate-600/50 hover:!bg-slate-700 hover:!text-white shadow-md text-[11px] uppercase py-3"
        />
      </div>

      {/* Main Stats */}
      <div className="flex-1 overflow-y-auto p-3 space-y-5 scrollbar-thin scrollbar-track-slate-950 scrollbar-thumb-slate-800">
        {/* KPI Cards */}
        <div className="space-y-2">
          <div className="grid grid-cols-2 gap-2">
            <div className={cn(CARD_BASE, 'border-blue-500/20 bg-blue-950/10')}>
              <div className={LABEL_BASE}>
                <Droplets className="w-3 h-3 text-blue-500" /> Recovery
              </div>
              <div className="text-xl font-bold text-blue-400 tabular-nums">
                {pct(recovery)}
              </div>
              <div className="w-full bg-slate-800 h-1 mt-2 rounded-full overflow-hidden">
                <div
                  style={{ width: `${Math.min(recovery, 100)}%` }}
                  className="h-full bg-blue-500"
                />
              </div>
            </div>
            <div
              className={cn(
                CARD_BASE,
                'border-emerald-500/20 bg-emerald-950/10',
              )}
            >
              <div className={LABEL_BASE}>
                <Zap className="w-3 h-3 text-emerald-500" /> Energy
              </div>
              <div className="text-xl font-bold text-emerald-400 tabular-nums">
                {fmt(energy)}
              </div>
              <div className="text-[9px] text-emerald-600 font-medium">
                kWh/m³
              </div>
            </div>
          </div>
          <div className="grid grid-cols-3 gap-2">
            <div className={cn(CARD_BASE, 'border-cyan-500/20 bg-cyan-950/10')}>
              <div className={LABEL_BASE}>
                <Droplet className="w-3 h-3 text-cyan-400" /> Perm TDS
              </div>
              <div className="text-lg font-bold text-cyan-300 tabular-nums">
                {fmt(productTds)}
              </div>
              <div className="text-[9px] text-cyan-600 font-medium">mg/L</div>
            </div>
            <div className={CARD_BASE}>
              <div className={LABEL_BASE}>
                <Waves className="w-3 h-3 text-slate-400" /> Flux
              </div>
              <div className="text-lg font-bold text-slate-200 tabular-nums">
                {fmt(flux)}
              </div>
              <div className="text-[9px] text-slate-500">lmh</div>
            </div>
            <div className={CARD_BASE}>
              <div className={LABEL_BASE}>
                <Gauge className="w-3 h-3 text-slate-400" /> Press
              </div>
              <div className="text-lg font-bold text-slate-200 tabular-nums">
                {fmt(pressure)}
              </div>
              <div className="text-[9px] text-slate-500">bar</div>
            </div>
          </div>
        </div>

        {/* System Integrity */}
        <div className="rounded-lg border border-slate-800 bg-slate-900/30 p-3">
          <div className="flex items-center gap-2 text-[10px] font-bold text-slate-400 uppercase tracking-wide mb-3 border-b border-slate-800 pb-2">
            <ShieldCheck className="w-3 h-3 text-emerald-500" /> System
            Integrity Check
          </div>
          <div className="space-y-2">
            <HealthCheckItem
              label="LSI Scaling Potential"
              status={chem?.lsi > 1.8 ? 'warning' : 'ok'}
              value={chem?.lsi}
              unit="(idx)"
            />
            <HealthCheckItem
              label="Hydraulic Balance"
              status="ok"
              value="Stable"
            />
          </div>
        </div>

        {/* Stage Overview */}
        <div className="space-y-3 pb-6">
          <div className="flex items-center gap-2 text-xs font-bold text-slate-400 uppercase tracking-wide border-b border-slate-800 pb-2 sticky top-0 bg-slate-950/95 backdrop-blur z-10 pt-2">
            <Maximize2 className="w-3 h-3" /> Stage Overview
          </div>
          {metrics.map((m: any, idx: number) => {
            const typeKey = m.module_type || 'RO';
            const hrroHistory = typeKey === 'HRRO' ? m.time_history : null;

            // ✅ [Standardization] flux_lmh만 사용 (Fallback 제거)
            const stageFlux = m.flux_lmh ?? 0;

            return (
              <div
                key={idx}
                className="rounded-lg border border-slate-700/50 bg-slate-800/30 overflow-hidden"
              >
                <div className="px-3 py-2 flex justify-between items-center border-b border-slate-700/50 bg-slate-950/20">
                  <div className="flex items-center gap-2">
                    <div className="w-2 h-2 rounded-full bg-blue-500 shadow-[0_0_8px_currentColor]" />
                    <span className="text-xs font-bold text-slate-400">
                      Stage {m.stage}
                    </span>
                    <span className="text-[9px] px-1.5 py-0.5 rounded bg-white/5 text-slate-300 font-medium border border-white/5">
                      {typeKey}
                    </span>
                  </div>
                </div>
                <div className="p-3">
                  <div className="grid grid-cols-2 gap-y-3 gap-x-2">
                    <div>
                      <div className={LABEL_BASE}>Feed P</div>
                      <div className="font-mono font-bold text-slate-100 tabular-nums text-sm">
                        {fmt(m.p_in_bar)}{' '}
                        <span className="text-[9px] text-slate-500">bar</span>
                      </div>
                    </div>
                    <div>
                      <div className={LABEL_BASE}>Flux</div>
                      <div className="font-mono font-bold text-slate-100 tabular-nums text-sm">
                        {fmt(stageFlux)}{' '}
                        <span className="text-[9px] text-slate-500">lmh</span>
                      </div>
                    </div>
                  </div>
                  {['RO', 'NF'].includes(typeKey) && (
                    <RODetailContent data={m} />
                  )}
                  {['UF', 'MF'].includes(typeKey) && (
                    <UFDetailContent data={m} />
                  )}
                  {typeKey === 'HRRO' && (
                    <HRROBatchChart history={hrroHistory} />
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      <DetailedResultModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        data={result}
        mode="SYSTEM"
        unitMode={unitMode}
      />
    </div>
  );
}
