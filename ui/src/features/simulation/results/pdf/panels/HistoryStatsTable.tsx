// ui/src/features/simulation/results/pdf/panels/HistoryStatsTable.tsx
import React from 'react';
import { THEME } from '../theme';
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
  if (!s) return null;

  const row = (
    label: string,
    st: any,
    end: any,
    unit: string,
    fmtFn?: (v: any) => string,
  ) => (
    <tr className={THEME.TR}>
      <td className={THEME.TD_LABEL}>{label}</td>
      <td className={THEME.TD}>{st ? fmt(st.min) : '-'}</td>
      <td className={THEME.TD}>{st ? fmt(st.avg) : '-'}</td>
      <td className={THEME.TD}>{st ? fmt(st.max) : '-'}</td>
      <td className={THEME.TD}>
        {end != null ? (fmtFn ? fmtFn(end) : fmt(end)) : '-'}
      </td>
      <td className={THEME.TD}>{unit}</td>
    </tr>
  );

  return (
    <div className={THEME.TABLE_WRAP}>
      <table className={THEME.TABLE}>
        <thead>
          <tr>
            <th className={THEME.TH}>Metric</th>
            <th className={THEME.TH}>Min</th>
            <th className={THEME.TH}>Avg</th>
            <th className={THEME.TH}>Max</th>
            <th className={THEME.TH}>End</th>
            <th className={THEME.TH}>Unit</th>
          </tr>
        </thead>
        <tbody>
          {row('Pressure', s.p, s.end?.p, u.pressure)}
          {row('TDS', s.tds, s.end?.tds, 'mg/L')}
          {row('Flux', s.f, s.end?.f, u.flux)}
          {row('Recovery', s.r, s.end?.r, '%', (v) => pct(v))}
        </tbody>
      </table>
    </div>
  );
}
