// ui/src/features/simulation/results/pdf/panels/StageWaterQualityPanel.tsx
import React from 'react';
import { THEME } from '../theme';
import { fmt, pct, first, pickNumFromKeys, pickNumber } from '../utils';
import { UnitLabels } from '../types';

export function StageWaterQualityPanel({
  stages,
  u,
}: {
  stages: any[];
  u: UnitLabels;
}) {
  if (!stages.length) {
    return <div className="text-[10px] text-slate-500">No stage data.</div>;
  }

  const keys = {
    Qf: ['Qf', 'Qf_m3h', 'qf_m3h', 'feed_flow_m3h', 'feed_m3h', 'Qin_m3h'],
    Cf: ['Cf', 'Cf_mgL', 'cf_mgL', 'feed_tds_mgL', 'feed_tds', 'Cf_tds'],
    Qp: [
      'Qp',
      'Qp_m3h',
      'permeate_flow_m3h',
      'perm_flow_m3h',
      'product_flow_m3h',
    ],
    Cp: ['Cp', 'Cp_mgL', 'permeate_tds_mgL', 'perm_tds_mgL', 'product_tds_mgL'],
    Qc: ['Qc', 'Qc_m3h', 'concentrate_flow_m3h', 'brine_flow_m3h', 'Qb'],
    Cc: ['Cc', 'Cc_mgL', 'concentrate_tds_mgL', 'brine_tds_mgL', 'Cb'],
    dP: ['dp_bar', 'dP_bar', 'delta_p_bar', 'deltaP_bar'],
  };

  const rows = stages.map((s: any, idx: number) => {
    const stage = s?.stage ?? idx + 1;
    const type = s?.module_type ?? 'RO';
    const Qf = pickNumFromKeys(s, keys.Qf);
    const Cf = pickNumFromKeys(s, keys.Cf);
    const Qp = first(pickNumber(s?.Qp), pickNumFromKeys(s, keys.Qp));
    const Cp = first(pickNumber(s?.Cp), pickNumFromKeys(s, keys.Cp));
    const Qc = pickNumFromKeys(s, keys.Qc);
    const Cc = pickNumFromKeys(s, keys.Cc);
    const dP = first(pickNumber(s?.dp_bar), pickNumFromKeys(s, keys.dP));
    const rec = pickNumber(s?.recovery_pct);
    return { stage, type, Qf, Cf, Qp, Cp, Qc, Cc, dP, rec };
  });

  const has = {
    Qf: rows.some((r) => r.Qf != null),
    Cf: rows.some((r) => r.Cf != null),
    Qc: rows.some((r) => r.Qc != null),
    Cc: rows.some((r) => r.Cc != null),
    dP: rows.some((r) => r.dP != null),
  };

  return (
    <div className={THEME.TABLE_WRAP}>
      <div className="overflow-x-auto">
        <table className={THEME.TABLE}>
          <thead>
            <tr>
              <th className={THEME.TH}>Stage</th>
              <th className={THEME.TH}>Type</th>

              {has.Qf ? <th className={THEME.TH}>{`Qf (${u.flow})`}</th> : null}
              {has.Cf ? <th className={THEME.TH}>Cf (mg/L)</th> : null}

              <th className={THEME.TH}>{`Qp (${u.flow})`}</th>
              <th className={THEME.TH}>Cp (mg/L)</th>

              {has.Qc ? <th className={THEME.TH}>{`Qc (${u.flow})`}</th> : null}
              {has.Cc ? <th className={THEME.TH}>Cc (mg/L)</th> : null}

              {has.dP ? (
                <th className={THEME.TH}>{`ΔP (${u.pressure})`}</th>
              ) : null}
              <th className={THEME.TH}>Recovery (%)</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i} className={THEME.TR}>
                <td className={THEME.TD_LABEL}>{`Stage ${r.stage}`}</td>
                <td className={THEME.TD}>{String(r.type)}</td>

                {has.Qf ? <td className={THEME.TD}>{fmt(r.Qf)}</td> : null}
                {has.Cf ? <td className={THEME.TD}>{fmt(r.Cf)}</td> : null}

                <td className={THEME.TD}>{fmt(r.Qp)}</td>
                <td className={THEME.TD}>{fmt(r.Cp)}</td>

                {has.Qc ? <td className={THEME.TD}>{fmt(r.Qc)}</td> : null}
                {has.Cc ? <td className={THEME.TD}>{fmt(r.Cc)}</td> : null}

                {has.dP ? <td className={THEME.TD}>{fmt(r.dP)}</td> : null}
                <td className={THEME.TD}>{r.rec == null ? '-' : pct(r.rec)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="px-3 py-2 text-[10px] text-slate-500 bg-white border-t border-slate-200">
        * Qf/Cf/Qc/Cc/ΔP는 결과 payload에 존재하는 경우에만 자동 표시됩니다(키
        변형은 후보 목록으로 흡수).
      </div>
    </div>
  );
}
