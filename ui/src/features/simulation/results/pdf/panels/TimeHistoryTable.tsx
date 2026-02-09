// ui/src/features/simulation/results/pdf/panels/TimeHistoryTable.tsx
import React from 'react';
import { THEME } from '../theme';
import { fmt, safeArr } from '../utils';

export function TimeHistoryTable({
  history,
  maxRows = 12,
}: {
  history: any[];
  maxRows?: number;
}) {
  const h = safeArr(history);
  if (!h.length) {
    return (
      <div className="text-[10px] text-slate-500">
        No time history available.
      </div>
    );
  }

  const head = h.slice(0, Math.min(maxRows, h.length));
  const tail = h.length > maxRows * 2 ? h.slice(-maxRows) : h.slice(maxRows);

  const render = (rows: any[], title: string) => (
    <div className="mt-3">
      <div className="text-[10px] font-extrabold text-slate-500 uppercase tracking-widest mb-2">
        {title}
      </div>
      <div className={THEME.TABLE_WRAP}>
        <div className="overflow-x-auto">
          <table className={THEME.TABLE}>
            <thead>
              <tr>
                <th className={THEME.TH}>time_min</th>
                <th className={THEME.TH}>recovery_pct</th>
                <th className={THEME.TH}>pressure</th>
                <th className={THEME.TH}>tds</th>
                <th className={THEME.TH}>flux</th>
                <th className={THEME.TH}>ndp</th>
                <th className={THEME.TH}>perm_flow</th>
                <th className={THEME.TH}>perm_tds</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={i} className={THEME.TR}>
                  <td className={THEME.TD}>{fmt(r?.time_min)}</td>
                  <td className={THEME.TD}>{fmt(r?.recovery_pct)}</td>
                  <td className={THEME.TD}>{fmt(r?.pressure_bar)}</td>
                  <td className={THEME.TD}>{fmt(r?.tds_mgL)}</td>
                  <td className={THEME.TD}>{fmt(r?.flux_lmh)}</td>
                  <td className={THEME.TD}>{fmt(r?.ndp_bar)}</td>
                  <td className={THEME.TD}>{fmt(r?.permeate_flow_m3h)}</td>
                  <td className={THEME.TD}>{fmt(r?.permeate_tds_mgL)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );

  return (
    <div>
      {render(head, `Time History (처음 ${head.length}개)`)}
      {tail.length
        ? render(tail, `Time History (마지막 ${tail.length}개)`)
        : null}
    </div>
  );
}
