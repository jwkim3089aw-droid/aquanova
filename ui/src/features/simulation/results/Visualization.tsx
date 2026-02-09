// ui/src/features/simulation/results/Visualization.tsx

import React, {
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
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
  FileText,
} from 'lucide-react';

import { UnitMode, fmt, pct } from '../model/types';
import { DetailedResultModal } from '../../../components/common/DetailedResultModal';

// -----------------------------------------------------------------------------
// Utilities
// -----------------------------------------------------------------------------
function cn(...classes: (string | undefined | null | false)[]) {
  return classes.filter(Boolean).join(' ');
}

function n(v: any, fallback = 0) {
  const x = Number(v);
  return Number.isFinite(x) ? x : fallback;
}

function getUnitLabel(
  result: any,
  key: 'flow' | 'pressure' | 'temperature' | 'flux',
  unitMode: UnitMode,
) {
  const u = result?.unit_labels ?? {};
  if (u?.[key]) return String(u[key]);

  if (key === 'flow') return unitMode === 'US' ? 'gpm' : 'm³/h';
  if (key === 'pressure') return unitMode === 'US' ? 'psi' : 'bar';
  if (key === 'temperature') return unitMode === 'US' ? '°F' : '°C';
  return unitMode === 'US' ? 'gfd' : 'LMH';
}

function stageFlux(m: any) {
  return m?.flux_lmh ?? m?.jw_avg_lmh ?? null;
}

const CARD_BASE =
  'rounded-lg border bg-slate-900/40 p-3 shadow-sm transition-all hover:bg-slate-900/60 hover:border-slate-700';
const LABEL_BASE =
  'text-[10px] font-bold text-slate-500 uppercase tracking-wider flex items-center gap-1.5 mb-1';

// -----------------------------------------------------------------------------
// ResizeObserver 기반 사이즈 측정 (ResponsiveContainer 대체)
// -----------------------------------------------------------------------------
function useElementSize<T extends HTMLElement>() {
  const ref = useRef<T | null>(null);
  const [size, setSize] = useState({ width: 0, height: 0 });

  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;

    let raf = 0;

    const commit = (w: number, h: number) => {
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(() => {
        const width = Math.max(0, Math.floor(w));
        const height = Math.max(0, Math.floor(h));
        setSize((prev) =>
          prev.width === width && prev.height === height
            ? prev
            : { width, height },
        );
      });
    };

    // 초기값
    const r = el.getBoundingClientRect();
    commit(r.width, r.height);

    const ro = new ResizeObserver((entries) => {
      const cr = entries[0]?.contentRect;
      if (!cr) return;
      commit(cr.width, cr.height);
    });

    ro.observe(el);

    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
    };
  }, []);

  return { ref, size };
}

function AutoSizedChart({
  className,
  children,
}: {
  className?: string;
  children: (w: number, h: number) => React.ReactNode;
}) {
  const { ref, size } = useElementSize<HTMLDivElement>();
  const w = size.width;
  const h = size.height;

  return (
    <div ref={ref} className={cn('w-full h-full min-w-0 min-h-0', className)}>
      {w > 0 && h > 0 ? (
        children(w, h)
      ) : (
        <div className="w-full h-full flex items-center justify-center text-[10px] text-slate-600">
          sizing...
        </div>
      )}
    </div>
  );
}

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
  } as const;
  const icons = {
    ok: <CheckCircle2 className="w-3 h-3" />,
    warning: <AlertTriangle className="w-3 h-3" />,
    error: <AlertOctagon className="w-3 h-3" />,
  } as const;

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
      {value !== undefined && value !== null ? (
        <div className="font-mono font-bold opacity-80">
          {value as any}
          <span className="text-[10px] ml-0.5 opacity-60">{unit}</span>
        </div>
      ) : null}
    </div>
  );
}

