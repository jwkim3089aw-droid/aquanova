// ui/src/features/simulation/results/pdf/panels/BrineScalingPanel.tsx
import React from 'react';
import { THEME } from '../theme';
import { Badge } from '../components';

export function BrineScalingPanel({ chemistry }: { chemistry: any }) {
  const brine = chemistry?.final_brine;

  if (!brine) {
    return null;
  }

  // 🛑 [WAVE PATCH] 상태 판별 로직 고도화 (WAVE 가이드라인 기준)
  const checkLimit = (
    val: number | undefined | null,
    warnLimit: number,
    errLimit: number,
  ) => {
    if (val == null) return { status: 'N/A', color: 'text-slate-500' };
    if (val >= errLimit)
      return { status: 'ERROR', color: 'text-rose-600 font-black' };
    if (val >= warnLimit)
      return { status: 'WARN', color: 'text-amber-500 font-bold' };
    return { status: 'OK', color: 'text-emerald-600 font-medium' };
  };

  const metrics = [
    {
      label: 'Langelier Saturation Index (LSI)',
      value: brine.lsi,
      unit: '',
      limitTxt: 'Max 1.8 (w/ AS)',
      ...checkLimit(brine.lsi, 0.5, 1.8), // 0.5 이상 주의, 1.8 이상 에러
    },
    {
      label: 'Stiff & Davis Index (SDSI)',
      value: brine.s_dsi,
      unit: '',
      limitTxt: 'Max 1.8 (w/ AS)',
      ...checkLimit(brine.s_dsi, 0.5, 1.8),
    },
    {
      label: 'CaSO4 Saturation',
      value: brine.caso4_sat_pct,
      unit: '%',
      limitTxt: 'Max 100%',
      ...checkLimit(brine.caso4_sat_pct, 80, 100), // 80% 이상 주의, 100% 초과 에러
    },
    {
      label: 'BaSO4 Saturation',
      value: brine.baso4_sat_pct,
      unit: '%',
      limitTxt: 'Max 100%',
      ...checkLimit(brine.baso4_sat_pct, 80, 100),
    },
    {
      label: 'Silica (SiO2) Saturation',
      value: brine.sio2_sat_pct,
      unit: '%',
      limitTxt: 'Max 100%',
      ...checkLimit(brine.sio2_sat_pct, 80, 100),
    },
  ].filter((m) => m.value != null);

  if (metrics.length === 0) return null;

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2 mb-1">
        <Badge text="SCALING" tone="violet" />
        <div className="text-[10px] text-slate-500 font-medium">
          Concentrate Stream Solubility Indicators (Antiscalant may be required)
        </div>
      </div>

      <div className={THEME.TABLE_WRAP}>
        <div className="overflow-x-auto">
          <table className={THEME.TABLE}>
            <thead>
              <tr>
                <th className={THEME.TH}>Parameter</th>
                <th className={THEME.TH}>Value</th>
                <th className={THEME.TH}>Limit (Guideline)</th>
                <th className={THEME.TH}>Status</th>
              </tr>
            </thead>
            <tbody>
              {metrics.map((m, i) => {
                const val =
                  typeof m.value === 'number' ? m.value.toFixed(2) : m.value;

                return (
                  <tr key={i} className={THEME.TR}>
                    <td className={`${THEME.TD_LABEL} font-semibold`}>
                      {m.label}
                    </td>
                    <td className={`${THEME.TD} font-mono ${m.color}`}>
                      {val}{' '}
                      <span className="text-[9px] opacity-70">{m.unit}</span>
                    </td>
                    <td className={`${THEME.TD} text-[10px] text-slate-500`}>
                      {m.limitTxt}
                    </td>
                    <td className={THEME.TD}>
                      <span className={m.color}>{m.status}</span>
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
