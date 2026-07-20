// ui/src/features/simulation/results/Visualization.tsx
import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Activity,
  Droplets,
  Gauge,
  Zap,
  Waves,
  AlertTriangle,
  Maximize2,
  LayoutDashboard,
  ShieldCheck,
  Droplet,
  FileText,
  CircleDollarSign,
  Beaker,
} from 'lucide-react';

import { UnitMode, fmt, pct } from '../model/types';
import { DetailedResultModal } from '../../../components/common/DetailedResultModal';
import {
  cn,
  n,
  getUnitLabel,
  stageFlux,
  CARD_BASE,
  LABEL_BASE,
  HealthCheckItem,
  RODetailContent,
  UFDetailContent,
  HRROBatchChart,
} from './VisualizationWidgets';

import { PrecisionReportPanel } from './PrecisionReportPanel';

export function Visualization({
  result,
  unitMode,
}: {
  result: any;
  unitMode: UnitMode;
}) {
  const navigate = useNavigate();
  const [isModalOpen, setIsModalOpen] = useState(false);

  if (!result) {
    return (
      <div className="flex h-full flex-col items-center justify-center text-slate-500 space-y-4 bg-slate-950/30">
        <div className="p-5 rounded-full bg-slate-900 border border-slate-800 shadow-inner">
          <Activity className="w-10 h-10 opacity-30 text-blue-400" />
        </div>
        <div className="text-center">
          <p className="text-sm font-bold text-slate-400">
            시뮬레이션 대기 중 (Ready)
          </p>
          <p className="text-xs text-slate-500 mt-1.5">
            조건을 설정하고 상단의{' '}
            <strong className="text-blue-400">Run</strong> 버튼을 누르세요.
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
  const massBalance = kpi.mass_balance;
  const warnings = result.warnings ?? [];
  const scenarioId = result.scenario_id;

  const checkStatus = (val: number | undefined | null, limit: number) => {
    if (val == null) return 'inactive';
    if (val > limit) return 'error';
    if (val > limit * 0.8) return 'warning';
    return 'ok';
  };

  const mbStatus =
    massBalance?.is_balanced && Math.abs(massBalance.flow_error_pct) < 1.0
      ? 'ok'
      : 'error';

  return (
    <div className="h-full relative flex flex-col font-sans min-h-0 min-w-0 bg-[#0a0f18]">
      {/* 🚀 상단 액션 버튼 영역 (이미지 복사 삭제됨) */}
      <div className="flex-none p-4 pb-2 flex gap-2 overflow-x-auto custom-scrollbar">
        <button
          onClick={() => setIsModalOpen(true)}
          className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-white text-[11px] font-bold shadow-md transition-all border border-slate-700 whitespace-nowrap"
        >
          <LayoutDashboard className="w-3.5 h-3.5 text-blue-400" /> 상세 결과
        </button>

        <button
          onClick={() =>
            navigate('/reports', {
              state: {
                data: result,
                mode: 'SYSTEM',
                meta: {
                  scenario_id: scenarioId,
                  unitMode,
                  source: 'Visualization',
                },
              },
            })
          }
          className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2.5 rounded-lg bg-[#0F4C81] hover:bg-blue-800 text-white text-[11px] font-bold shadow-md transition-all border border-blue-700/50 whitespace-nowrap"
        >
          <FileText className="w-3.5 h-3.5 text-blue-200" /> 리포트 생성
        </button>
      </div>

      <div className="flex-1 min-h-0 overflow-y-auto scrollbar-thin scrollbar-track-transparent scrollbar-thumb-slate-700">
        <div className="p-4 space-y-5 bg-[#0a0f18]">
          {/* 🚨 경고 패널 */}
          {warnings.length > 0 && (
            <div className="bg-rose-950/40 border border-rose-500/40 rounded-xl p-3.5 shadow-lg">
              <div className="flex items-center gap-2 text-rose-400 font-bold text-[11.5px] tracking-wide mb-2.5">
                <AlertTriangle className="w-4 h-4" /> 설계 지침 위반 (
                {warnings.length})
              </div>
              <ul className="text-[11px] text-rose-200/90 space-y-1.5 pl-6 list-disc font-medium">
                {warnings.map((w: any, idx: number) => (
                  <li key={idx}>
                    <span className="opacity-60 mr-1.5">
                      [{w.stage || 'SYS'}]
                    </span>
                    {w.message}
                  </li>
                ))}
              </ul>
            </div>
          )}

          <PrecisionReportPanel
            report={result.precision_report ?? null}
          />

          {/* 📊 KPI 요약 */}
          <div className="space-y-2.5">
            <div className="grid grid-cols-2 gap-2.5">
              <div
                className={cn(CARD_BASE, 'border-blue-500/30 bg-blue-900/20')}
              >
                <div className={LABEL_BASE}>
                  <Droplets className="w-3.5 h-3.5 text-blue-400" /> 시스템
                  회수율 (Rec %)
                </div>
                <div className="text-2xl font-bold text-blue-300 tabular-nums">
                  {pct(n(kpi.recovery_pct))}
                </div>
                <div className="w-full bg-slate-900/50 h-1.5 mt-2 rounded-full overflow-hidden">
                  <div
                    style={{ width: `${Math.min(n(kpi.recovery_pct), 100)}%` }}
                    className="h-full bg-blue-500 shadow-[0_0_8px_#3b82f6]"
                  />
                </div>
              </div>
              <div
                className={cn(
                  CARD_BASE,
                  'border-emerald-500/30 bg-emerald-900/20',
                )}
              >
                <div className={LABEL_BASE}>
                  <Zap className="w-3.5 h-3.5 text-emerald-400" /> 비에너지
                  (SEC)
                </div>
                <div className="text-2xl font-bold text-emerald-300 tabular-nums">
                  {fmt(n(kpi.sec_kwhm3))}
                </div>
                <div className="text-[10px] text-emerald-500/80 font-bold tracking-wide mt-1">
                  kWh/m³
                </div>
              </div>
            </div>

            <div className="grid grid-cols-3 gap-2.5">
              <div
                className={cn(CARD_BASE, 'border-cyan-500/20 bg-cyan-900/10')}
              >
                <div className={LABEL_BASE}>
                  <Droplet className="w-3.5 h-3.5 text-cyan-400" /> 생산수 (TDS)
                </div>
                <div className="text-[17px] font-bold text-cyan-300 tabular-nums">
                  {fmt(n(kpi.prod_tds))}
                </div>
                <div className="text-[9.5px] text-cyan-600/80 font-bold mt-0.5">
                  mg/L
                </div>
              </div>
              <div className={CARD_BASE}>
                <div className={LABEL_BASE}>
                  <Waves className="w-3.5 h-3.5 text-slate-400" /> 플럭스 (Flux)
                </div>
                <div className="text-[17px] font-bold text-slate-200 tabular-nums">
                  {fmt(n(kpi.flux_lmh ?? kpi.jw_avg_lmh))}
                </div>
                <div className="text-[9.5px] text-slate-500 font-bold mt-0.5">
                  {unitFlux}
                </div>
              </div>
              <div className={CARD_BASE}>
                <div className={LABEL_BASE}>
                  <Gauge className="w-3.5 h-3.5 text-slate-400" /> 구동압력
                  (NDP)
                </div>
                <div className="text-[17px] font-bold text-slate-200 tabular-nums">
                  {fmt(n(kpi.ndp_bar))}
                </div>
                <div className="text-[9.5px] text-slate-500 font-bold mt-0.5">
                  {unitPress}
                </div>
              </div>
            </div>
          </div>

          {/* 💰 경제성 평가 */}
          {result.economics && (
            <div className="rounded-xl border border-amber-500/30 bg-amber-900/10 p-4 shadow-lg backdrop-blur-sm">
              <div className="flex items-center justify-between mb-3.5 border-b border-amber-800/50 pb-2.5">
                <div className="flex items-center gap-2 text-[11.5px] font-bold text-amber-400 uppercase tracking-wide">
                  <CircleDollarSign className="w-4 h-4" /> 경제성 평가 및 단가
                  분석 (OPEX)
                </div>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="col-span-1 md:border-r border-amber-800/30 md:pr-4 flex flex-col justify-center">
                  <div className={LABEL_BASE}>
                    총 생산 단가 (Total Unit Cost)
                  </div>
                  <div className="flex items-baseline gap-1.5">
                    <span className="text-3xl font-extrabold text-amber-300 tabular-nums tracking-tight">
                      ${fmt(result.economics.unit_cost, 4)}
                    </span>
                    <span className="text-[11px] text-amber-500/80 font-bold uppercase">
                      / m³
                    </span>
                  </div>
                </div>
                <div className="col-span-2 grid grid-cols-2 gap-2.5">
                  <div
                    className={cn(
                      CARD_BASE,
                      'bg-slate-900/40 border-slate-700/50',
                    )}
                  >
                    <div className={LABEL_BASE}>
                      <Zap className="w-3.5 h-3.5 text-emerald-400" /> 전력비
                      (Energy)
                    </div>
                    <div className="text-[15px] font-bold text-slate-200 tabular-nums">
                      ${fmt(result.economics.energy_cost_per_m3, 4)}
                    </div>
                  </div>
                  <div
                    className={cn(
                      CARD_BASE,
                      'bg-slate-900/40 border-slate-700/50',
                    )}
                  >
                    <div className={LABEL_BASE}>
                      <Droplet className="w-3.5 h-3.5 text-cyan-400" /> 약품비
                      (Chemicals)
                    </div>
                    <div className="text-[15px] font-bold text-slate-200 tabular-nums">
                      ${fmt(result.economics.chem_cost_per_m3, 4)}
                    </div>
                  </div>
                  {result.dosing && (
                    <div className="col-span-2 mt-1 px-3 py-2 bg-slate-900/60 rounded border border-slate-700/50 flex justify-between items-center">
                      <span className="text-[10px] font-bold text-slate-400 uppercase flex items-center gap-1.5">
                        <Beaker className="w-3.5 h-3.5 text-purple-400" /> 목표
                        pH 조절
                      </span>
                      <span className="text-[11px] font-mono text-cyan-300">
                        원수 pH {result.dosing.initial_ph} ➔ 투입 후 pH{' '}
                        {result.dosing.actual_ph}
                      </span>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* 🩺 시스템 건전성 */}
          <div className="rounded-xl border border-slate-700/60 bg-slate-900/40 p-4 shadow-lg backdrop-blur-sm">
            <div className="flex items-center justify-between mb-3.5 border-b border-slate-800/80 pb-2.5">
              <div className="flex items-center gap-2 text-[11.5px] font-bold text-slate-300 uppercase tracking-wide">
                <ShieldCheck className="w-4 h-4 text-indigo-400" /> 시스템
                건전성 및 스케일링
              </div>
            </div>
            <div className="grid grid-cols-2 gap-2.5">
              <HealthCheckItem
                label="질량 밸런스"
                status={mbStatus}
                value={mbStatus === 'ok' ? '정상 (< 1%)' : '불일치'}
              />
              <HealthCheckItem
                label="LSI (랑겔리아)"
                status={checkStatus(chemFinal?.lsi, 1.8)}
                value={
                  chemFinal?.lsi != null ? fmt(chemFinal.lsi, 2) : undefined
                }
              />
              <HealthCheckItem
                label="CaSO4 포화도"
                status={checkStatus(chemFinal?.caso4_sat_pct, 100)}
                value={
                  chemFinal?.caso4_sat_pct != null
                    ? fmt(chemFinal.caso4_sat_pct, 1)
                    : undefined
                }
                unit="%"
              />
              <HealthCheckItem
                label="SiO2 포화도"
                status={checkStatus(chemFinal?.sio2_sat_pct, 100)}
                value={
                  chemFinal?.sio2_sat_pct != null
                    ? fmt(chemFinal.sio2_sat_pct, 1)
                    : undefined
                }
                unit="%"
              />
            </div>
          </div>

          {/* 🌊 스테이지별 성능 요약 (반복문) */}
          <div className="space-y-4 pb-6 min-w-0">
            <div className="flex items-center gap-2 text-[11px] font-bold text-slate-400 uppercase tracking-wide border-b border-slate-800 pb-2.5 pt-2">
              <Maximize2 className="w-3.5 h-3.5" /> 스테이지별 성능 요약 (Stage
              Overview)
            </div>
            {metrics.map((m: any, idx: number) => {
              const typeKey = String(m.module_type || 'RO').toUpperCase();
              const vioCount =
                typeKey === 'HRRO'
                  ? (m?.chemistry?.violations?.length ?? 0)
                  : 0;
              return (
                <div
                  key={`${m.stage ?? idx}-${typeKey}`}
                  className="rounded-xl border border-slate-700/50 bg-slate-800/20 overflow-hidden shadow-sm hover:border-slate-600/80 transition-colors min-w-0"
                >
                  <div className="px-3.5 py-2.5 flex justify-between items-center border-b border-slate-700/50 bg-slate-900/60">
                    <div className="flex items-center gap-2 min-w-0">
                      <div className="w-2.5 h-2.5 rounded-full bg-blue-500 shadow-[0_0_8px_#3b82f6]" />
                      <span className="text-[11.5px] font-bold text-slate-300 whitespace-nowrap">
                        스테이지 {m.stage}
                      </span>
                      <span className="text-[9.5px] px-1.5 py-0.5 rounded bg-slate-700 text-slate-200 font-bold border border-slate-600">
                        {typeKey}
                      </span>
                      {typeKey === 'HRRO' && (
                        <span
                          className={cn(
                            'text-[9px] px-1.5 py-0.5 rounded font-bold border',
                            vioCount > 0
                              ? 'bg-rose-950/50 text-rose-400 border-rose-500/30'
                              : 'bg-emerald-950/50 text-emerald-400 border-emerald-500/30',
                          )}
                        >
                          {vioCount > 0 ? `위반 ${vioCount}건` : '정상'}
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="p-3.5 min-w-0">
                    <div className="grid grid-cols-2 gap-y-3 gap-x-2">
                      <div>
                        <div className={LABEL_BASE}>유입 압력 (Feed P)</div>
                        <div className="font-mono font-bold text-slate-200 tabular-nums text-[15px]">
                          {fmt(m.p_in_bar)}{' '}
                          <span className="text-[9.5px] text-slate-500 ml-0.5">
                            {unitPress}
                          </span>
                        </div>
                      </div>
                      <div>
                        <div className={LABEL_BASE}>플럭스 (Flux)</div>
                        <div className="font-mono font-bold text-slate-200 tabular-nums text-[15px]">
                          {fmt(stageFlux(m))}{' '}
                          <span className="text-[9.5px] text-slate-500 ml-0.5">
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
                        history={m.time_history ?? null}
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
