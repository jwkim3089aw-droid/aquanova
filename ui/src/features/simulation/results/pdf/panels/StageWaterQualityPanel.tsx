// ui/src/features/simulation/results/pdf/panels/StageWaterQualityPanel.tsx
import React from 'react';
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
    grossQ: ['gross_flow_m3h'],
    bwLoss: ['backwash_loss_m3h'],
    netRec: ['net_recovery_pct'],
  };

  const rows = stages.map((s: any, idx: number) => {
    const stage = s?.stage ?? idx + 1;
    const type = String(
      s?.module_type ?? s?.type ?? s?.membrane_model ?? 'RO',
    ).toUpperCase();

    // 기본 값 추출
    const Qf = pickNumFromKeys(s, keys.Qf);
    const Cf = pickNumFromKeys(s, keys.Cf);
    const Qp = first(pickNumber(s?.Qp), pickNumFromKeys(s, keys.Qp));
    const Cp = first(pickNumber(s?.Cp), pickNumFromKeys(s, keys.Cp));
    const Qc = pickNumFromKeys(s, keys.Qc);
    const Cc = pickNumFromKeys(s, keys.Cc);
    const dP = first(pickNumber(s?.dp_bar), pickNumFromKeys(s, keys.dP));

    let rec = pickNumber(s?.recovery_pct);
    let grossQ = pickNumFromKeys(s, keys.grossQ);
    let bwLoss = pickNumFromKeys(s, keys.bwLoss);
    let netRec = pickNumFromKeys(s, keys.netRec);

    // 💡 [PATCH] MF/UF 스마트 폴백 로직 적용 (0으로 들어오는 데이터까지 방어)
    if (['MF', 'UF'].includes(type)) {
      if (grossQ == null || grossQ === 0) grossQ = Qf;
      if (bwLoss == null || bwLoss === 0) bwLoss = Qc;
      const netFlow = Qp;

      // 회수율(Gross) 계산 폴백
      if (rec == null && grossQ > 0) {
        rec = ((Qp + (Qc ?? 0)) / grossQ) * 100;
      }

      // 🎯 순 회수율(Net Rec)이 없거나 0.0일 경우, 유량 기반으로 역산하여 채움!
      if (netRec == null || netRec === 0) {
        netRec = grossQ > 0 ? (netFlow / grossQ) * 100 : 0;
      }
    }

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
    UF: rows.some(
      (r) =>
        r.grossQ != null || r.netRec != null || ['MF', 'UF'].includes(r.type),
    ),
  };

  // WAVE 스타일 테이블 클래스 정의
  const thClass =
    'py-1.5 px-2 text-[9px] font-bold text-slate-800 border border-slate-400 bg-slate-200 text-center whitespace-pre-wrap align-middle leading-tight tracking-tighter';
  const tdClass =
    'py-1 px-2 text-[10px] text-slate-800 border border-slate-300 text-center tabular-nums bg-white';
  const highlightTd =
    'py-1 px-2 text-[10px] font-bold text-blue-900 border border-slate-300 text-center tabular-nums bg-blue-50/50';
  const labelTd =
    'py-1 px-2 text-[10px] font-bold text-slate-800 border border-slate-300 text-center bg-slate-50';

  return (
    <div className="w-full print:break-inside-avoid overflow-x-auto">
      <table className="w-full border-collapse border-2 border-slate-500 min-w-max">
        <thead>
          <tr>
            <th className={thClass}>구간{'\n'}(Stage)</th>
            <th className={thClass}>공정 타입{'\n'}(Type)</th>

            {has.Qf && <th className={thClass}>{`유입수\n(${u.flow})`}</th>}
            {has.Cf && <th className={thClass}>{`유입 TDS\n(mg/L)`}</th>}

            {has.UF && <th className={thClass}>{`총 유량\n(${u.flow})`}</th>}

            {/* 🎯 핵심 결과 열 헤더 (생산수) */}
            <th className={thClass}>
              {has.UF ? `순 생산수\n(${u.flow})` : `생산수\n(${u.flow})`}
            </th>
            <th className={thClass}>{`생산 TDS\n(mg/L)`}</th>

            {has.Qc && <th className={thClass}>{`농축수\n(${u.flow})`}</th>}
            {has.UF && <th className={thClass}>{`역세 손실\n(${u.flow})`}</th>}
            {has.Cc && <th className={thClass}>{`농축 TDS\n(mg/L)`}</th>}
            {has.dP && (
              <th className={thClass}>{`차압 ΔP\n(${u.pressure})`}</th>
            )}

            <th className={thClass}>
              {has.UF ? `총 회수율\n(%)` : `회수율\n(%)`}
            </th>

            {/* 🎯 핵심 결과 열 헤더 (순 회수율) */}
            {has.UF && <th className={thClass}>{`순 회수율\n(%)`}</th>}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} className="hover:bg-slate-50/50">
              <td className={labelTd}>{r.stage}</td>
              <td className={tdClass}>{r.type}</td>

              {has.Qf && (
                <td className={tdClass}>{r.Qf != null ? fmt(r.Qf) : '-'}</td>
              )}
              {has.Cf && (
                <td className={tdClass}>{r.Cf != null ? fmt(r.Cf) : '-'}</td>
              )}

              {has.UF && (
                <td className={tdClass}>
                  {r.grossQ != null ? fmt(r.grossQ) : '-'}
                </td>
              )}

              {/* 🎯 핵심 결과 데이터 (Qp, Cp) - 강조 테마 적용 */}
              <td className={highlightTd}>{r.Qp != null ? fmt(r.Qp) : '-'}</td>
              <td className={highlightTd}>{r.Cp != null ? fmt(r.Cp) : '-'}</td>

              {has.Qc && (
                <td className={tdClass}>{r.Qc != null ? fmt(r.Qc) : '-'}</td>
              )}
              {has.UF && (
                <td className={tdClass}>
                  {r.bwLoss != null ? fmt(r.bwLoss) : '-'}
                </td>
              )}
              {has.Cc && (
                <td className={tdClass}>{r.Cc != null ? fmt(r.Cc) : '-'}</td>
              )}
              {has.dP && (
                <td className={tdClass}>{r.dP != null ? fmt(r.dP) : '-'}</td>
              )}

              <td className={tdClass}>{r.rec == null ? '-' : pct(r.rec)}</td>

              {/* 🎯 핵심 결과 데이터 (순 회수율) - 강조 테마 적용 */}
              {has.UF && (
                <td className={highlightTd}>
                  {r.netRec == null ? '-' : pct(r.netRec)}
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>

      {/* PDF 원본 각주 스타일 재현 */}
      <div className="mt-1 text-[9px] text-slate-500 font-medium">
        * 강조된 열은 시스템의 최종 생산수(Product) 및 주요 성능 지표입니다.
      </div>
    </div>
  );
}
