// ui/src/components/common/DetailedResultModal.tsx
// ✅ [FIXED VERSION] Missing Icons Imported (Loader2, Beaker added)

import React, { useState, useEffect, useMemo, useRef } from 'react';
import {
  X,
  Calculator,
  Globe,
  Layers,
  ChevronRight,
  LayoutDashboard,
  FlaskConical,
  Waves,
  Zap,
  Clock,
  Table2,
  Activity,
  Droplet,
  ArrowRight,
  AlertCircle,
  CheckCircle2, // ✅ 추가됨
  AlertTriangle, // ✅ 추가됨
  Loader2, // ✅ 추가됨 (에러 원인)
  Beaker, // ✅ 추가됨
} from 'lucide-react';
import {
  ComposedChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Area,
  ReferenceLine,
} from 'recharts';
import { fmt, pct, UnitMode } from '../../features/simulation/model/types';

// --- STYLING CONSTANTS (Professional Dark Theme) ---
const STYLES = {
  OVERLAY:
    'fixed inset-0 z-[9999] flex items-center justify-center bg-black/80 backdrop-blur-md animate-in fade-in duration-200',
  CONTAINER:
    'w-[95vw] max-w-[1600px] h-[92vh] bg-[#0b1120] border border-slate-700 rounded-xl shadow-2xl flex flex-col overflow-hidden ring-1 ring-white/10 font-sans',
  HEADER:
    'flex-none h-16 border-b border-slate-700 bg-[#0f172a] flex items-center justify-between px-6 select-none shrink-0',
  SIDEBAR:
    'w-72 bg-[#0f172a] border-r border-slate-700 flex flex-col overflow-y-auto shrink-0 scrollbar-thin scrollbar-thumb-slate-800',
  CONTENT: 'flex-1 flex flex-col bg-[#0b1120] relative min-w-0 overflow-hidden',
  TAB_BAR:
    'flex-none border-b border-slate-700 bg-[#1e293b]/50 backdrop-blur-sm flex px-4 gap-1',
  SCROLL_AREA:
    'flex-1 overflow-y-auto p-0 scrollbar-thin scrollbar-thumb-slate-700',

  // Tables
  TH: 'px-4 py-3 text-left font-semibold text-slate-500 uppercase text-[10px] bg-slate-900/90 border-b border-slate-700 sticky top-0 backdrop-blur-md z-10',
  TD: 'px-4 py-3 text-right font-mono text-slate-300 border-b border-slate-800/50 text-[11px] tabular-nums',
  TD_L: 'px-4 py-3 text-left font-bold text-slate-400 border-b border-slate-800/50 text-[11px]',
};

interface DetailedResultModalProps {
  isOpen: boolean;
  onClose: () => void;
  data: any;
  mode: 'SYSTEM' | 'STAGE';
  unitMode: UnitMode;
}

