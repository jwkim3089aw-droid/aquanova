// ui/src/features/simulation/results/pdf/components/tables/StageSummaryTable.tsx
import React from 'react';
import { THEME } from '../../theme';
import { fmt, pct } from '../../utils';
import { UnitLabels } from '../../types';

export function StageSummaryTable({
  stages,
  u,
}: {
  stages: any[];
  u: UnitLabels;
}) {
  return (
    <div className={THEME.TABLE_WRAP}>
      <div className="overflow-x-auto">
        <table className={THEME.TABLE}>
          <thead>
            <tr>
              <th className={THEME.TH}>Stage</th>
              <th className={THEME.TH}>Type</th>
              <th className={THEME.TH}>Recovery</th>
              <th className={THEME.TH}>{`Flux (${u.flux})`}</th>
              <th className={THEME.TH}>{`NDP (${u.pressure})`}</th>
              <th className={THEME.TH}>SEC (kWh/m³)</th>
              <th className={THEME.TH}>{`p_in (${u.pressure})`}</th>
              <th className={THEME.TH}>{`p_out (${u.pressure})`}</th>
              <th className={THEME.TH}>{`Qp (${u.flow})`}</th>
              <th className={THEME.TH}>Cp</th>
            </tr>
          </thead>
          <tbody>
            {stages.map((s: any, i: number) => {
              const flux = s?.flux_lmh ?? s?.jw_avg_lmh ?? null;
              const sec = s?.sec_kwhm3 ?? s?.sec_kwh_m3 ?? null;
              return (
                <tr key={i} className={THEME.TR}>
                  <td
                    className={THEME.TD_LABEL}
                  >{`Stage ${s?.stage ?? i + 1}`}</td>
                  <td className={THEME.TD}>{s?.module_type ?? '-'}</td>
                  <td className={THEME.TD}>{pct(s?.recovery_pct)}</td>
                  <td className={THEME.TD}>{fmt(flux)}</td>
                  <td className={THEME.TD}>{fmt(s?.ndp_bar)}</td>
                  <td className={THEME.TD}>{fmt(sec)}</td>
                  <td className={THEME.TD}>{fmt(s?.p_in_bar)}</td>
                  <td className={THEME.TD}>{fmt(s?.p_out_bar)}</td>
                  <td className={THEME.TD}>{fmt(s?.Qp)}</td>
                  <td className={THEME.TD}>{fmt(s?.Cp)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div className="px-3 py-2 text-[10px] text-slate-500 bg-white border-t border-slate-200">
        * 상세(Qf/Qc/Cf/Cc, element profile 등)는 아래 패널에서(존재 시) 추가로
        표시됩니다. 또한 Raw(접기)에서 전체 키를 확인할 수 있습니다.
      </div>
    </div>
  );
}