// [RO/NF Detail]
function RODetailContent({
  data,
  unitPress,
  unitFlow,
}: {
  data: any;
  unitPress: string;
  unitFlow: string;
}) {
  if (!data) return null;
  const { Qf, Qp, Qc, Cf, Cp, Cc, p_in_bar, p_out_bar } = data;

  return (
    <div className="mt-3 pt-3 border-t border-dashed border-slate-700/50 space-y-3">
      <div className="rounded border border-slate-800 overflow-hidden text-[9px] leading-tight">
        <div className="grid grid-cols-4 bg-slate-800/80 font-bold text-slate-400 py-1 text-center">
          <div className="text-left pl-2">Stream</div>
          <div>Flow ({unitFlow})</div>
          <div>TDS (mg/L)</div>
          <div>Press ({unitPress})</div>
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

// [UF/MF Detail]
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

// [HRRO Chart]
function HRROBatchChart({
  history,
  unitPress,
  unitFlux,
}: {
  history: any[] | null;
  unitPress: string;
  unitFlux: string;
}) {
  const hasData = !!history && history.length > 0;

  const cleanData = useMemo(() => {
    if (!hasData || !history) return [];
    return history.map((d) => ({
      ...d,
      time_min: n(d.time_min),
      pressure_bar: n(d.pressure_bar),
      tds_mgL: n(d.tds_mgL),
      flux_lmh: n(d.flux_lmh),
      recovery_pct: n(d.recovery_pct),
    }));
  }, [history, hasData]);

  // 데이터 들어오는 타이밍에 레이아웃 갱신 트리거(안전장치)
  useEffect(() => {
    if (!hasData) return;
    const raf = requestAnimationFrame(() =>
      window.dispatchEvent(new Event('resize')),
    );
    return () => cancelAnimationFrame(raf);
  }, [hasData, cleanData.length]);

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
        <div className="flex w-full h-[160px] overflow-hidden gap-2 min-w-0 min-h-0">
          <div className="bg-slate-900/20 rounded border border-slate-800/50 p-1 relative flex-1 min-w-0 min-h-0">
            <div className="absolute top-1 left-2 text-[8px] text-slate-500 font-bold z-10">
              Press &amp; TDS
            </div>

            <AutoSizedChart className="pt-[12px]">
              {(w, h) => (
                <ComposedChart
                  width={w}
                  height={h}
                  data={cleanData}
                  margin={{ top: 6, right: 8, left: 0, bottom: 0 }}
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
                    width={30}
                    domain={['auto', 'auto']}
                  />
                  <YAxis
                    yAxisId="right"
                    orientation="right"
                    stroke="#34d399"
                    tick={{ fontSize: 8 }}
                    width={30}
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
                    fillOpacity={0.12}
                    isAnimationActive={false}
                    name="TDS (mg/L)"
                  />
                  <Line
                    yAxisId="left"
                    type="monotone"
                    dataKey="pressure_bar"
                    stroke="#fb923c"
                    strokeWidth={1.5}
                    dot={false}
                    isAnimationActive={false}
                    name={`Pressure (${unitPress})`}
                  />
                </ComposedChart>
              )}
            </AutoSizedChart>
          </div>

          <div className="bg-slate-900/20 rounded border border-slate-800/50 p-1 relative flex-1 min-w-0 min-h-0">
            <div className="absolute top-1 left-2 text-[8px] text-slate-500 font-bold z-10">
              Flux &amp; Rec %
            </div>

            <AutoSizedChart className="pt-[12px]">
              {(w, h) => (
                <ComposedChart
                  width={w}
                  height={h}
                  data={cleanData}
                  margin={{ top: 6, right: 8, left: 0, bottom: 0 }}
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
                    width={30}
                    domain={['auto', 'auto']}
                  />
                  <YAxis
                    yAxisId="right"
                    orientation="right"
                    stroke="#818cf8"
                    tick={{ fontSize: 8 }}
                    width={30}
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
                    name={`Flux (${unitFlux})`}
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
                    name="Recovery (%)"
                  />
                </ComposedChart>
              )}
            </AutoSizedChart>
          </div>
        </div>
      )}
    </div>
  );
}

// -----------------------------------------------------------------------------
// Main Component
// -----------------------------------------------------------------------------
interface Props {
  result: any;
  unitMode: UnitMode;
}

