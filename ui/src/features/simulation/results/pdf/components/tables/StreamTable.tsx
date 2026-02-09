// ui/src/features/simulation/results/pdf/components/tables/StreamTable.tsx
import React from 'react';
import { THEME } from '../../theme';
import { fmt } from '../../utils';
import { UnitLabels } from '../../types';

export function StreamTable({
  feed,
  perm,
  brine,
  u,
}: {
  feed: any;
  perm: any;
  brine: any;
  u: UnitLabels;
}) {
  const row = (label: string, d: any, highlight?: boolean) => (
    <tr className={`${THEME.TR} ${highlight ? 'bg-slate-50' : ''}`}>
      <td className={THEME.TD_LABEL}>{label}</td>
      <td className={THEME.TD}>{fmt(d?.flow_m3h ?? d?.Q ?? d?.Q_m3h)}</td>
      <td className={THEME.TD}>{fmt(d?.tds_mgL ?? d?.tds ?? d?.TDS)}</td>
      <td className={THEME.TD}>{fmt(d?.pressure_bar ?? d?.p_bar ?? d?.p)}</td>
      <td className={THEME.TD}>{fmt(d?.ph ?? d?.pH)}</td>
    </tr>
  );

  return (
    <div className={THEME.TABLE_WRAP}>
      <table className={THEME.TABLE}>
        <thead>
          <tr>
            <th className={THEME.TH}>스트림</th>
            <th className={THEME.TH}>{`유량 (${u.flow})`}</th>
            <th className={THEME.TH}>TDS (mg/L)</th>
            <th className={THEME.TH}>{`압력 (${u.pressure})`}</th>
            <th className={THEME.TH}>pH</th>
          </tr>
        </thead>
        <tbody>
          {row('Feed', feed)}
          {row('Product', perm, true)}
          {row('Brine', brine)}
        </tbody>
      </table>
    </div>
  );
}
