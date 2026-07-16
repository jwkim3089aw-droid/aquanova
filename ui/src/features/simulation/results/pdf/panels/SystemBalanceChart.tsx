// ui/src/features/simulation/results/pdf/panels/SystemBalanceChart.tsx
import React from 'react';
import { fmt } from '../utils';
import { UnitLabels } from '../types';

export function SystemBalanceChart({
  stageData,
  u,
}: {
  stageData: any[];
  u: UnitLabels;
}) {
  if (!stageData || stageData.length === 0) return null;

  // PDF와 동일한 스케일링을 위해 각 지표의 최대값 계산 (안전장치로 기본 최소값 설정)
  const rawMaxFlux = Math.max(...stageData.map((s) => s.flux || 0), 200);
  const rawMaxNdp = Math.max(...stageData.map((s) => s.ndp || 0), 3);

  // 눈금을 깔끔하게 떨어지게 하기 위해 상단 여백 10% 추가
  const maxFlux = rawMaxFlux * 1.1;
  const maxNdp = rawMaxNdp * 1.1;

  // 4등분 눈금 생성을 위한 배열 (100%, 75%, 50%, 25%, 0%)
  const ticks = [1, 0.75, 0.5, 0.25, 0];

  return (
    <div
      className="w-full print:break-inside-avoid border-2 border-slate-500 bg-white pt-6 pb-8 px-12 flex flex-col"
      style={{ WebkitPrintColorAdjust: 'exact', printColorAdjust: 'exact' }} // PDF 배경색 강제 출력
    >
      {/* 범례 (Legend) */}
      <div className="flex justify-between w-full mb-3 text-[10px] font-bold text-slate-800">
        <div className="flex items-center gap-1">
          <div className="w-3 h-3 bg-slate-700 border border-slate-900"></div>
          <span>플럭스 (Flux, {u.flux || 'LMH'})</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-3 h-3 bg-slate-300 border border-slate-500"></div>
          <span>순구동압력 (NDP, {u.pressure || 'bar'})</span>
        </div>
      </div>

      {/* 차트 본체 */}
      <div className="relative h-48 w-full border-l-2 border-b-2 border-r-2 border-slate-800 flex items-end justify-around pb-0">
        {/* 가로 점선 그리드 (Grid lines) */}
        {ticks.slice(1, -1).map((tick, i) => (
          <div
            key={i}
            className="absolute w-full border-t border-dashed border-slate-300 z-0"
            style={{ top: `${(1 - tick) * 100}%` }}
          ></div>
        ))}

        {/* 왼쪽 Y축 라벨 (Flux) */}
        <div className="absolute -left-10 bottom-0 h-full flex flex-col justify-between items-end text-[9px] font-mono font-bold text-slate-700 tabular-nums">
          {ticks.map((tick, i) => (
            <span key={i} className="transform translate-y-1/2">
              {fmt(maxFlux * tick)}
            </span>
          ))}
        </div>

        {/* 오른쪽 Y축 라벨 (NDP) */}
        <div className="absolute -right-10 bottom-0 h-full flex flex-col justify-between items-start text-[9px] font-mono font-bold text-slate-700 tabular-nums">
          {ticks.map((tick, i) => (
            <span key={i} className="transform translate-y-1/2">
              {fmt(maxNdp * tick)}
            </span>
          ))}
        </div>

        {/* 막대 그래프 (Bars) */}
        {stageData.map((s, i) => {
          const fluxPct = ((s.flux || 0) / maxFlux) * 100;
          const ndpPct = ((s.ndp || 0) / maxNdp) * 100;

          return (
            <div
              key={i}
              className="relative z-10 flex flex-col items-center w-20 h-full justify-end group"
            >
              <div className="flex items-end gap-1 w-full h-full justify-center pb-0 border-b-0">
                {/* Flux Bar */}
                <div
                  className="w-5 bg-slate-700 border border-slate-900 transition-all"
                  style={{ height: `${fluxPct}%` }}
                ></div>
                {/* NDP Bar */}
                <div
                  className="w-5 bg-slate-300 border border-slate-500 transition-all"
                  style={{ height: `${ndpPct}%` }}
                ></div>
              </div>

              {/* X축 스테이지 라벨 */}
              <div className="absolute -bottom-6 text-[10px] font-bold text-slate-800 whitespace-nowrap">
                Stage {s.stage}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
