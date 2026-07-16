// ui/src/components/common/DetailedResultModal/tabs/SummaryTab.tsx
import React, { memo } from 'react';
import {
  Table2,
  Layers,
  ArrowRight,
  Droplet,
  Zap,
  ArrowDownRight,
} from 'lucide-react';
import { fmt, pct } from '../../../../features/simulation/model/types';
import { STYLES } from '../constants';
import { BigKPI, MiniKPI } from '../SharedComponents';

// 💡 [최적화] React.memo 적용: Props가 변경되지 않으면 리렌더링 완벽 차단
export const SummaryTab = memo(function SummaryTab({
  isSystemView,
  currentData,
  feed,
  perm,
  conc,
  stages,
  displayRecovery,
  displayEnergy,
  displayFlux,
  displayNDP,
  setSelectedScope,
  isHRRO,
}: any) {
  return (
    <div className="p-8 max-w-[1400px] mx-auto grid grid-cols-12 gap-6 animate-in fade-in slide-in-from-bottom-2 duration-300">
      <div className="col-span-12 xl:col-span-8 space-y-6">
        <div className="rounded-xl border border-slate-700 bg-slate-900/50 overflow-hidden shadow-lg backdrop-blur-sm">
          <div className="bg-slate-800/80 px-5 py-3 border-b border-slate-700 flex justify-between items-center">
            <span className="text-sm font-bold text-slate-200 flex items-center gap-2">
              <Table2 className="w-4 h-4 text-blue-400" /> 질량 밸런스 흐름도
              (Mass Flow)
            </span>
            <span className="text-[10px] text-slate-400 bg-slate-950 px-2 py-1 rounded border border-slate-800 font-mono">
              {isSystemView
                ? 'PLANT BOUNDARY'
                : `STAGE ${currentData.stage} BOUNDARY`}
            </span>
          </div>

          <div className="p-6 flex items-center justify-between gap-4">
            {/* 1. 유입수 (Feed) */}
            <div className="flex-1 bg-blue-950/30 border border-blue-900/50 rounded-xl p-4 relative">
              <div className="text-[11px] font-bold text-blue-400 uppercase mb-2 flex items-center gap-1.5">
                <div className="w-2 h-2 rounded-full bg-blue-500 animate-pulse" />{' '}
                유입 (Feed)
              </div>
              <div className="text-2xl font-mono text-slate-200 font-bold">
                {fmt(feed?.flow_m3h)}{' '}
                <span className="text-xs text-slate-500 font-sans">m³/h</span>
              </div>
              <div className="text-sm font-mono text-slate-400 mt-1">
                TDS: {fmt(feed?.tds_mgL)} mg/L
              </div>
              <div className="text-xs font-mono text-slate-500 mt-1">
                P: {fmt(feed?.pressure_bar)} bar
              </div>
              <ArrowRight className="absolute -right-6 top-1/2 -translate-y-1/2 w-8 h-8 text-slate-600" />
            </div>

            {/* 2. 프로세스 블록 */}
            <div className="w-16 h-32 bg-slate-800 border border-slate-700 rounded-lg flex flex-col items-center justify-center relative shadow-inner">
              <Layers className="w-6 h-6 text-slate-500 mb-2 opacity-50" />
              <div className="text-[9px] text-slate-400 font-bold rotate-90 tracking-widest">
                PROCESS
              </div>
              <ArrowRight className="absolute -right-6 top-8 w-8 h-8 text-emerald-600/50" />
              <ArrowDownRight className="absolute -right-6 bottom-8 w-8 h-8 text-orange-600/50" />
            </div>

            {/* 3. 생산수 & 농축수 */}
            <div className="flex-1 flex flex-col gap-4">
              <div className="bg-emerald-950/30 border border-emerald-900/50 rounded-xl p-4">
                <div className="text-[11px] font-bold text-emerald-400 uppercase mb-2">
                  생산수 (Permeate)
                </div>
                <div className="text-2xl font-mono text-emerald-300 font-bold">
                  {fmt(perm?.flow_m3h)}{' '}
                  <span className="text-xs text-emerald-600/80 font-sans">
                    m³/h
                  </span>
                </div>
                <div className="text-sm font-mono text-emerald-500/80 mt-1">
                  TDS: {fmt(perm?.tds_mgL)} mg/L
                </div>
              </div>
              <div className="bg-orange-950/30 border border-orange-900/50 rounded-xl p-4">
                <div className="text-[11px] font-bold text-orange-400 uppercase mb-2">
                  농축수 (Concentrate)
                </div>
                <div className="text-2xl font-mono text-orange-300 font-bold">
                  {fmt(conc?.flow_m3h)}{' '}
                  <span className="text-xs text-orange-600/80 font-sans">
                    m³/h
                  </span>
                </div>
                <div className="text-sm font-mono text-orange-500/80 mt-1">
                  TDS: {fmt(conc?.tds_mgL)} mg/L
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* 스테이지 성능 요약 */}
        {isSystemView && stages.length > 0 && (
          <div className="rounded-xl border border-slate-700 bg-slate-900/50 overflow-hidden shadow-sm">
            <div className="bg-slate-800/80 px-5 py-3 border-b border-slate-700">
              <span className="text-sm font-bold text-slate-200 flex items-center gap-2">
                <Layers className="w-4 h-4 text-purple-400" /> 스테이지 상세
                부하 (Stage Workload)
              </span>
            </div>
            <table className="w-full text-sm">
              <thead>
                <tr>
                  <th className={STYLES.TH}>구간 (Stage)</th>
                  <th className={STYLES.TH + ' text-right w-1/4'}>
                    회수율 (Recovery)
                  </th>
                  <th className={STYLES.TH + ' text-right w-1/4'}>
                    평균 플럭스 (Avg Flux)
                  </th>
                  <th className={STYLES.TH + ' text-right w-1/4'}>
                    순구동압력 (NDP)
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/50 bg-slate-900/20">
                {stages.map((s: any, i: number) => {
                  const rec = s.recovery_pct || 0;
                  const flux = s.flux_lmh || s.jw_avg_lmh || 0;
                  const ndp = s.ndp_bar || 0;
                  return (
                    <tr
                      key={`${s.stage ?? i}-${s.module_type ?? 'X'}`}
                      className="hover:bg-blue-900/20 transition-colors cursor-pointer group"
                      onClick={() => setSelectedScope(i)}
                    >
                      <td className={`${STYLES.TD_L} pl-6`}>
                        <div className="flex items-center gap-2">
                          <span className="font-mono text-slate-400 font-bold">
                            #{s.stage}
                          </span>
                          <span className="text-[10px] bg-slate-800 px-1.5 py-0.5 rounded text-slate-300 border border-slate-700">
                            {s.module_type}
                          </span>
                        </div>
                      </td>
                      <td className={STYLES.TD}>
                        <div className="flex flex-col items-end gap-1">
                          <span
                            className={
                              rec > 0
                                ? 'text-emerald-400 font-mono font-bold'
                                : 'text-slate-500 font-mono'
                            }
                          >
                            {pct(rec)}
                          </span>
                          <div className="w-24 h-1 bg-slate-800 rounded-full overflow-hidden">
                            <div
                              style={{ width: `${Math.min(rec, 100)}%` }}
                              className="h-full bg-emerald-500"
                            />
                          </div>
                        </div>
                      </td>
                      <td className={STYLES.TD}>
                        <div className="flex flex-col items-end gap-1">
                          <span className="font-mono text-blue-300 font-bold">
                            {fmt(flux)}{' '}
                            <span className="text-[9px] text-slate-500 font-sans">
                              LMH
                            </span>
                          </span>
                          <div className="w-24 h-1 bg-slate-800 rounded-full overflow-hidden">
                            <div
                              style={{
                                width: `${Math.min((flux / 60) * 100, 100)}%`,
                              }}
                              className="h-full bg-blue-500"
                            />
                          </div>
                        </div>
                      </td>
                      <td className={STYLES.TD}>
                        <div className="flex flex-col items-end gap-1">
                          <span className="font-mono text-orange-300 font-bold">
                            {fmt(ndp)}{' '}
                            <span className="text-[9px] text-slate-500 font-sans">
                              bar
                            </span>
                          </span>
                          <div className="w-24 h-1 bg-slate-800 rounded-full overflow-hidden">
                            <div
                              style={{
                                width: `${Math.min((ndp / 15) * 100, 100)}%`,
                              }}
                              className="h-full bg-orange-500"
                            />
                          </div>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="col-span-12 xl:col-span-4 space-y-4">
        <BigKPI
          label={
            isSystemView
              ? '시스템 회수율 (System Recovery)'
              : '구간 회수율 (Stage Recovery)'
          }
          value={displayRecovery}
          unit="%"
          icon={Droplet}
          color="blue"
          subValue={isHRRO ? '배치 운전 (Batch)' : '연속 운전 (Continuous)'}
        />
        <BigKPI
          label="비에너지 (Specific Energy)"
          value={displayEnergy}
          unit="kWh/m³"
          icon={Zap}
          color="yellow"
          subValue="펌프 전력 (Pumping Power)"
        />
        <div className="grid grid-cols-2 gap-4">
          <MiniKPI
            label="평균 플럭스 (Avg Flux)"
            value={fmt(displayFlux)}
            unit="LMH"
          />
          <MiniKPI
            label="순구동압력 (Avg NDP)"
            value={fmt(displayNDP)}
            unit="bar"
          />
        </div>
      </div>
    </div>
  );
});