export function Visualization({ result, unitMode }: Props) {
  const navigate = useNavigate();
  const [isModalOpen, setIsModalOpen] = useState(false);

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

  const unitFlow = getUnitLabel(result, 'flow', unitMode);
  const unitPress = getUnitLabel(result, 'pressure', unitMode);
  const unitFlux = getUnitLabel(result, 'flux', unitMode);

  const kpi = result.kpi ?? {};
  const metrics = result.stage_metrics ?? [];
  const chemFinal = result.chemistry?.final_brine;
  const scenarioId = result.scenario_id;

  const recovery = n(kpi.recovery_pct);
  const energy = n(kpi.sec_kwhm3);
  const flux = n(kpi.flux_lmh ?? kpi.jw_avg_lmh);
  const pressure = n(kpi.ndp_bar);
  const productTds = n(kpi.prod_tds);

  const lsi = chemFinal?.lsi;
  const lsiNum = Number(lsi);
  const lsiStatus = Number.isFinite(lsiNum) && lsiNum > 1.8 ? 'warning' : 'ok';

  const onOpenDetailedReport = () => {
    navigate('/reports', {
      state: {
        data: result,
        mode: 'SYSTEM',
        meta: {
          scenario_id: scenarioId ?? null,
          unitMode,
          source: 'Visualization',
          opened_at: new Date().toISOString(),
        },
      },
    });
  };

  return (
    <div className="h-full relative flex flex-col font-sans min-h-0 min-w-0">
      <div className="flex-none p-3 pb-0 grid grid-cols-2 gap-2">
        <button
          onClick={() => setIsModalOpen(true)}
          className="flex items-center justify-center gap-2 px-3 py-3 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-[11px] font-bold shadow-lg shadow-blue-900/20 transition-all active:scale-[0.98] ring-1 ring-blue-400/50"
        >
          <LayoutDashboard className="w-4 h-4" /> ANALYSIS DASHBOARD
        </button>

        <button
          onClick={onOpenDetailedReport}
          className="flex items-center justify-center gap-2 px-3 py-3 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-[11px] font-bold shadow-lg shadow-emerald-900/20 transition-all active:scale-[0.98] ring-1 ring-emerald-400/50"
          title="Open Detailed Report (UI render → client PDF export)"
        >
          <FileText className="w-4 h-4" /> DETAILED REPORT
        </button>
      </div>

      <div className="flex-1 min-h-0 overflow-y-auto p-3 space-y-5 scrollbar-thin scrollbar-track-slate-950 scrollbar-thumb-slate-800">
        {/* KPI cards */}
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
              <div className="text-[9px] text-slate-500">{unitFlux}</div>
            </div>

            <div className={CARD_BASE}>
              <div className={LABEL_BASE}>
                <Gauge className="w-3 h-3 text-slate-400" /> Press
              </div>
              <div className="text-lg font-bold text-slate-200 tabular-nums">
                {fmt(pressure)}
              </div>
              <div className="text-[9px] text-slate-500">{unitPress}</div>
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
              status={lsiStatus}
              value={lsi}
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
        <div className="space-y-3 pb-6 min-w-0">
          <div className="flex items-center gap-2 text-xs font-bold text-slate-400 uppercase tracking-wide border-b border-slate-800 pb-2 sticky top-0 bg-slate-950/95 backdrop-blur z-10 pt-2">
            <Maximize2 className="w-3 h-3" /> Stage Overview
          </div>

          {metrics.map((m: any, idx: number) => {
            const typeKey = String(m.module_type || 'RO').toUpperCase();
            const hrroHistory =
              typeKey === 'HRRO' ? (m.time_history ?? null) : null;
            const vioCount =
              typeKey === 'HRRO' ? (m?.chemistry?.violations?.length ?? 0) : 0;

            const sFlux = stageFlux(m) ?? 0;

            return (
              <div
                key={`${m.stage ?? idx}-${typeKey}`}
                className="rounded-lg border border-slate-700/50 bg-slate-800/30 overflow-hidden min-w-0"
              >
                <div className="px-3 py-2 flex justify-between items-center border-b border-slate-700/50 bg-slate-950/20">
                  <div className="flex items-center gap-2 min-w-0">
                    <div className="w-2 h-2 rounded-full bg-blue-500 shadow-[0_0_8px_currentColor]" />
                    <span className="text-xs font-bold text-slate-400">
                      Stage {m.stage}
                    </span>
                    <span className="text-[9px] px-1.5 py-0.5 rounded bg-white/5 text-slate-300 font-medium border border-white/5">
                      {typeKey}
                    </span>

                    {typeKey === 'HRRO' ? (
                      <span
                        className={cn(
                          'text-[9px] px-1.5 py-0.5 rounded font-bold border',
                          vioCount > 0
                            ? 'bg-rose-500/10 text-rose-300 border-rose-500/20'
                            : 'bg-emerald-500/10 text-emerald-300 border-emerald-500/20',
                        )}
                        title="HRRO guideline violations"
                      >
                        {vioCount > 0 ? `VIOL ${vioCount}` : 'OK'}
                      </span>
                    ) : null}
                  </div>
                </div>

                <div className="p-3 min-w-0">
                  <div className="grid grid-cols-2 gap-y-3 gap-x-2">
                    <div>
                      <div className={LABEL_BASE}>Feed P</div>
                      <div className="font-mono font-bold text-slate-100 tabular-nums text-sm">
                        {fmt(m.p_in_bar)}{' '}
                        <span className="text-[9px] text-slate-500">
                          {unitPress}
                        </span>
                      </div>
                    </div>
                    <div>
                      <div className={LABEL_BASE}>Flux</div>
                      <div className="font-mono font-bold text-slate-100 tabular-nums text-sm">
                        {fmt(sFlux)}{' '}
                        <span className="text-[9px] text-slate-500">
                          {unitFlux}
                        </span>
                      </div>
                    </div>
                  </div>

                  {['RO', 'NF'].includes(typeKey) && (
                    <RODetailContent
                      data={m}
                      unitPress={unitPress}
                      unitFlow={unitFlow}
                    />
                  )}
                  {['UF', 'MF'].includes(typeKey) && (
                    <UFDetailContent data={m} />
                  )}
                  {typeKey === 'HRRO' && (
                    <HRROBatchChart
                      history={hrroHistory}
                      unitPress={unitPress}
                      unitFlux={unitFlux}
                    />
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
