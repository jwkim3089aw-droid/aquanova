// ui/src/features/simulation/results/pdf/panels/DistributionSummaryPanel.tsx
import React from 'react';
import { fmt, pickNumber } from '../utils';
import { UnitLabels } from '../types';

export function DistributionSummaryPanel({
  stages = [],
  u,
}: {
  stages?: any[];
  u: UnitLabels;
}) {
  if (!stages || !Array.isArray(stages) || stages.length === 0) {
    return (
      <div className="text-[10px] text-slate-500">No stage data available.</div>
    );
  }

  // 🟢 데이터 추출 (MF/UF/NF/RO 혼합 데이터 안전 대응)
  const vals = stages.map((s) => {
    const flux = pickNumber(s?.flux_lmh ?? s?.jw_avg_lmh);
    const ndp = pickNumber(s?.ndp_bar);
    const dp = pickNumber(s?.dp_bar ?? s?.chemistry?.model?.dp_total_bar);
    const sec = pickNumber(s?.sec_kwhm3 ?? s?.sec_kwh_m3);
    return { flux, ndp, dp, sec, stageIdx: s?.stage };
  });

  // 통계 계산 헬퍼
  const stat = (arr: Array<number | null>) => {
    const v = arr.filter((x): x is number => x != null && Number.isFinite(x));
    if (v.length === 0) return null;
    const min = Math.min(...v);
    const max = Math.max(...v);
    const avg = v.reduce((a, b) => a + b, 0) / v.length;
    return { min, avg, max };
  };

  const sFlux = stat(vals.map((v) => v.flux));
  const sNdp = stat(vals.map((v) => v.ndp));
  const sDp = stat(vals.map((v) => v.dp));
  const sSec = stat(vals.map((v) => v.sec));

  // Worst DP 스테이지 찾기
  const validDps = vals.filter((v) => v.dp != null);
  let worstStageLabel = 'N/A';
  if (validDps.length > 0) {
    const worst = validDps.reduce((prev, curr) =>
      (curr.dp as number) > (prev.dp as number) ? curr : prev,
    );
    worstStageLabel = `Stage ${worst.stageIdx ?? 'Unknown'}`;
  }

  // 🟦 촘촘한 WAVE 테마 CSS 클래스
  const thHeaderClass =
    'py-1.5 px-3 text-[10px] font-bold text-slate-800 border border-slate-400 bg-slate-200 text-center tracking-wider';
  const thLabelClass =
    'py-1.5 px-3 text-[11px] font-bold text-slate-800 border border-slate-400 bg-slate-100 text-center';
  const tdClass =
    'py-1.5 px-3 text-[11px] font-mono font-bold text-slate-900 border border-slate-300 bg-white tabular-nums text-center';
  const tdAvgClass =
    'py-1.5 px-3 text-[11px] font-mono font-bold text-blue-900 border border-slate-300 bg-blue-50/40 tabular-nums text-center'; // 평균값 강조
  const tdUnitClass =
    'py-1.5 px-3 text-[10px] font-bold text-slate-600 border border-slate-300 bg-slate-50 text-center';

  return (
    <div className="w-full print:break-inside-avoid mb-6">
      {/* 헤더 영역 */}
      <div className="flex items-center justify-between mb-2">
        <div className="text-[12px] font-bold text-slate-800 pl-2 border-l-2 border-slate-800 uppercase tracking-wider">
          전체 시스템 분포 요약 (Distribution Summary)
        </div>
        <div className="flex gap-2">
          <span className="text-[10px] font-bold bg-slate-200 text-slate-700 px-2 py-0.5 rounded border border-slate-300">
            MIN / AVG / MAX
          </span>
          <span
            className={`text-[10px] font-bold px-2 py-0.5 rounded border ${worstStageLabel !== 'N/A' ? 'bg-amber-100 text-amber-800 border-amber-300' : 'bg-slate-100 text-slate-600 border-slate-300'}`}
          >
            Worst ΔP: {worstStageLabel}
          </span>
        </div>
      </div>

      {/* 테이블 영역 */}
      <table className="w-full border-collapse border-2 border-slate-500">
        <thead>
          <tr>
            <th className={thHeaderClass}>측정 항목 (Metric)</th>
            <th className={thHeaderClass}>최소값 (Min)</th>
            <th className={thHeaderClass}>평균값 (Avg)</th>
            <th className={thHeaderClass}>최대값 (Max)</th>
            <th className={thHeaderClass}>단위 (Unit)</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <th className={thLabelClass}>운전 플럭스 (Flux)</th>
            <td className={tdClass}>{sFlux ? fmt(sFlux.min) : '-'}</td>
            <td className={tdAvgClass}>{sFlux ? fmt(sFlux.avg) : '-'}</td>
            <td className={tdClass}>{sFlux ? fmt(sFlux.max) : '-'}</td>
            <td className={tdUnitClass}>{u.flux || 'LMH'}</td>
          </tr>
          <tr>
            <th className={thLabelClass}>순추진압력 (NDP)</th>
            <td className={tdClass}>{sNdp ? fmt(sNdp.min) : '-'}</td>
            <td className={tdAvgClass}>{sNdp ? fmt(sNdp.avg) : '-'}</td>
            <td className={tdClass}>{sNdp ? fmt(sNdp.max) : '-'}</td>
            <td className={tdUnitClass}>{u.pressure || 'bar'}</td>
          </tr>
          <tr>
            <th className={thLabelClass}>모듈 차압 (ΔP)</th>
            <td className={tdClass}>{sDp ? fmt(sDp.min) : '-'}</td>
            <td className={tdAvgClass}>{sDp ? fmt(sDp.avg) : '-'}</td>
            <td className={tdClass}>{sDp ? fmt(sDp.max) : '-'}</td>
            <td className={tdUnitClass}>{u.pressure || 'bar'}</td>
          </tr>
          <tr>
            <th className={thLabelClass}>비에너지소비량 (SEC)</th>
            <td className={tdClass}>{sSec ? fmt(sSec.min) : '-'}</td>
            <td className={tdAvgClass}>{sSec ? fmt(sSec.avg) : '-'}</td>
            <td className={tdClass}>{sSec ? fmt(sSec.max) : '-'}</td>
            <td className={tdUnitClass}>kWh/m³</td>
          </tr>
        </tbody>
      </table>

      <div className="text-[10px] text-slate-500 mt-1.5 text-right">
        * 평균값(Avg)은 전체 시스템 운영의 기준 성능 지표로 활용됩니다.
      </div>
    </div>
  );
}
