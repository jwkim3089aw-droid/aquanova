// ui/src/features/simulation/results/pdf/panels/HistoryStatsTable.tsx
import React from 'react';
import { fmt, pct, pickNumber, safeArr } from '../utils';
import { UnitLabels } from '../types';

function summarizeHistory(history: any[]) {
  const h = safeArr(history);
  const xs = h
    .map((d) => ({
      p: pickNumber(d?.pressure_bar),
      tds: pickNumber(d?.tds_mgL),
      f: pickNumber(d?.flux_lmh),
      r: pickNumber(d?.recovery_pct),
    }))
    .filter((x) => x.p != null || x.tds != null || x.f != null || x.r != null);

  const stat = (arr: Array<number | null>) => {
    const v = arr.filter((x): x is number => x != null && Number.isFinite(x));
    if (!v.length) return null;
    const min = Math.min(...v);
    const max = Math.max(...v);
    const avg = v.reduce((a, b) => a + b, 0) / v.length;
    return { min, avg, max };
  };

  const last = xs.length ? xs[xs.length - 1] : null;

  return {
    p: stat(xs.map((x) => x.p)),
    tds: stat(xs.map((x) => x.tds)),
    f: stat(xs.map((x) => x.f)),
    r: stat(xs.map((x) => x.r)),
    end: last,
  };
}

export function HistoryStatsTable({
  history,
  u,
}: {
  history: any[];
  u: UnitLabels;
}) {
  const s = summarizeHistory(history);
  if (!s || (!s.p && !s.tds && !s.f && !s.r)) return null;

  // 🟦 원하시던 촘촘한 WAVE 스타일 가로형 테이블 테마 클래스
  const thHeaderClass =
    'py-1.5 px-3 text-[10px] font-bold text-slate-800 border border-slate-400 bg-slate-200 text-center tracking-wider';
  const thLabelClass =
    'py-1.5 px-3 text-[11px] font-bold text-slate-800 border border-slate-400 bg-slate-100 text-center';
  const tdClass =
    'py-1.5 px-3 text-[11px] font-mono font-bold text-slate-900 border border-slate-300 bg-white tabular-nums text-center';
  const tdAvgClass =
    'py-1.5 px-3 text-[11px] font-mono font-bold text-blue-900 border border-slate-300 bg-blue-50/40 tabular-nums text-center';
  const tdEndClass =
    'py-1.5 px-3 text-[11px] font-mono font-bold text-indigo-900 border border-slate-300 bg-indigo-50/40 tabular-nums text-center'; // 최종값 강조
  const tdUnitClass =
    'py-1.5 px-3 text-[10px] font-bold text-slate-600 border border-slate-300 bg-slate-50 text-center';

  // 행(Row) 렌더링 헬퍼
  const renderRow = (
    label: string,
    st: any,
    endVal: any,
    unit: string,
    isPct: boolean = false,
  ) => {
    const format = (v: any) => (isPct ? pct(v) : fmt(v));
    return (
      <tr>
        <th className={thLabelClass}>{label}</th>
        <td className={tdClass}>{st ? format(st.min) : '-'}</td>
        <td className={tdAvgClass}>{st ? format(st.avg) : '-'}</td>
        <td className={tdClass}>{st ? format(st.max) : '-'}</td>
        <td className={tdEndClass}>{endVal != null ? format(endVal) : '-'}</td>
        <td className={tdUnitClass}>{unit}</td>
      </tr>
    );
  };

  return (
    <div className="w-full print:break-inside-avoid mb-6">
      <div className="text-[12px] font-bold text-slate-800 mb-2 pl-2 border-l-2 border-slate-800 uppercase tracking-wider">
        운전 이력 통계 요약 (Operation History Stats)
      </div>

      <table className="w-full border-collapse border-2 border-slate-500">
        <thead>
          <tr>
            <th className={thHeaderClass}>운전 항목 (Metric)</th>
            <th className={thHeaderClass}>최소 (Min)</th>
            <th className={thHeaderClass}>평균 (Avg)</th>
            <th className={thHeaderClass}>최대 (Max)</th>
            <th className={thHeaderClass}>최종 (End)</th>
            <th className={thHeaderClass}>단위 (Unit)</th>
          </tr>
        </thead>
        <tbody>
          {renderRow('운전 압력 (Pressure)', s.p, s.end?.p, u.pressure)}
          {renderRow('투과수 수질 (TDS)', s.tds, s.end?.tds, 'mg/L')}
          {renderRow('평균 플럭스 (Flux)', s.f, s.end?.f, u.flux)}
          {renderRow('시스템 회수율 (Recovery)', s.r, s.end?.r, '%', true)}
        </tbody>
      </table>

      <div className="text-[10px] text-slate-500 mt-1.5 text-right italic">
        * "최종(End)" 값은 시뮬레이션 종료 시점의 운전 상태를 나타냅니다.
      </div>
    </div>
  );
}
