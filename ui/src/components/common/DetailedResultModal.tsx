// ui/src/features/flow-builder/ui/results/DetailedResultModal.tsx
import React, { useState, useEffect, useMemo } from 'react';
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
} from 'lucide-react';
import {
  ComposedChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Area,
  Legend,
} from 'recharts';
import { fmt, pct, UnitMode } from '../../features/simulation/model/types';

// --- UI Components (스타일 재사용) ---
const TH =
  'px-3 py-2 text-right font-semibold text-slate-500 uppercase text-[10px] bg-slate-900 border-b border-slate-700 sticky top-0';
const TD =
  'px-3 py-2 text-right font-mono text-slate-300 border-b border-slate-800/50 text-[11px]';
const TD_L =
  'px-3 py-2 text-left font-bold text-slate-400 border-b border-slate-800/50 text-[11px]';

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
  mode,
  unitMode,
}: DetailedResultModalProps) {
  // 1. 모든 Hook을 최상단에 선언
  const [selectedScope, setSelectedScope] = useState<'SYSTEM' | number>(
    'SYSTEM',
  );
  const [activeTab, setActiveTab] = useState<string>('summary');

  useEffect(() => {
    if (isOpen) {
      setSelectedScope('SYSTEM');
      setActiveTab('summary');
    }
  }, [isOpen]);

  // 2. 데이터 가공 로직 (Hook 내부나 일반 변수로 처리하되, return보다 위에 위치)
  const safeData = data || {};
  const kpi = safeData.kpi || {};
  const stages = safeData.stage_metrics || [];

  const currentData = useMemo(() => {
    return selectedScope === 'SYSTEM'
      ? { ...safeData, ...kpi }
      : stages[selectedScope] || {};
  }, [safeData, kpi, stages, selectedScope]);

  const isSystemView = selectedScope === 'SYSTEM';
  const isHRRO = currentData.module_type === 'HRRO';

  // 3. 차트 데이터 useMemo (return보다 위에 있어야 함)
  const chartData = useMemo(() => {
    if (!data) return []; // 데이터 없으면 빈 배열
    if (isHRRO) return currentData.time_history || [];
    return currentData.element_profile || [];
  }, [data, currentData, isHRRO]);

  // 4. Early Return은 모든 Hook 선언 이후에!
  if (!isOpen || !data) return null;

  // 5. 렌더링용 변수 할당 (Hook 아님)
  const displayRecovery = currentData.recovery_pct || 0;
  const displayEnergy = currentData.sec_kwhm3 || 0;
  const displayFlux = currentData.jw_avg_lmh || currentData.flux_lmh || 0;
  const displayNDP = currentData.ndp_bar || 0;

  const feed = isSystemView
    ? safeData.streams?.[0]
    : {
        flow_m3h: currentData.Qf,
        tds_mgL: currentData.Cf,
        pressure_bar: currentData.p_in_bar,
      };
  const perm = isSystemView
    ? safeData.streams?.[1]
    : { flow_m3h: currentData.Qp, tds_mgL: currentData.Cp, pressure_bar: 0 };
  const conc = isSystemView
    ? safeData.streams?.[2]
    : {
        flow_m3h: currentData.Qc,
        tds_mgL: currentData.Cc,
        pressure_bar: currentData.p_out_bar,
      };

  return (
    <div className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/80 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="w-[95vw] max-w-[1500px] h-[92vh] bg-[#0b1120] border border-slate-700 rounded-xl shadow-2xl flex flex-col overflow-hidden ring-1 ring-white/10 font-sans">
        {/* 헤더 */}
        <div className="flex-none h-14 border-b border-slate-700 bg-[#0f172a] flex items-center justify-between px-6 select-none">
          <div className="flex items-center gap-3">
            <div className="bg-blue-600/20 p-2 rounded text-blue-400">
              <Calculator className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-slate-100">
                Detailed Analysis Dashboard
              </h2>
              <div className="text-[10px] text-slate-500 font-mono">
                ID: {safeData.scenario_id?.slice(0, 8) || 'N/A'}
              </div>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-slate-800 rounded-lg text-slate-400 hover:text-white transition-colors"
          >
            <X className="w-6 h-6" />
          </button>
        </div>

        <div className="flex flex-1 overflow-hidden">
          {/* 사이드바 */}
          <div className="w-72 bg-[#0f172a] border-r border-slate-700 flex flex-col overflow-y-auto shrink-0">
            <div className="p-4 text-[10px] font-bold text-slate-500 uppercase tracking-wider">
              Scope Selection
            </div>
            <SidebarBtn
              active={selectedScope === 'SYSTEM'}
              onClick={() => setSelectedScope('SYSTEM')}
              icon={Globe}
              label="Overall System"
            />

            <div className="mt-6 mb-2 px-4 text-[10px] font-bold text-slate-600 uppercase">
              Stages
            </div>
            {stages.map((s: any, idx: number) => (
              <SidebarBtn
                key={idx}
                active={selectedScope === idx}
                onClick={() => setSelectedScope(idx)}
                icon={Layers}
                label={`Stage ${s.stage}`}
                badge={s.module_type}
              />
            ))}
          </div>

          {/* 메인 컨텐츠 */}
          <div className="flex-1 flex flex-col bg-[#0b1120] relative min-w-0">
            {/* 탭 버튼 */}
            <div className="flex-none border-b border-slate-700 bg-[#1e293b] flex px-2 overflow-x-auto">
              <TabBtn
                active={activeTab === 'summary'}
                onClick={() => setActiveTab('summary')}
                icon={LayoutDashboard}
                label="Summary & Flows"
              />
              <TabBtn
                active={activeTab === 'chemistry'}
                onClick={() => setActiveTab('chemistry')}
                icon={FlaskConical}
                label="Solubility & Ions"
              />
              {!isSystemView && (
                <TabBtn
                  active={activeTab === 'profile'}
                  onClick={() => setActiveTab('profile')}
                  icon={isHRRO ? Clock : Waves}
                  label={isHRRO ? 'Time Trends' : 'Element Profile'}
                />
              )}
              <TabBtn
                active={activeTab === 'power'}
                onClick={() => setActiveTab('power')}
                icon={Zap}
                label="Power & Cost"
              />
            </div>

            {/* 탭 내용 */}
            <div className="flex-1 overflow-y-auto p-0 relative scrollbar-thin scrollbar-thumb-slate-700">
              {/* === SUMMARY 탭 === */}
              {activeTab === 'summary' && (
                <div className="p-8 grid grid-cols-12 gap-6 animate-in fade-in duration-300">
                  <div className="col-span-12 mb-2 border-b border-slate-800 pb-4">
                    <h3 className="text-2xl font-bold text-slate-100 mb-1">
                      {isSystemView
                        ? 'Total Plant Performance'
                        : `Stage ${currentData.stage} Performance`}
                    </h3>
                  </div>

                  {/* 왼쪽: 테이블 영역 */}
                  <div className="col-span-12 xl:col-span-8 space-y-8">
                    <div className="border border-slate-700 rounded-lg overflow-hidden bg-[#1e293b]/30">
                      <div className="bg-slate-800/80 px-6 py-3 border-b border-slate-700 flex justify-between items-center">
                        <span className="text-sm font-bold text-slate-300 flex items-center gap-2">
                          <Table2 className="w-4 h-4" /> Mass Balance
                        </span>
                      </div>
                      <table className="w-full text-sm">
                        <thead>
                          <tr>
                            <th className={TH + ' text-left pl-6'}>Stream</th>
                            <th className={TH}>Flow (m³/h)</th>
                            <th className={TH}>TDS (mg/L)</th>
                            <th className={TH}>Press (bar)</th>
                          </tr>
                        </thead>
                        <tbody>
                          <Row
                            label="Feed"
                            color="text-blue-400"
                            flow={feed?.flow_m3h}
                            tds={feed?.tds_mgL}
                            press={feed?.pressure_bar}
                          />
                          <Row
                            label="Permeate"
                            color="text-emerald-400"
                            flow={perm?.flow_m3h}
                            tds={perm?.tds_mgL}
                            press={perm?.pressure_bar}
                          />
                          <Row
                            label="Concentrate"
                            color="text-orange-400"
                            flow={conc?.flow_m3h}
                            tds={conc?.tds_mgL}
                            press={conc?.pressure_bar}
                          />
                        </tbody>
                      </table>
                    </div>

                    {isSystemView && stages.length > 0 && (
                      <div className="border border-slate-700 rounded-lg overflow-hidden bg-[#1e293b]/30">
                        <div className="bg-slate-800/80 px-6 py-3 border-b border-slate-700">
                          <span className="text-sm font-bold text-slate-300 flex items-center gap-2">
                            <Layers className="w-4 h-4" /> Stage Breakdown
                          </span>
                        </div>
                        <table className="w-full text-sm">
                          <thead>
                            <tr>
                              <th className={TH + ' text-left pl-6'}>Stage</th>
                              <th className={TH}>Recov (%)</th>
                              <th className={TH}>Flux (lmh)</th>
                              <th className={TH}>NDP (bar)</th>
                            </tr>
                          </thead>
                          <tbody>
                            {stages.map((s: any, i: number) => (
                              <tr
                                key={i}
                                className="hover:bg-white/5 border-b border-slate-800/50"
                              >
                                <td className={`${TD_L} pl-6`}>
                                  Stage {s.stage}{' '}
                                  <span className="text-[9px] text-slate-500 ml-1">
                                    ({s.module_type})
                                  </span>
                                </td>
                                <td className={TD}>{pct(s.recovery_pct)}</td>
                                <td className={TD}>{fmt(s.jw_avg_lmh)}</td>
                                <td className={TD}>{fmt(s.ndp_bar)}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </div>

                  {/* 오른쪽: KPI 카드 */}
                  <div className="col-span-12 xl:col-span-4 space-y-4">
                    <BigKPI
                      label="Recovery"
                      value={displayRecovery}
                      unit="%"
                      color="blue"
                    />
                    <BigKPI
                      label="Specific Energy"
                      value={displayEnergy}
                      unit="kWh/m³"
                      color="yellow"
                    />
                    <BigKPI
                      label="Average Flux"
                      value={displayFlux}
                      unit="lmh"
                      color="emerald"
                    />
                    <BigKPI
                      label="Avg NDP"
                      value={displayNDP}
                      unit="bar"
                      color="purple"
                    />
                  </div>
                </div>
              )}

              {/* === PROFILE 탭 (그래프) === */}
              {activeTab === 'profile' && !isSystemView && (
                <div className="h-full flex flex-col p-8 animate-in fade-in duration-300">
                  <div className="flex-none mb-6">
                    <h3 className="text-xl font-bold text-slate-100">
                      {isHRRO ? 'HRRO Batch Cycle Profile' : 'Element Profile'}
                    </h3>
                  </div>
                  <div className="bg-slate-900/50 border border-slate-700 rounded-lg p-6 h-[60vh] min-h-[360px] min-w-0">
                    <ResponsiveContainer width="100%" height="100%">
                      <ComposedChart
                        data={chartData}
                        margin={{ top: 20, right: 30, bottom: 20, left: 20 }}
                      >
                        <CartesianGrid
                          strokeDasharray="3 3"
                          stroke="#334155"
                          vertical={false}
                        />
                        <XAxis
                          dataKey={isHRRO ? 'time_min' : 'el'}
                          stroke="#64748b"
                          label={{
                            value: isHRRO ? 'Time (min)' : 'Element',
                            position: 'bottom',
                          }}
                        />

                        <YAxis
                          yAxisId="left"
                          stroke="#3b82f6"
                          label={{
                            value: 'Flux (lmh)',
                            angle: -90,
                            position: 'insideLeft',
                          }}
                        />
                        <YAxis
                          yAxisId="right"
                          orientation="right"
                          stroke="#fb923c"
                          label={{
                            value: 'Pressure (bar)',
                            angle: 90,
                            position: 'insideRight',
                          }}
                        />

                        <Tooltip
                          contentStyle={{
                            backgroundColor: '#0f172a',
                            borderColor: '#334155',
                          }}
                        />
                        <Legend />

                        <Line
                          yAxisId="left"
                          type="monotone"
                          dataKey="flux_lmh"
                          stroke="#3b82f6"
                          strokeWidth={2}
                          name="Flux"
                          dot={false}
                        />
                        <Line
                          yAxisId="right"
                          type="monotone"
                          dataKey="pressure_bar"
                          stroke="#fb923c"
                          strokeWidth={2}
                          name="Pressure"
                          dot={false}
                        />
                        <Area
                          yAxisId="left"
                          type="monotone"
                          dataKey="recovery_pct"
                          fill="#10b981"
                          stroke="none"
                          fillOpacity={0.1}
                          name="Recovery %"
                        />
                      </ComposedChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              )}

              {/* === CHEMISTRY 탭 === */}
              {activeTab === 'chemistry' && (
                <div className="p-8 text-slate-400 text-center">
                  Chemistry module is active. (See PDF report for full details)
                </div>
              )}

              {/* === POWER 탭 === */}
              {activeTab === 'power' && (
                <div className="p-6 flex items-center justify-center h-full text-slate-500 flex-col gap-4">
                  <Zap className="w-16 h-16 opacity-20" />
                  <div className="text-center space-y-2">
                    <div className="text-3xl font-mono font-bold text-yellow-500">
                      {fmt(displayEnergy)}{' '}
                      <span className="text-sm text-slate-500">kWh/m³</span>
                    </div>
                    <p className="text-xs">Based on pumping energy.</p>
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

// --- 하위 컴포넌트 ---
function SidebarBtn({ active, onClick, icon: Icon, label, badge }: any) {
  return (
    <button
      onClick={onClick}
      className={`w-full flex items-center gap-3 px-4 py-3 text-xs font-bold transition-all border-l-2 text-left ${active ? 'border-blue-500 bg-blue-500/10 text-blue-400' : 'border-transparent text-slate-500 hover:text-slate-300 hover:bg-slate-800/50'}`}
    >
      <Icon className="w-5 h-5" />
      <span className="text-sm">{label}</span>
      {badge && (
        <span className="text-[10px] bg-slate-800 px-1.5 py-0.5 rounded text-slate-400 ml-2">
          {badge}
        </span>
      )}
      {active && <ChevronRight className="w-4 h-4 ml-auto opacity-50" />}
    </button>
  );
}

function TabBtn({ active, onClick, icon: Icon, label }: any) {
  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-2 px-6 py-4 text-xs font-bold transition-all border-b-2 outline-none uppercase tracking-wide ${active ? 'border-blue-500 text-blue-400 bg-slate-800' : 'border-transparent text-slate-500 hover:text-slate-300 hover:bg-slate-800/50'}`}
    >
      <Icon className="w-4 h-4" /> {label}
    </button>
  );
}

function Row({ label, color, flow, tds, press }: any) {
  return (
    <tr className="border-b border-slate-800/50 hover:bg-white/5">
      <td className={`${TD_L} pl-6 ${color}`}>{label}</td>
      <td className={TD}>{fmt(flow)}</td>
      <td className={TD}>{fmt(tds)}</td>
      <td className={TD}>{fmt(press)}</td>
    </tr>
  );
}

function BigKPI({ label, value, unit, color }: any) {
  const colorMap: any = {
    blue: 'text-blue-400 bg-blue-500/10 border-blue-500/20',
    emerald: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20',
    purple: 'text-purple-400 bg-purple-500/10 border-purple-500/20',
    yellow: 'text-yellow-400 bg-yellow-500/10 border-yellow-500/20',
  };
  return (
    <div
      className={`p-5 rounded-xl border flex items-center justify-between shadow-sm ${colorMap[color]}`}
    >
      <span className="text-sm font-bold uppercase opacity-80">{label}</span>
      <div className="text-right">
        <span className="text-2xl font-mono font-bold tracking-tight">
          {fmt(value)}
        </span>
        <span className="text-xs ml-1 opacity-70">{unit}</span>
      </div>
    </div>
  );
}
