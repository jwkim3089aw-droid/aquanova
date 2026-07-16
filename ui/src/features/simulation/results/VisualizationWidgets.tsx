// ui/src/features/simulation/results/VisualizationWidgets.tsx
import React, { useLayoutEffect, useMemo, useRef, useState } from 'react';
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
  ArrowRight,
  ArrowDownRight,
  AlertTriangle,
  CheckCircle2,
  AlertOctagon,
} from 'lucide-react';
import { UnitMode, fmt, pct } from '../model/types';

export function cn(...classes: (string | undefined | null | false)[]) {
  return classes.filter(Boolean).join(' ');
}

export function n(v: any, fallback = 0) {
  const x = Number(v);
  return Number.isFinite(x) ? x : fallback;
}

export function getUnitLabel(
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

export function stageFlux(m: any) {
  return m?.flux_lmh ?? m?.jw_avg_lmh ?? null;
}

export const THEME = {
  primary: '#0F4C81',
  primaryLight: '#3B82F6',
  teal: '#26A69A',
  orange: '#F57C00',
  indigo: '#818CF8',
};

export const CARD_BASE =
  'rounded-lg border bg-slate-900/50 p-3 shadow-md transition-all hover:bg-slate-800/60 hover:border-slate-600 backdrop-blur-sm';
export const LABEL_BASE =
  'text-[10px] font-bold text-slate-400 uppercase tracking-wider flex items-center gap-1.5 mb-1.5';

export function useElementSize<T extends HTMLElement>() {
  const ref = useRef<T | null>(null);
  const [size, setSize] = useState({ width: 0, height: 0 });

  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    let raf = 0;
    const commit = (w: number, h: number) => {
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(() =>
        setSize((prev) =>
          prev.width === w && prev.height === h
            ? prev
            : { width: w, height: h },
        ),
      );
    };
    commit(el.clientWidth, el.clientHeight);
    const ro = new ResizeObserver((entries) => {
      const cr = entries[0]?.contentRect;
      if (cr) commit(cr.width, cr.height);
    });
    ro.observe(el);
    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
    };
  }, []);

  return { ref, size };
}

export function AutoSizedChart({
  className,
  children,
}: {
  className?: string;
  children: (w: number, h: number) => React.ReactNode;
}) {
  const { ref, size } = useElementSize<HTMLDivElement>();
  return (
    <div ref={ref} className={cn('w-full h-full min-w-0 min-h-0', className)}>
      {size.width > 0 && size.height > 0 ? (
        children(size.width, size.height)
      ) : (
        <div className="w-full h-full flex items-center justify-center text-[10px] text-slate-600">
          sizing...
        </div>
      )}
    </div>
  );
}

export function HealthCheckItem({
  label,
  status,
  value,
  unit,
}: {
  label: string;
  status: 'ok' | 'warning' | 'error' | 'inactive';
  value?: string | number;
  unit?: string;
}) {
  const styles = {
    ok: 'text-emerald-400 bg-emerald-950/30 border-emerald-500/30',
    warning: 'text-amber-400 bg-amber-950/30 border-amber-500/30',
    error: 'text-rose-400 bg-rose-950/30 border-rose-500/30',
    inactive: 'text-slate-500 bg-slate-900/30 border-slate-800/50',
  };
  const icons = {
    ok: <CheckCircle2 className="w-3.5 h-3.5" />,
    warning: <AlertTriangle className="w-3.5 h-3.5" />,
    error: <AlertOctagon className="w-3.5 h-3.5" />,
    inactive: (
      <div className="w-3.5 h-3.5 rounded-full border-2 border-slate-600" />
    ),
  };

  return (
    <div
      className={cn(
        'flex flex-col justify-between p-3 rounded-lg border gap-2 transition-colors',
        styles[status],
      )}
    >
      <div className="flex items-start gap-1.5 font-bold opacity-90 leading-tight">
        {icons[status]}{' '}
        <span className="text-[10.5px] break-keep">{label}</span>
      </div>
      <div className="text-right">
        {value != null ? (
          <div className="font-mono font-bold text-[13px] tracking-tight">
            {value}{' '}
            {unit && (
              <span className="text-[9px] ml-0.5 opacity-70">{unit}</span>
            )}
          </div>
        ) : (
          <div className="text-[10px] font-medium opacity-50">N/A</div>
        )}
      </div>
    </div>
  );
}

