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
    // 🛑 UF Specific Keys
    grossQ: ['gross_flow_m3h'],
    bwLoss: ['backwash_loss_m3h'],
    netRec: ['net_recovery_pct'],
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
    const grossQ = pickNumFromKeys(s, keys.grossQ);
    const bwLoss = pickNumFromKeys(s, keys.bwLoss);
    const netRec = pickNumFromKeys(s, keys.netRec);

    return {
      stage,
      type,
      Qf,
      Cf,
      Qp,
      Cp,
      Qc,
      Cc,
      dP,
      rec,
      grossQ,
      bwLoss,
      netRec,
    };
  });

  const has = {
    Qf: rows.some((r) => r.Qf != null),
    Cf: rows.some((r) => r.Cf != null),
    Qc: rows.some((r) => r.Qc != null),
    Cc: rows.some((r) => r.Cc != null),
    dP: rows.some((r) => r.dP != null),
    // 시뮬레이션 내에 UF가 단 하나라도 있는지 확인
    UF: rows.some((r) => r.grossQ != null || r.netRec != null),
  };

  return (
    <div className={THEME.TABLE_WRAP}>
      <div className="overflow-x-auto">
        <table className={THEME.TABLE}>
          <thead>
            <tr>
              <th className={THEME.TH}>Stage</th>
              <th className={THEME.TH}>Type</th>

              {has.Qf && <th className={THEME.TH}>{`Qf (${u.flow})`}</th>}
              {has.Cf && <th className={THEME.TH}>Cf (mg/L)</th>}

              {/* UF가 있을 때만 보이는 Gross Flow 헤더 */}
              {has.UF && <th className={THEME.TH}>{`Gross Q (${u.flow})`}</th>}

              <th className={THEME.TH}>
                {has.UF ? `Net Qp (${u.flow})` : `Qp (${u.flow})`}
              </th>
              <th className={THEME.TH}>Cp (mg/L)</th>

              {has.Qc && <th className={THEME.TH}>{`Qc (${u.flow})`}</th>}

              {/* UF가 있을 때만 보이는 역세척 손실 헤더 */}
              {has.UF && <th className={THEME.TH}>{`BW Loss (${u.flow})`}</th>}

              {has.Cc && <th className={THEME.TH}>Cc (mg/L)</th>}
              {has.dP && <th className={THEME.TH}>{`ΔP (${u.pressure})`}</th>}

              <th className={THEME.TH}>
                {has.UF ? 'Gross Rec (%)' : 'Recovery (%)'}
              </th>

              {/* UF가 있을 때만 보이는 순 회수율 헤더 */}
              {has.UF && <th className={THEME.TH}>Net Rec (%)</th>}
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i} className={THEME.TR}>
                <td className={THEME.TD_LABEL}>{`Stage ${r.stage}`}</td>
                <td className={THEME.TD}>{String(r.type)}</td>

                {has.Qf && <td className={THEME.TD}>{fmt(r.Qf)}</td>}
                {has.Cf && <td className={THEME.TD}>{fmt(r.Cf)}</td>}

                {has.UF && (
                  <td className={THEME.TD}>
                    {r.grossQ != null ? fmt(r.grossQ) : '-'}
                  </td>
                )}

                <td className={THEME.TD}>{fmt(r.Qp)}</td>
                <td className={THEME.TD}>{fmt(r.Cp)}</td>

                {has.Qc && <td className={THEME.TD}>{fmt(r.Qc)}</td>}

                {has.UF && (
                  <td className={THEME.TD}>
                    {r.bwLoss != null ? fmt(r.bwLoss) : '-'}
                  </td>
                )}

                {has.Cc && <td className={THEME.TD}>{fmt(r.Cc)}</td>}
                {has.dP && <td className={THEME.TD}>{fmt(r.dP)}</td>}

                <td className={THEME.TD}>{r.rec == null ? '-' : pct(r.rec)}</td>

                {has.UF && (
                  <td className={THEME.TD}>
                    {r.netRec == null ? '-' : pct(r.netRec)}
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="px-3 py-2 text-[10px] text-slate-500 bg-white border-t border-slate-200">
        * UF 스테이지가 포함된 경우, 순수 생산량(Net Qp), 세정 손실량(BW Loss),
        최종 순 회수율(Net Rec)이 분리되어 표시됩니다.
      </div>
    </div>
  );
}
