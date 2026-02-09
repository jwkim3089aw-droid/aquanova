// ui/src/features/simulation/results/pdf/panels/DistributionSummaryPanel.tsx
import React from 'react';
import { THEME } from '../theme';
import { Badge } from '../components';
import { fmt, pickNumber } from '../utils';
import { UnitLabels } from '../types';

export function DistributionSummaryPanel({
  stages,
  u,
}: {
  stages: any[];
  u: UnitLabels;
}) {
  if (!stages.length) {
    return <div className="text-[10px] text-slate-500">No stage data.</div>;
  }

  const vals = stages.map((s) => ({
    flux: pickNumber(s?.flux_lmh ?? s?.jw_avg_lmh),
    ndp: pickNumber(s?.ndp_bar),
    dp: pickNumber(s?.dp_bar),
    sec: pickNumber(s?.sec_kwhm3 ?? s?.sec_kwh_m3),
  }));

  const stat = (arr: Array<number | null>) => {
    const v = arr.filter((x): x is number => x != null && Number.isFinite(x));
    if (!v.length) return null;
    const min = Math.min(...v);
    const max = Math.max(...v);
    const avg = v.reduce((a, b) => a + b, 0) / v.length;
    return { min, avg, max };
  };

  const sFlux = stat(vals.map((v) => v.flux));
  const sNdp = stat(vals.map((v) => v.ndp));
  const sDp = stat(vals.map((v) => v.dp));
  const sSec = stat(vals.map((v) => v.sec));

  const worstDpIdx =
    vals
      .map((v, i) => ({ i, dp: v.dp }))
      .filter((x) => x.dp != null)
      .sort((a, b) => (b.dp as number) - (a.dp as number))[0]?.i ?? null;

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 flex-wrap">
        <Badge text="MIN/AVG/MAX" tone="blue" />
        {worstDpIdx != null ? (
          <Badge
            text={`Worst ΔP: Stage ${stages[worstDpIdx]?.stage ?? worstDpIdx + 1}`}
            tone="amber"
          />
        ) : (
          <Badge text="Worst ΔP: N/A" tone="slate" />
        )}
      </div>

      <div className={THEME.TABLE_WRAP}>
        <table className={THEME.TABLE}>
          <thead>
            <tr>
              <th className={THEME.TH}>Metric</th>
              <th className={THEME.TH}>Min</th>
              <th className={THEME.TH}>Avg</th>
              <th className={THEME.TH}>Max</th>
              <th className={THEME.TH}>Unit</th>
            </tr>
          </thead>
          <tbody>
            <tr className={THEME.TR}>
              <td className={THEME.TD_LABEL}>Flux</td>
              <td className={THEME.TD}>{sFlux ? fmt(sFlux.min) : '-'}</td>
              <td className={THEME.TD}>{sFlux ? fmt(sFlux.avg) : '-'}</td>
              <td className={THEME.TD}>{sFlux ? fmt(sFlux.max) : '-'}</td>
              <td className={THEME.TD}>{u.flux}</td>
            </tr>
            <tr className={THEME.TR}>
              <td className={THEME.TD_LABEL}>NDP</td>
              <td className={THEME.TD}>{sNdp ? fmt(sNdp.min) : '-'}</td>
              <td className={THEME.TD}>{sNdp ? fmt(sNdp.avg) : '-'}</td>
              <td className={THEME.TD}>{sNdp ? fmt(sNdp.max) : '-'}</td>
              <td className={THEME.TD}>{u.pressure}</td>
            </tr>
            <tr className={THEME.TR}>
              <td className={THEME.TD_LABEL}>ΔP</td>
              <td className={THEME.TD}>{sDp ? fmt(sDp.min) : '-'}</td>
              <td className={THEME.TD}>{sDp ? fmt(sDp.avg) : '-'}</td>
              <td className={THEME.TD}>{sDp ? fmt(sDp.max) : '-'}</td>
              <td className={THEME.TD}>{u.pressure}</td>
            </tr>
            <tr className={THEME.TR}>
              <td className={THEME.TD_LABEL}>SEC</td>
              <td className={THEME.TD}>{sSec ? fmt(sSec.min) : '-'}</td>
              <td className={THEME.TD}>{sSec ? fmt(sSec.avg) : '-'}</td>
              <td className={THEME.TD}>{sSec ? fmt(sSec.max) : '-'}</td>
              <td className={THEME.TD}>kWh/m³</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div className="text-[10px] text-slate-500">
        * Wave Detailed 리포트의 “stage/element 분포 감”을 Stage 요약 값으로
        재구성한 패널입니다.
      </div>
    </div>
  );
}