export function RODetailContent({
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
      <div className="rounded border border-slate-800 overflow-hidden text-[10px] leading-tight">
        <div className="grid grid-cols-4 bg-slate-800/80 font-bold text-slate-400 py-1.5 text-center">
          <div className="text-left pl-3">스트림 (Stream)</div>
          <div>유량 ({unitFlow})</div>
          <div>농도 (mg/L)</div>
          <div>압력 ({unitPress})</div>
        </div>
        {[
          {
            label: '유입 (Feed)',
            color: 'text-blue-400',
            flow: Qf,
            tds: Cf,
            press: p_in_bar,
            icon: <div className="w-1.5 h-1.5 rounded-full bg-blue-500" />,
          },
          {
            label: '생산 (Perm)',
            color: 'text-emerald-400',
            flow: Qp,
            tds: Cp,
            press: 0,
            icon: <ArrowRight className="w-2.5 h-2.5 text-emerald-500" />,
          },
          {
            label: '농축 (Conc)',
            color: 'text-orange-400',
            flow: Qc,
            tds: Cc,
            press: p_out_bar,
            icon: <ArrowDownRight className="w-2.5 h-2.5 text-orange-500" />,
          },
        ].map((row, i) => (
          <div
            key={i}
            className="grid grid-cols-4 py-1.5 items-center border-t border-slate-800/50 bg-slate-900/40 hover:bg-slate-800/60 transition-colors"
          >
            <div
              className={cn(
                'pl-3 flex items-center gap-1.5 font-bold whitespace-nowrap',
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

export function UFDetailContent({ data }: { data: any }) {
  if (!data) return null;
  const Qf = data.Qf ?? 0,
    Qp = data.Qp ?? 0,
    Qc = data.Qc ?? 0;
  const grossFlow = data.gross_flow_m3h ?? Qf;
  const netFlow = data.net_flow_m3h ?? Qp;
  const bwLoss = data.backwash_loss_m3h ?? Qc;
  const grossRecVal =
    data.recovery_pct ?? (grossFlow > 0 ? ((Qp + Qc) / grossFlow) * 100 : 0);
  let netRecVal = data.net_recovery_pct;
  if (!netRecVal || netRecVal === 0)
    netRecVal = grossFlow > 0 ? (netFlow / grossFlow) * 100 : 0;

  return (
    <div className="mt-3 pt-3 border-t border-dashed border-slate-700/50 space-y-3">
      <div className="grid grid-cols-2 gap-4">
        <div>
          <div className="flex justify-between text-[10px] uppercase font-bold text-slate-400 mb-1.5">
            <span>총 회수율 (Gross Rec)</span>
            <span className="text-blue-400">{pct(grossRecVal)}</span>
          </div>
          <div className="h-1.5 w-full bg-slate-800 rounded-full overflow-hidden">
            <div
              style={{ width: `${Math.min(grossRecVal, 100)}%` }}
              className="h-full bg-blue-500 shadow-[0_0_8px_#3b82f6]"
            />
          </div>
        </div>
        <div>
          <div className="flex justify-between text-[10px] uppercase font-bold text-slate-400 mb-1.5">
            <span>순 회수율 (Net Rec)</span>
            <span className="text-emerald-400">{pct(netRecVal)}</span>
          </div>
          <div className="h-1.5 w-full bg-slate-800 rounded-full overflow-hidden flex shadow-inner">
            <div
              style={{ width: `${Math.min(netRecVal, 100)}%` }}
              className="bg-emerald-500"
            />
            <div
              style={{ width: `${Math.max(0, grossRecVal - netRecVal)}%` }}
              className="bg-rose-500/50"
            />
          </div>
        </div>
      </div>
      <div className="grid grid-cols-3 gap-2">
        <div className="bg-slate-900/60 p-2.5 rounded border border-slate-700/50 flex flex-col justify-center">
          <div className="text-[10px] text-slate-400 uppercase font-bold truncate mb-1">
            총 유량 (Gross Flow)
          </div>
          <div className="font-mono text-[13px] font-bold text-blue-300">
            {fmt(grossFlow)}
          </div>
        </div>
        <div className="bg-rose-950/20 p-2.5 rounded border border-rose-900/30 flex flex-col justify-center">
          <div className="text-[10px] text-rose-400/80 uppercase font-bold truncate mb-1">
            역세 손실 (BW Loss)
          </div>
          <div className="font-mono text-[13px] font-bold text-rose-400">
            -{fmt(bwLoss)}
          </div>
        </div>
        <div className="bg-emerald-950/20 p-2.5 rounded border border-emerald-900/30 flex flex-col justify-center">
          <div className="text-[10px] text-emerald-500/80 uppercase font-bold truncate mb-1">
            순 유량 (Net Flow)
          </div>
          <div className="font-mono text-[13px] font-bold text-emerald-400">
            {fmt(netFlow)}
          </div>
        </div>
      </div>
    </div>
  );
}

export function HRROBatchChart({
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

  return (
    <div className="mt-3 pt-3 border-t border-dashed border-slate-700/50">
      <div className="flex items-center justify-between mb-2">
        <div className="text-[10.5px] font-bold text-slate-400 uppercase flex gap-1.5">
          <Activity className="w-3.5 h-3.5" /> HRRO 배치 사이클 (Batch Cycle)
        </div>
      </div>
      {!hasData ? (
        <div className="rounded border border-slate-800/50 bg-slate-900/40 p-3 text-[10px] text-slate-500 text-center">
          시계열 데이터가 없습니다.
        </div>
      ) : (
        <div className="flex w-full h-[170px] overflow-hidden gap-3 min-w-0 min-h-0">
          <div className="bg-slate-950/40 rounded-lg border border-slate-800 p-1.5 relative flex-1 min-w-0 min-h-0 shadow-inner">
            <div className="absolute top-1.5 left-2.5 text-[9px] text-slate-400 font-bold z-10 tracking-wide">
              압력 및 농도 (Press &amp; TDS)
            </div>
            <AutoSizedChart className="pt-[16px]">
              {(w, h) => (
                <ComposedChart
                  width={w}
                  height={h}
                  data={cleanData}
                  margin={{ top: 5, right: 5, left: 0, bottom: 0 }}
                >
                  <CartesianGrid
                    strokeDasharray="3 3"
                    stroke="#334155"
                    vertical={false}
                  />
                  <XAxis
                    dataKey="time_min"
                    stroke="#64748b"
                    tick={{ fontSize: 9 }}
                  />
                  <YAxis
                    yAxisId="left"
                    stroke={THEME.orange}
                    tick={{ fontSize: 9 }}
                    width={28}
                  />
                  <YAxis
                    yAxisId="right"
                    orientation="right"
                    stroke={THEME.teal}
                    tick={{ fontSize: 9 }}
                    width={28}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#0f172a',
                      borderColor: '#334155',
                      fontSize: '11px',
                      borderRadius: '6px',
                    }}
                  />
                  <Area
                    yAxisId="right"
                    type="monotone"
                    dataKey="tds_mgL"
                    fill={THEME.teal}
                    stroke={THEME.teal}
                    fillOpacity={0.15}
                    isAnimationActive={false}
                    name="농도 (TDS)"
                  />
                  <Line
                    yAxisId="left"
                    type="monotone"
                    dataKey="pressure_bar"
                    stroke={THEME.orange}
                    strokeWidth={2}
                    dot={false}
                    isAnimationActive={false}
                    name={`압력 (${unitPress})`}
                  />
                </ComposedChart>
              )}
            </AutoSizedChart>
          </div>
          <div className="bg-slate-950/40 rounded-lg border border-slate-800 p-1.5 relative flex-1 min-w-0 min-h-0 shadow-inner">
            <div className="absolute top-1.5 left-2.5 text-[9px] text-slate-400 font-bold z-10 tracking-wide">
              플럭스 및 회수율 (Flux &amp; Rec %)
            </div>
            <AutoSizedChart className="pt-[16px]">
              {(w, h) => (
                <ComposedChart
                  width={w}
                  height={h}
                  data={cleanData}
                  margin={{ top: 5, right: 5, left: 0, bottom: 0 }}
                >
                  <CartesianGrid
                    strokeDasharray="3 3"
                    stroke="#334155"
                    vertical={false}
                  />
                  <XAxis
                    dataKey="time_min"
                    stroke="#64748b"
                    tick={{ fontSize: 9 }}
                  />
                  <YAxis
                    yAxisId="left"
                    stroke={THEME.primaryLight}
                    tick={{ fontSize: 9 }}
                    width={28}
                  />
                  <YAxis
                    yAxisId="right"
                    orientation="right"
                    stroke={THEME.indigo}
                    tick={{ fontSize: 9 }}
                    width={28}
                    domain={[0, 100]}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#0f172a',
                      borderColor: '#334155',
                      fontSize: '11px',
                      borderRadius: '6px',
                    }}
                  />
                  <Line
                    yAxisId="left"
                    type="monotone"
                    dataKey="flux_lmh"
                    stroke={THEME.primaryLight}
                    strokeWidth={2}
                    dot={false}
                    isAnimationActive={false}
                    name={`플럭스 (${unitFlux})`}
                  />
                  <Line
                    yAxisId="right"
                    type="monotone"
                    dataKey="recovery_pct"
                    stroke={THEME.indigo}
                    strokeWidth={2}
                    dot={false}
                    strokeDasharray="4 4"
                    isAnimationActive={false}
                    name="회수율 (%)"
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
