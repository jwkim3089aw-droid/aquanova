// ui/src/features/simulation/results/pdf/panels/BrineScalingPanel.tsx
import React from 'react';
import { THEME } from '../theme';
import { Badge } from '../components';

export function BrineScalingPanel({ chemistry }: { chemistry: any }) {
  const brine = chemistry?.final_brine;

  if (!brine) {
    return null; // 데이터가 없으면 렌더링하지 않음
  }

  const metrics = [
    {
      label: 'Langelier Saturation Index (LSI)',
      value: brine.lsi,
      unit: '',
      limit: '> 0 Warn',
    },
    {
      label: 'Stiff & Davis Index (SDSI)',
      value: brine.s_dsi,
      unit: '',
      limit: '> 0 Warn',
    },
    {
      label: 'CaSO4 Saturation',
      value: brine.caso4_sat_pct,
      unit: '%',
      limit: '100%',
    },
    {
      label: 'BaSO4 Saturation',
      value: brine.baso4_sat_pct,
      unit: '%',
      limit: '100%',
    },
    {
      label: 'Silica (SiO2) Saturation',
      value: brine.sio2_sat_pct,
      unit: '%',
      limit: '100%',
    },
  ].filter((m) => m.value != null); // 값이 있는 것만 필터링

  if (metrics.length === 0) return null;

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <Badge text="CHEMISTRY" tone="blue" />
        <div className="text-[10px] text-slate-500">
          Brine Scaling & Solubility (Concentrate Stream)
        </div>
      </div>

      <div className={THEME.TABLE_WRAP}>
        <div className="overflow-x-auto">
          <table className={THEME.TABLE}>
            <thead>
              <tr>
                <th className={THEME.TH}>Parameter</th>
                <th className={THEME.TH}>Value</th>
                <th className={THEME.TH}>Limit</th>
                <th className={THEME.TH}>Status</th>
              </tr>
            </thead>
            <tbody>
              {metrics.map((m, i) => {
                const val =
                  typeof m.value === 'number' ? m.value.toFixed(2) : m.value;
                const isWarning =
                  (m.unit === '%' && (m.value as number) > 100) ||
                  (m.unit === '' && (m.value as number) > 0);

                return (
                  <tr key={i} className={THEME.TR}>
                    <td className={THEME.TD_LABEL}>{m.label}</td>
                    <td
                      className={`${THEME.TD} font-mono ${isWarning ? 'text-rose-600 font-bold' : ''}`}
                    >
                      {val} {m.unit}
                    </td>
                    <td className={THEME.TD}>{m.limit}</td>
                    <td className={THEME.TD}>
                      {isWarning ? (
                        <span className="text-rose-600 font-bold">WARN</span>
                      ) : (
                        <span className="text-emerald-600">OK</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
