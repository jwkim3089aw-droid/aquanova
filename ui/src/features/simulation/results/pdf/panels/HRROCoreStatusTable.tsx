// ui/src/features/simulation/results/pdf/panels/HRROCoreStatusTable.tsx
import React from 'react';
import { THEME } from '../theme';
import { Badge } from '../components';
import { pickAnyFromKeys, pickNumber, safeObj, summarizeValue } from '../utils';
import { UnitLabels } from '../types';

export function HRROCoreStatusTable({
  physics,
  u,
}: {
  physics: any;
  u: UnitLabels;
}) {
  const p = safeObj(physics);

  const targetFlux = pickNumber(p?.target_flux_lmh);
  const achievedFlux = pickNumber(p?.achieved_flux_lmh);
  const pIn = pickNumber(p?.p_in_bar);
  const pOut = pickNumber(p?.p_out_bar);
  const dp = pickNumber(p?.dp_bar);
  const ndp = pickNumber(p?.ndp_bar);
  const sec = pickNumber(p?.sec_kwhm3 ?? p?.sec_kwh_m3);
  const pumpEff = pickAnyFromKeys(p, ['pump_eff', 'pumpEff', 'eff']);
  const pLimit = pickNumber(p?.pressure_limit_bar);

  const fluxStatus = () => {
    if (targetFlux == null || achievedFlux == null || targetFlux === 0)
      return <Badge text="N/A" tone="slate" />;
    const ratio = achievedFlux / targetFlux;
    if (ratio >= 0.98 && ratio <= 1.05)
      return <Badge text="OK" tone="emerald" />;
    if (ratio >= 0.9 && ratio <= 1.15)
      return <Badge text="WARN" tone="amber" />;
    return <Badge text="OFF" tone="rose" />;
  };

  const pLimitStatus = () => {
    if (pLimit == null || pOut == null)
      return <Badge text="N/A" tone="slate" />;
    if (pOut <= pLimit) return <Badge text="OK" tone="emerald" />;
    if (pOut <= pLimit * 1.02) return <Badge text="WARN" tone="amber" />;
    return <Badge text="LIMIT" tone="rose" />;
  };

  const rows = [
    {
      label: 'Target Flux',
      value: targetFlux,
      unit: u.flux,
      status: <Badge text="REF" tone="blue" />,
    },
    {
      label: 'Achieved Flux',
      value: achievedFlux,
      unit: u.flux,
      status: fluxStatus(),
    },
    {
      label: 'Inlet Pressure',
      value: pIn,
      unit: u.pressure,
      status: <Badge text="INFO" tone="slate" />,
    },
    {
      label: 'Outlet Pressure',
      value: pOut,
      unit: u.pressure,
      status: pLimitStatus(),
    },
    {
      label: 'Pressure Limit',
      value: pLimit,
      unit: u.pressure,
      status: <Badge text="REF" tone="blue" />,
    },
    {
      label: 'ΔP',
      value: dp,
      unit: u.pressure,
      status: <Badge text="INFO" tone="slate" />,
    },
    {
      label: 'NDP',
      value: ndp,
      unit: u.pressure,
      status: <Badge text="INFO" tone="slate" />,
    },
    {
      label: 'SEC',
      value: sec,
      unit: 'kWh/m³',
      status: <Badge text="INFO" tone="slate" />,
    },
    {
      label: 'Pump Eff.',
      value: pumpEff,
      unit: '',
      status: <Badge text="INFO" tone="slate" />,
    },
  ].filter((r) => r.value !== undefined);

  return (
    <div className={THEME.TABLE_WRAP}>
      <table className={THEME.TABLE}>
        <thead>
          <tr>
            <th className={THEME.TH}>Item</th>
            <th className={THEME.TH}>Value</th>
            <th className={THEME.TH}>Unit</th>
            <th className={THEME.TH}>Status</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} className={THEME.TR}>
              <td className={THEME.TD_LABEL}>{r.label}</td>
              <td className={THEME.TD}>{summarizeValue(r.value)}</td>
              <td className={THEME.TD}>{r.unit}</td>
              <td className={THEME.TD}>{r.status}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
