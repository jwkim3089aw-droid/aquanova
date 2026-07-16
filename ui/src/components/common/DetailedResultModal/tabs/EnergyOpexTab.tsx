// ui/src/components/common/DetailedResultModal/tabs/EnergyOpexTab.tsx
import React, { useMemo, memo } from 'react';
import {
  Zap,
  CircleDollarSign,
  Droplet,
  Beaker,
  PieChart as PieChartIcon,
} from 'lucide-react';
import {
  PieChart,
  Pie,
  Cell,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
} from 'recharts';
import { fmt, pct } from '../../../../features/simulation/model/types';

// 💡 [최적화] React.memo 적용 및 내부 데이터 구조 고정
export const EnergyOpexTab = memo(function EnergyOpexTab({
  isSystemView,
  economics,
  displayEnergy,
  dosing,
}: any) {
  const energyCost = economics?.energy_cost_per_m3 ?? 0;
  const chemCost = economics?.chem_cost_per_m3 ?? 0;
  const totalCost = economics?.unit_cost ?? energyCost + chemCost;

  // 💡 [최적화] 매 렌더링마다 배열이 새로 할당되어 Recharts를 깨우는 것을 방지
  const costData = useMemo(() => {
    return [
      { name: '전력비 (Energy)', value: energyCost, color: '#34d399' },
      { name: '약품비 (Chemicals)', value: chemCost, color: '#22d3ee' },
    ].filter((d) => d.value > 0);
  }, [energyCost, chemCost]);

  return (
    <div className="p-8 max-w-[1200px] mx-auto animate-in fade-in duration-300">
      {isSystemView && economics ? (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          <div className="flex flex-col justify-center items-center p-10 bg-gradient-to-br from-slate-900 to-slate-950 rounded-3xl border border-slate-700 shadow-2xl relative overflow-hidden">
            <div className="absolute -top-16 -right-16 p-16 opacity-5 bg-yellow-500 rounded-full blur-2xl pointer-events-none" />
            <div className="absolute -bottom-10 -left-10 p-10 opacity-5 bg-blue-500 rounded-full blur-xl pointer-events-none" />

            <Zap className="w-14 h-14 text-yellow-400 mb-5 relative z-10 drop-shadow-[0_0_15px_rgba(250,204,21,0.4)]" />
            <h3 className="text-sm font-bold text-slate-400 uppercase tracking-widest relative z-10">
              총 비에너지 (Specific Energy)
            </h3>
            <div className="text-[5rem] font-mono font-extrabold text-transparent bg-clip-text bg-gradient-to-r from-yellow-300 to-yellow-500 mt-3 mb-2 tracking-tighter drop-shadow-sm relative z-10 leading-none">
              {fmt(displayEnergy)}{' '}
              <span className="text-2xl text-slate-500 font-sans font-normal tracking-normal">
                kWh/m³
              </span>
            </div>
            <div className="text-xs text-slate-500 mt-2 tracking-wide">
              시스템 전체 펌프 구동에 필요한 단위 부피당 전력량
            </div>
          </div>

          <div className="flex flex-col justify-between space-y-5">
            <div className="p-6 bg-gradient-to-br from-amber-950/40 to-amber-900/10 border border-amber-500/30 rounded-2xl shadow-lg relative overflow-hidden">
              <div className="absolute top-0 right-0 p-4 opacity-10 pointer-events-none">
                <CircleDollarSign className="w-24 h-24 text-amber-500" />
              </div>
              <div className="text-[11px] font-bold text-amber-500 uppercase tracking-wider mb-2 flex items-center gap-2">
                <CircleDollarSign className="w-4 h-4" /> 총 생산 단가 (Total
                OPEX)
              </div>
              <div className="flex items-baseline gap-2 relative z-10">
                <span className="text-5xl font-extrabold text-amber-400 tabular-nums tracking-tight">
                  ${fmt(totalCost, 4)}
                </span>
                <span className="text-sm text-amber-500/80 font-bold uppercase tracking-widest">
                  / m³
                </span>
              </div>
            </div>

            <div className="flex gap-4 items-center bg-slate-900/40 border border-slate-700/50 rounded-2xl p-5 shadow-inner flex-1">
              <div className="w-1/3 h-[120px] flex-shrink-0 relative">
                {costData.length > 0 ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={costData}
                        cx="50%"
                        cy="50%"
                        innerRadius={35}
                        outerRadius={55}
                        paddingAngle={5}
                        dataKey="value"
                        stroke="none"
                      >
                        {costData.map((entry, index) => (
                          <Cell key={`cell-${index}`} fill={entry.color} />
                        ))}
                      </Pie>
                      <RechartsTooltip
                        formatter={(value: number) => [
                          `$${value.toFixed(4)}`,
                          '단가',
                        ]}
                        contentStyle={{
                          backgroundColor: '#0f172a',
                          borderColor: '#334155',
                          fontSize: '11px',
                          borderRadius: '6px',
                        }}
                      />
                    </PieChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="w-full h-full flex items-center justify-center text-slate-600">
                    <PieChartIcon className="w-8 h-8 opacity-20" />
                  </div>
                )}
                <div className="absolute inset-0 flex items-center justify-center text-[10px] font-bold text-slate-400 pointer-events-none">
                  비율
                </div>
              </div>

              <div className="flex-1 flex flex-col gap-3">
                <div className="p-3 bg-slate-800/60 border border-slate-700/50 rounded-xl flex justify-between items-center group hover:bg-slate-800 transition-colors">
                  <div className="flex items-center gap-2">
                    <div className="w-8 h-8 rounded-lg bg-emerald-950/50 border border-emerald-500/30 flex items-center justify-center">
                      <Zap className="w-4 h-4 text-emerald-400" />
                    </div>
                    <div>
                      <div className="text-[10px] font-bold text-slate-400 uppercase">
                        전력비용 (Energy)
                      </div>
                      <div className="text-[10px] text-emerald-500/70">
                        {totalCost > 0
                          ? pct((energyCost / totalCost) * 100)
                          : '0%'}
                      </div>
                    </div>
                  </div>
                  <div className="text-xl font-bold text-slate-200 tabular-nums tracking-tight">
                    ${fmt(energyCost, 4)}
                  </div>
                </div>

                <div className="p-3 bg-slate-800/60 border border-slate-700/50 rounded-xl flex justify-between items-center group hover:bg-slate-800 transition-colors">
                  <div className="flex items-center gap-2">
                    <div className="w-8 h-8 rounded-lg bg-cyan-950/50 border border-cyan-500/30 flex items-center justify-center">
                      <Droplet className="w-4 h-4 text-cyan-400" />
                    </div>
                    <div>
                      <div className="text-[10px] font-bold text-slate-400 uppercase">
                        약품비용 (Chemicals)
                      </div>
                      <div className="text-[10px] text-cyan-500/70">
                        {totalCost > 0
                          ? pct((chemCost / totalCost) * 100)
                          : '0%'}
                      </div>
                    </div>
                  </div>
                  <div className="text-xl font-bold text-slate-200 tabular-nums tracking-tight">
                    ${fmt(chemCost, 4)}
                  </div>
                </div>
              </div>
            </div>

            {dosing && (
              <div className="p-4 bg-slate-800/30 border border-slate-700 border-dashed rounded-xl flex justify-between items-center shadow-sm">
                <div className="text-[11px] font-bold text-slate-400 flex items-center gap-2">
                  <Beaker className="w-4 h-4 text-purple-400" /> 목표 pH 조절
                  (Dosing)
                </div>
                <div className="text-sm font-mono text-cyan-300 font-bold bg-slate-950/80 px-4 py-1.5 rounded-lg border border-slate-700">
                  원수 <span className="text-slate-400">pH</span>{' '}
                  {dosing.initial_ph}{' '}
                  <span className="text-slate-600 mx-2">➔</span> 투입 후{' '}
                  <span className="text-slate-400">pH</span> {dosing.actual_ph}
                </div>
              </div>
            )}
          </div>
        </div>
      ) : (
        <div className="flex flex-col items-center justify-center min-h-[400px] text-slate-500 space-y-4">
          <div className="p-6 bg-slate-900 rounded-full ring-1 ring-slate-700 shadow-lg">
            <Zap className="w-12 h-12 text-yellow-500" />
          </div>
          <div className="text-center">
            <h3 className="text-lg font-bold text-slate-300">
              비에너지 (Energy & Power)
            </h3>
            <div className="text-6xl font-mono font-bold text-yellow-500 mt-4 mb-2 tracking-tighter drop-shadow-lg">
              {fmt(displayEnergy)}{' '}
              <span className="text-xl text-slate-500 font-sans font-normal">
                kWh/m³
              </span>
            </div>
            <p className="text-sm max-w-md mx-auto opacity-70">
              해당 스테이지의 펌프 효율 및 구동 압력을 기반으로 계산된
              비에너지(SEC)입니다.
            </p>
          </div>
        </div>
      )}
    </div>
  );
});