export function DetailedResultModal({
  isOpen,
  onClose,
  data,
}: DetailedResultModalProps) {
  // --- STATE ---
  const [selectedScope, setSelectedScope] = useState<'SYSTEM' | number>(
    'SYSTEM',
  );
  const [activeTab, setActiveTab] = useState<string>('summary');

  // --- CHART SIZING LOGIC (The Fix) ---
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const [chartSize, setChartSize] = useState({ width: 0, height: 0 });

  // Init on Open
  useEffect(() => {
    if (isOpen) {
      setSelectedScope('SYSTEM');
      setActiveTab('summary');
    }
  }, [isOpen]);

  // ResizeObserver: Measures the div size exactly to prevent Recharts 0-width bug
  useEffect(() => {
    if (activeTab === 'profile' && chartContainerRef.current) {
      const observer = new ResizeObserver((entries) => {
        const { width, height } = entries[0].contentRect;
        // Use requestAnimationFrame to avoid "ResizeObserver loop limit exceeded"
        requestAnimationFrame(() => {
          setChartSize({ width, height });
        });
      });
      observer.observe(chartContainerRef.current);
      return () => observer.disconnect();
    }
  }, [activeTab, isOpen, selectedScope]);

  // --- DATA PROCESSING ---
  const safeData = data || {};
  const kpi = safeData.kpi || {};
  const stages = safeData.stage_metrics || [];
  const chemistry = safeData.chemistry || {};

  const currentData = useMemo(() => {
    return selectedScope === 'SYSTEM'
      ? { ...safeData, ...kpi }
      : stages[selectedScope] || {};
  }, [safeData, kpi, stages, selectedScope]);

  const isSystemView = selectedScope === 'SYSTEM';
  const isHRRO = currentData.module_type === 'HRRO';

  // --- CHART DATA MAPPING ---
  const chartData = useMemo(() => {
    if (!currentData) return [];

    // HRRO: Time History (Dynamic Cycle)
    if (
      isHRRO &&
      currentData.time_history &&
      Array.isArray(currentData.time_history)
    ) {
      return currentData.time_history.map((d: any) => ({
        ...d,
        flux_lmh: Number(d.flux_lmh || 0),
        pressure_bar: Number(d.pressure_bar || 0),
        recovery_pct: Number(d.recovery_pct || 0),
        time_min: Number(d.time_min || 0),
      }));
    }
    // RO/NF: Element Profile (Static)
    return currentData.element_profile || [];
  }, [currentData, isHRRO]);

  // --- MASS BALANCE LOGIC ---
  let feed, perm, conc;
  if (isSystemView) {
    feed = safeData.streams?.find((s: any) => s.label === 'Feed');
    perm = safeData.streams?.find((s: any) => s.label === 'Product');
    conc = safeData.streams?.find((s: any) => s.label === 'Brine');
  } else {
    feed = {
      flow_m3h: currentData.Qf,
      tds_mgL: currentData.Cf,
      pressure_bar: currentData.p_in_bar,
    };
    perm = {
      flow_m3h: currentData.Qp,
      tds_mgL: currentData.Cp,
      pressure_bar: 0,
    };
    conc = {
      flow_m3h: currentData.Qc,
      tds_mgL: currentData.Cc,
      pressure_bar: currentData.p_out_bar,
    };
  }

  // Display Values
  const displayRecovery = currentData.recovery_pct || 0;
  const displayEnergy = currentData.sec_kwhm3 || 0;
  const displayFlux = currentData.jw_avg_lmh || currentData.flux_lmh || 0;
  const displayNDP = currentData.ndp_bar || 0;

  if (!isOpen || !data) return null;

  return (
    <div className={STYLES.OVERLAY}>
      <div className={STYLES.CONTAINER}>
        {/* === 1. HEADER === */}
        <div className={STYLES.HEADER}>
          <div className="flex items-center gap-4">
            <div className="bg-gradient-to-br from-blue-600 to-indigo-700 p-2.5 rounded-lg text-white shadow-lg shadow-blue-900/20 ring-1 ring-white/10">
              <Calculator className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-bold text-slate-100 tracking-tight">
                Process Analysis & Audit
              </h2>
              <div className="flex items-center gap-2 text-[11px] text-slate-500 font-mono mt-0.5">
                <span className="bg-slate-800 px-1.5 rounded text-slate-400 border border-slate-700">
                  ID: {safeData.scenario_id?.slice(0, 8) || 'N/A'}
                </span>
                <span className="w-1 h-1 bg-slate-600 rounded-full mx-1" />
                <span
                  className={
                    isSystemView
                      ? 'text-blue-400 font-bold'
                      : 'text-emerald-400 font-bold'
                  }
                >
                  {isSystemView
                    ? 'System Overview'
                    : `Stage ${Number(selectedScope) + 1}: ${currentData.module_type}`}
                </span>
              </div>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-slate-800 rounded-lg text-slate-400 hover:text-white transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="flex flex-1 overflow-hidden">
          {/* === 2. SIDEBAR NAVIGATION === */}
          <div className={STYLES.SIDEBAR}>
            <div className="p-4 pt-6 pb-2 text-[10px] font-bold text-slate-500 uppercase tracking-wider flex items-center gap-2">
              <Globe className="w-3 h-3" /> System Boundary
            </div>
            <SidebarBtn
              active={selectedScope === 'SYSTEM'}
              onClick={() => setSelectedScope('SYSTEM')}
              icon={LayoutDashboard}
              label="Overall Plant"
            />

            <div className="mt-6 mb-2 px-4 text-[10px] font-bold text-slate-500 uppercase tracking-wider flex items-center gap-2">
              <Layers className="w-3 h-3" /> Process Stages
            </div>
            <div className="space-y-0.5 px-2">
              {stages.map((s: any, idx: number) => (
                <SidebarBtn
                  key={idx}
                  active={selectedScope === idx}
                  onClick={() => setSelectedScope(idx)}
                  icon={s.module_type === 'HRRO' ? Clock : Waves}
                  label={`Stage ${s.stage}`}
                  badge={s.module_type}
                />
              ))}
            </div>
          </div>

          {/* === 3. MAIN CONTENT AREA === */}
          <div className={STYLES.CONTENT}>
            {/* TABS */}
            <div className={STYLES.TAB_BAR}>
              <TabBtn
                active={activeTab === 'summary'}
                onClick={() => setActiveTab('summary')}
                icon={Activity}
                label="Overview"
              />
              {/* Show Graph tab only if HRRO or data exists */}
              {!isSystemView && (isHRRO || chartData.length > 0) && (
                <TabBtn
                  active={activeTab === 'profile'}
                  onClick={() => setActiveTab('profile')}
                  icon={isHRRO ? Clock : Waves}
                  label={isHRRO ? 'Dynamic Cycle' : 'Pressure Profile'}
                />
              )}
              <TabBtn
                active={activeTab === 'chemistry'}
                onClick={() => setActiveTab('chemistry')}
                icon={FlaskConical}
                label="Chemistry"
              />
              <TabBtn
                active={activeTab === 'power'}
                onClick={() => setActiveTab('power')}
                icon={Zap}
                label="Energy"
              />
            </div>

            <div className={STYLES.SCROLL_AREA}>
              {/* --- TAB: SUMMARY --- */}
              {activeTab === 'summary' && (
                <div className="p-8 max-w-[1400px] mx-auto grid grid-cols-12 gap-6 animate-in fade-in slide-in-from-bottom-2 duration-300">
                  {/* Left: Tables */}
                  <div className="col-span-12 xl:col-span-8 space-y-6">
                    {/* Mass Balance Table */}
                    <div className="rounded-xl border border-slate-700 bg-[#1e293b]/30 overflow-hidden shadow-sm">
                      <div className="bg-slate-800/80 px-5 py-3 border-b border-slate-700 flex justify-between items-center backdrop-blur-md">
                        <span className="text-sm font-bold text-slate-200 flex items-center gap-2">
                          <Table2 className="w-4 h-4 text-blue-400" /> Mass
                          Balance
                        </span>
                        <span className="text-[10px] text-slate-500 bg-slate-900 px-2 py-1 rounded border border-slate-800">
                          {isSystemView
                            ? 'Plant Boundary'
                            : `Stage ${currentData.stage} Boundary`}
                        </span>
                      </div>
                      <table className="w-full text-sm">
                        <thead>
                          <tr>
                            <th className={STYLES.TH}>Stream</th>
                            <th className={STYLES.TH + ' text-right'}>
                              Flow (m³/h)
                            </th>
                            <th className={STYLES.TH + ' text-right'}>
                              TDS (mg/L)
                            </th>
                            <th className={STYLES.TH + ' text-right'}>
                              Pressure (bar)
                            </th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-800/50">
                          <Row
                            label="Feed"
                            color="text-blue-400"
                            icon={
                              <ArrowRight className="w-3 h-3 text-blue-500" />
                            }
                            flow={feed?.flow_m3h}
                            tds={feed?.tds_mgL}
                            press={feed?.pressure_bar}
                          />
                          <Row
                            label="Permeate (Product)"
                            color="text-emerald-400"
                            icon={
                              <ArrowRight className="w-3 h-3 text-emerald-500" />
                            }
                            flow={perm?.flow_m3h}
                            tds={perm?.tds_mgL}
                            press={perm?.pressure_bar}
                          />
                          <Row
                            label="Concentrate (Brine)"
                            color="text-orange-400"
                            icon={
                              <ArrowRight className="w-3 h-3 text-orange-500" />
                            }
                            flow={conc?.flow_m3h}
                            tds={conc?.tds_mgL}
                            press={conc?.pressure_bar}
                          />
                        </tbody>
                      </table>
                    </div>

                    {/* Stage Breakdown (System View) */}
                    {isSystemView && stages.length > 0 && (
                      <div className="rounded-xl border border-slate-700 bg-[#1e293b]/30 overflow-hidden shadow-sm">
                        <div className="bg-slate-800/80 px-5 py-3 border-b border-slate-700">
                          <span className="text-sm font-bold text-slate-200 flex items-center gap-2">
                            <Layers className="w-4 h-4 text-purple-400" /> Stage
                            Performance
                          </span>
                        </div>
                        <table className="w-full text-sm">
                          <thead>
                            <tr>
                              <th className={STYLES.TH}>Stage</th>
                              <th className={STYLES.TH + ' text-right'}>
                                Recovery
                              </th>
                              <th className={STYLES.TH + ' text-right'}>
                                Avg Flux
                              </th>
                              <th className={STYLES.TH + ' text-right'}>NDP</th>
                              <th className={STYLES.TH + ' text-right'}>
                                Energy
                              </th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-slate-800/50">
                            {stages.map((s: any, i: number) => (
                              <tr
                                key={i}
                                className="hover:bg-white/5 transition-colors cursor-pointer"
                                onClick={() => setSelectedScope(i)}
                              >
                                <td className={`${STYLES.TD_L} pl-6`}>
                                  <span className="font-mono text-slate-500">
                                    #{s.stage}
                                  </span>{' '}
                                  <span className="text-slate-200 ml-1">
                                    {s.module_type}
                                  </span>
                                </td>
                                <td className={STYLES.TD}>
                                  <span
                                    className={
                                      s.recovery_pct > 0
                                        ? 'text-emerald-400'
                                        : 'text-slate-500'
                                    }
                                  >
                                    {pct(s.recovery_pct)}
                                  </span>
                                </td>
                                <td className={STYLES.TD}>
                                  {fmt(s.jw_avg_lmh)}
                                </td>
                                <td className={STYLES.TD}>{fmt(s.ndp_bar)}</td>
                                <td className={STYLES.TD}>
                                  {fmt(s.sec_kwhm3)}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </div>

                  {/* Right: KPIs */}
                  <div className="col-span-12 xl:col-span-4 space-y-4">
                    <BigKPI
                      label="System Recovery"
                      value={displayRecovery}
                      unit="%"
                      icon={Droplet}
                      color="blue"
                      subValue={isHRRO ? 'Batch Operation' : 'Continuous'}
                    />
                    <BigKPI
                      label="Specific Energy"
                      value={displayEnergy}
                      unit="kWh/m³"
                      icon={Zap}
                      color="yellow"
                      subValue="Pumping Power"
                    />
                    <div className="grid grid-cols-2 gap-4">
                      <MiniKPI
                        label="Avg Flux"
                        value={fmt(displayFlux)}
                        unit="lmh"
                      />
                      <MiniKPI
                        label="Avg NDP"
                        value={fmt(displayNDP)}
                        unit="bar"
                      />
                    </div>
                  </div>
                </div>
              )}

              {/* --- TAB 2: GRAPH (RESIZE OBSERVER FIXED) --- */}
              {activeTab === 'profile' && !isSystemView && (
                <div className="h-full flex flex-col p-6 animate-in fade-in duration-500">
                  <div className="flex-none mb-4 flex justify-between items-end px-2">
                    <div>
                      <h3 className="text-lg font-bold text-slate-100 flex items-center gap-2">
                        {isHRRO ? (
                          <Clock className="w-5 h-5 text-blue-400" />
                        ) : (
                          <Waves className="w-5 h-5 text-blue-400" />
                        )}
                        {isHRRO
                          ? 'HRRO Dynamic Cycle'
                          : 'Pressure & Flux Profile'}
                      </h3>
                      <p className="text-xs text-slate-500 mt-1">
                        {isHRRO
                          ? 'Time-dependent variation of Flux, Pressure, and Recovery.'
                          : 'Axial profile along the pressure vessel.'}
                      </p>
                    </div>
                    {/* Legend */}
                    <div className="flex gap-4 text-xs font-bold bg-slate-900/50 px-3 py-1.5 rounded-lg border border-slate-800">
                      <div className="flex items-center gap-1.5 text-blue-400">
                        <div className="w-2 h-2 rounded-full bg-blue-500 shadow-[0_0_8px_rgba(59,130,246,0.5)]" />{' '}
                        Flux
                      </div>
                      <div className="flex items-center gap-1.5 text-orange-400">
                        <div className="w-2 h-2 rounded-full bg-orange-500 shadow-[0_0_8px_rgba(251,146,60,0.5)]" />{' '}
                        Pressure
                      </div>
                      {isHRRO && (
                        <div className="flex items-center gap-1.5 text-emerald-400">
                          <div className="w-2 h-2 rounded-full bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.5)]" />{' '}
                          Recovery
                        </div>
                      )}
                    </div>
                  </div>

                  {/* 🔥 Graph Container with Ref */}
                  <div
                    ref={chartContainerRef}
                    className="flex-1 bg-slate-900/30 border border-slate-700/50 rounded-xl p-4 min-h-[450px] relative w-full overflow-hidden"
                  >
                    {chartData.length > 0 && chartSize.width > 0 ? (
                      <ComposedChart
                        width={chartSize.width - 32}
                        height={chartSize.height - 32}
                        data={chartData}
                        margin={{ top: 10, right: 30, bottom: 10, left: 10 }}
                      >
                        <CartesianGrid
                          strokeDasharray="3 3"
                          stroke="#1e293b"
                          vertical={false}
                        />
                        <XAxis
                          dataKey={isHRRO ? 'time_min' : 'el'}
                          stroke="#64748b"
                          tick={{ fontSize: 11, fill: '#64748b' }}
                          tickLine={false}
                          axisLine={false}
                          label={{
                            value: isHRRO ? 'Time (min)' : 'Element',
                            position: 'bottom',
                            fill: '#475569',
                            fontSize: 11,
                            dy: 10,
                          }}
                        />

                        <YAxis
                          yAxisId="left"
                          stroke="#3b82f6"
                          tick={{ fontSize: 11, fill: '#3b82f6' }}
                          tickLine={false}
                          axisLine={false}
                          domain={['auto', 'auto']}
                        />
                        <YAxis
                          yAxisId="right"
                          orientation="right"
                          stroke="#fb923c"
                          tick={{ fontSize: 11, fill: '#fb923c' }}
                          tickLine={false}
                          axisLine={false}
                          domain={['auto', 'auto']}
                        />

                        <Tooltip
                          contentStyle={{
                            backgroundColor: '#0f172a',
                            borderColor: '#334155',
                            borderRadius: '8px',
                            fontSize: '12px',
                          }}
                          itemStyle={{ padding: 0 }}
                          formatter={(val: number) => val.toFixed(2)}
                          labelFormatter={(label) =>
                            isHRRO ? `Time: ${label} min` : `Element: ${label}`
                          }
                        />

                        {isHRRO && (
                          <ReferenceLine
                            y={60}
                            yAxisId="right"
                            stroke="#10b981"
                            strokeDasharray="3 3"
                          />
                        )}

                        <Area
                          yAxisId="left"
                          type="monotone"
                          dataKey="flux_lmh"
                          fill="url(#colorFlux)"
                          stroke="#3b82f6"
                          strokeWidth={2}
                          fillOpacity={0.15}
                          activeDot={{ r: 6, strokeWidth: 0 }}
                        />
                        <Line
                          yAxisId="right"
                          type="monotone"
                          dataKey="pressure_bar"
                          stroke="#fb923c"
                          strokeWidth={2}
                          dot={false}
                          activeDot={{ r: 6, strokeWidth: 0 }}
                        />
                        {isHRRO && (
                          <Line
                            yAxisId="right"
                            type="monotone"
                            dataKey="recovery_pct"
                            stroke="#10b981"
                            strokeWidth={2}
                            strokeDasharray="4 4"
                            dot={false}
                          />
                        )}

                        <defs>
                          <linearGradient
                            id="colorFlux"
                            x1="0"
                            y1="0"
                            x2="0"
                            y2="1"
                          >
                            <stop
                              offset="5%"
                              stopColor="#3b82f6"
                              stopOpacity={0.3}
                            />
                            <stop
                              offset="95%"
                              stopColor="#3b82f6"
                              stopOpacity={0}
                            />
                          </linearGradient>
                        </defs>
                      </ComposedChart>
                    ) : (
                      <div className="absolute inset-0 flex flex-col items-center justify-center text-slate-500">
                        {chartSize.width === 0 ? (
                          <div className="flex flex-col items-center">
                            <Loader2 className="w-8 h-8 animate-spin text-blue-500 mb-2" />
                            <span className="text-xs">
                              Initializing Chart...
                            </span>
                          </div>
                        ) : (
                          <div className="flex flex-col items-center">
                            <AlertCircle className="w-10 h-10 mb-2 opacity-30" />
                            <p className="text-sm">
                              No simulation data available.
                            </p>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* --- TAB 3: CHEMISTRY (Fully Implemented) --- */}
              {activeTab === 'chemistry' && (
                <div className="p-8 max-w-[1200px] mx-auto animate-in fade-in duration-300">
                  <div className="mb-6">
                    <h3 className="text-xl font-bold text-slate-100 flex items-center gap-2">
                      <FlaskConical className="w-6 h-6 text-purple-400" />{' '}
                      Chemistry Audit
                    </h3>
                    <p className="text-xs text-slate-500 mt-1">
                      Scale saturation indices based on feed water composition
                      and recovery rate.
                    </p>
                  </div>

                  {chemistry.feed ? (
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                      {/* Feed Analysis */}
                      <ChemCard
                        title="Feed Water"
                        color="blue"
                        data={chemistry.feed}
                      />
                      {/* Brine Analysis */}
                      {chemistry.final_brine ? (
                        <ChemCard
                          title="Concentrate (Brine)"
                          color="orange"
                          data={chemistry.final_brine}
                        />
                      ) : (
                        <div className="bg-slate-900/20 border border-slate-800 border-dashed rounded-xl flex items-center justify-center h-full text-slate-500">
                          No Brine Data
                        </div>
                      )}
                    </div>
                  ) : (
                    <div className="flex flex-col items-center justify-center min-h-[300px] text-slate-500">
                      <AlertTriangle className="w-10 h-10 mb-3 text-yellow-500/50" />
                      <p>Chemistry module is disabled or failed to converge.</p>
                    </div>
                  )}
                </div>
              )}

              {/* --- TAB 4: ENERGY --- */}
              {activeTab === 'power' && (
                <div className="flex flex-col items-center justify-center min-h-[500px] text-slate-500 space-y-4 animate-in fade-in">
                  <div className="p-6 bg-slate-900 rounded-full ring-1 ring-slate-700 shadow-lg">
                    <Zap className="w-12 h-12 text-yellow-500" />
                  </div>
                  <div className="text-center">
                    <h3 className="text-lg font-bold text-slate-300">
                      Energy & Cost
                    </h3>
                    <div className="text-6xl font-mono font-bold text-yellow-500 mt-4 mb-2 tracking-tighter drop-shadow-lg">
                      {fmt(displayEnergy)}{' '}
                      <span className="text-xl text-slate-500 font-sans font-normal">
                        kWh/m³
                      </span>
                    </div>
                    <p className="text-sm max-w-md mx-auto opacity-70">
                      Calculated based on pump efficiency (80%) and operating
                      pressure.
                    </p>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// --- SUB COMPONENTS ---

// 1. Sidebar Button
function SidebarBtn({ active, onClick, icon: Icon, label, badge }: any) {
  return (
    <button
      onClick={onClick}
      className={`mx-3 mb-1 flex items-center gap-3 px-3 py-2.5 rounded-lg text-xs font-medium transition-all group ${active ? 'bg-blue-600 text-white shadow-md shadow-blue-900/30' : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'}`}
    >
      <Icon
        className={`w-4 h-4 transition-colors ${active ? 'text-white' : 'text-slate-500 group-hover:text-slate-300'}`}
      />
      <span className="flex-1 text-left">{label}</span>
      {badge && (
        <span
          className={`text-[9px] px-1.5 py-0.5 rounded font-bold tracking-wide ${active ? 'bg-blue-500 text-blue-100 border border-blue-400' : 'bg-slate-800 text-slate-500 border border-slate-700'}`}
        >
          {badge}
        </span>
      )}
      {active && <ChevronRight className="w-3 h-3 ml-auto opacity-80" />}
    </button>
  );
}

// 2. Tab Button
function TabBtn({ active, onClick, icon: Icon, label }: any) {
  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-2 px-5 py-3 text-xs font-bold transition-all border-b-[2px] outline-none ${active ? 'border-blue-500 text-blue-400 bg-slate-800/50' : 'border-transparent text-slate-500 hover:text-slate-300 hover:bg-slate-800/30'}`}
    >
      <Icon className="w-4 h-4" /> {label}
    </button>
  );
}

// 3. Table Row
function Row({ label, icon, color, flow, tds, press }: any) {
  return (
    <tr className="hover:bg-slate-800/30 transition-colors group">
      <td className={`${STYLES.TD_L} pl-5 ${color}`}>
        <div className="flex items-center gap-2">
          <div className="opacity-50 group-hover:opacity-100 transition-opacity">
            {icon}
          </div>{' '}
          {label}
        </div>
      </td>
      <td className={STYLES.TD}>{fmt(flow)}</td>
      <td className={STYLES.TD}>{fmt(tds)}</td>
      <td className={STYLES.TD}>{fmt(press)}</td>
    </tr>
  );
}

// 4. KPI Card
function BigKPI({ label, value, unit, icon: Icon, color, subValue }: any) {
  const map: any = {
    blue: 'text-blue-400 from-blue-500/10 to-blue-500/5 border-blue-500/20',
    emerald:
      'text-emerald-400 from-emerald-500/10 to-emerald-500/5 border-emerald-500/20',
    yellow:
      'text-yellow-400 from-yellow-500/10 to-yellow-500/5 border-yellow-500/20',
  };
  return (
    <div
      className={`p-5 rounded-xl border bg-gradient-to-br shadow-sm relative overflow-hidden group transition-all duration-300 ${map[color]}`}
    >
      <div className="absolute -top-6 -right-6 p-6 opacity-5 group-hover:opacity-10 group-hover:scale-110 transition-transform duration-500 bg-current rounded-full">
        <Icon className="w-20 h-20" />
      </div>
      <div className="flex items-center gap-2 mb-2 relative z-10">
        <Icon className="w-4 h-4 opacity-70" />
        <span className="text-xs font-bold uppercase tracking-wider opacity-80">
          {label}
        </span>
      </div>
      <div className="flex items-baseline gap-1 relative z-10">
        <span className="text-3xl font-mono font-bold tracking-tighter drop-shadow-sm">
          {fmt(value)}
        </span>
        <span className="text-xs font-bold opacity-60">{unit}</span>
      </div>
      {subValue && (
        <div className="mt-3 text-[10px] font-medium opacity-60 flex items-center gap-1.5 relative z-10">
          <div className="w-1.5 h-1.5 rounded-full bg-current animate-pulse" />{' '}
          {subValue}
        </div>
      )}
    </div>
  );
}

function MiniKPI({ label, value, unit }: any) {
  return (
    <div className="p-4 rounded-lg border border-slate-700 bg-slate-800/30 hover:bg-slate-800/50 transition-colors">
      <div className="text-[10px] text-slate-500 font-bold uppercase mb-1">
        {label}
      </div>
      <div className="text-lg font-mono font-bold text-slate-200">
        {value}{' '}
        <span className="text-[10px] text-slate-500 ml-0.5">{unit}</span>
      </div>
    </div>
  );
}

// 5. Chemistry Card (New)
function ChemCard({ title, color, data }: any) {
  const headerColor = color === 'blue' ? 'bg-blue-500' : 'bg-orange-500';
  return (
    <div className="bg-slate-900/50 border border-slate-700/50 rounded-xl overflow-hidden shadow-lg">
      <div className="bg-slate-800/80 px-6 py-4 border-b border-slate-700 flex items-center gap-2">
        <span className={`w-2 h-2 rounded-full ${headerColor}`}></span>
        <h4 className="font-bold text-slate-200">{title}</h4>
      </div>
      <div className="p-6 space-y-4">
        <ChemRow
          label="LSI (Langelier)"
          value={data.lsi}
          desc="CaCO3 Scale Potential"
          threshold={0}
          type="max"
        />
        <ChemRow
          label="RSI (Ryznar)"
          value={data.rsi}
          desc="Corrosion vs Scaling"
          threshold={6}
          type="min"
        />
        <ChemRow
          label="S&DSI (Stiff-Davis)"
          value={data.s_dsi}
          desc="High TDS Scaling"
          threshold={0}
          type="max"
        />
        <div className="border-t border-slate-800/50 pt-4 mt-4">
          <ChemRow
            label="CaSO4 Saturation"
            value={data.caso4_si}
            unit="%"
            desc="Gypsum Potential"
            threshold={100}
            type="max"
          />
          <ChemRow
            label="SiO2 Saturation"
            value={data.sio2_si}
            unit="%"
            desc="Silica Potential"
            threshold={100}
            type="max"
          />
        </div>
      </div>
    </div>
  );
}

function ChemRow({ label, value, unit = '', desc, threshold, type }: any) {
  if (value === undefined || value === null) return null;

  // Safety Logic: Green is good, Red is bad
  let isSafe = true;
  if (type === 'max' && value > threshold) isSafe = false; // LSI > 0 is bad
  if (type === 'min' && value < threshold) isSafe = false; // RSI < 6 is bad

  return (
    <div className="flex items-center justify-between group">
      <div>
        <div className="text-xs font-bold text-slate-400 group-hover:text-slate-200 transition-colors">
          {label}
        </div>
        <div className="text-[10px] text-slate-600">{desc}</div>
      </div>
      <div className="text-right flex items-center gap-2">
        <div
          className={`text-sm font-mono font-bold ${isSafe ? 'text-emerald-400' : 'text-red-400'}`}
        >
          {value.toFixed(2)}{' '}
          <span className="text-[10px] opacity-60">{unit}</span>
        </div>
        {isSafe ? (
          <CheckCircle2 className="w-3 h-3 text-emerald-500/50" />
        ) : (
          <AlertCircle className="w-3 h-3 text-red-500/50" />
        )}
      </div>
    </div>
  );
}
