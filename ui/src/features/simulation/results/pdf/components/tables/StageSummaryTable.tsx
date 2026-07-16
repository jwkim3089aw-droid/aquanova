// ui/src/features/simulation/results/pdf/components/tables/StageSummaryTable.tsx
import React from 'react';
import { fmt, pct } from '../../utils';
import { UnitLabels } from '../../types';

export function StageSummaryTable({
  stages,
  u,
}: {
  stages: any[];
  u: UnitLabels;
}) {
  // 🛑 [WAVE PATCH] 출력 시 잘림 방지: 폰트 사이즈를 8px/9px로 줄이고, 좌우 여백(px-0.5)을 극한으로 줄임
  const thClass =
    'py-1 px-0.5 text-[8px] font-bold text-slate-800 border border-slate-400 bg-slate-200 text-center whitespace-pre-wrap align-middle leading-tight tracking-tighter break-words';
  const tdClass =
    'py-1 px-0.5 text-[9px] text-slate-800 border border-slate-300 text-center tabular-nums tracking-tighter';
  const labelTd =
    'py-1 px-0.5 text-[9px] font-bold text-slate-800 border border-slate-300 text-center bg-slate-50';

  return (
    // 🛑 overflow-x-auto 제거하여 스크롤 원천 차단
    <div className="w-full print:break-inside-avoid">
      {/* 🛑 min-w-max 제거하여 테이블이 부모 div(A4 가로폭)를 넘어가지 못하게 강제함 */}
      <table className="w-full border-collapse border-2 border-slate-500">
        <thead>
          {/* 1단 헤더: 기능별 그룹핑 (한국어 적용) */}
          <tr>
            <th className={thClass} rowSpan={2}>
              구간{'\n'}(Stage)
            </th>
            <th className={thClass} rowSpan={2}>
              공정 타입{'\n'}(Type)
            </th>
            <th className={thClass} rowSpan={2}>
              배열{'\n'}(Ves x Ele)
            </th>
            <th className={thClass} colSpan={2}>
              유입수 (Feed)
            </th>
            <th className={thClass} colSpan={3}>
              생산수 (Product)
            </th>
            <th className={thClass} colSpan={3}>
              농축수 & 손실 (Brine & Loss)
            </th>
            <th className={thClass} colSpan={2}>
              압력 ({u.pressure || 'bar'})
            </th>
            <th className={thClass} colSpan={2}>
              회수율 (%)
            </th>
            <th className={thClass} rowSpan={2}>
              평균 플럭스{'\n'}({u.flux || 'LMH'})
            </th>
          </tr>
          {/* 2단 헤더: 상세 항목 (한국어 적용) */}
          <tr>
            {/* Feed */}
            <th className={thClass}>
              유량{'\n'}({u.flow || 'm³/h'})
            </th>
            <th className={thClass}>TDS{'\n'}(mg/L)</th>

            {/* Product */}
            <th className={thClass}>총 유량{'\n'}(Gross)</th>
            <th className={thClass}>순 유량{'\n'}(Net)</th>
            <th className={thClass}>TDS{'\n'}(mg/L)</th>

            {/* Brine & Loss */}
            <th className={thClass}>
              유량{'\n'}({u.flow || 'm³/h'})
            </th>
            <th className={thClass}>역세 손실{'\n'}(BW Loss)</th>
            <th className={thClass}>TDS{'\n'}(mg/L)</th>

            {/* Pressure */}
            <th className={thClass}>유입 (P in)</th>
            <th className={thClass}>차압 (ΔP)</th>

            {/* Recovery */}
            <th className={thClass}>총 (Gross)</th>
            <th className={thClass}>순 (Net)</th>
          </tr>
        </thead>
        <tbody>
          {stages.map((s: any, i: number) => {
            // 백엔드 데이터 매핑 및 폴백(Fallback) 처리
            const membrane =
              s?.membrane_model || s?.module_type || s?.type || 'UF';
            const arrayStr =
              s?.vessel_count && s?.elements_per_vessel
                ? `${s.vessel_count} x ${s.elements_per_vessel}`
                : '-';

            // 🟢 1. 압력 매핑 수정: 백엔드 엔진의 Pf, Pb, delta_p 키값 추가
            const pIn = s?.Pf ?? s?.feed_pressure ?? s?.p_in_bar;
            const pOut = s?.Pb ?? s?.brine_pressure ?? s?.p_out_bar;
            const dp =
              s?.delta_p ??
              s?.dp_bar ??
              (pIn != null && pOut != null ? pIn - pOut : null);

            // 🟢 2. 유량 및 수질 매핑 수정: Qb, Cb, Qp 등의 표준 물리 엔진 키값 추가
            const feedTds = s?.Cf ?? s?.feed_tds_mgL ?? null;
            const permTds = s?.Cp ?? s?.permeate_tds_mgL ?? null;

            const grossQ = s?.gross_q ?? s?.Qp;
            const netQ = s?.net_q ?? s?.Qp;
            const bwLoss =
              s?.bw_loss ?? s?.Qbw ?? (grossQ && netQ ? grossQ - netQ : 0);

            const brineQ = s?.Qb ?? s?.Qc ?? s?.brine_flow_m3h ?? null;
            const brineTds = s?.Cb ?? s?.Cc ?? s?.brine_tds_mgL ?? null;

            // 회수율
            const grossRec = s?.gross_recovery_pct ?? s?.recovery_pct;
            const netRec = s?.net_recovery_pct ?? s?.recovery_pct;

            const flux = s?.flux_lmh ?? s?.jw_avg_lmh ?? null;

            return (
              <tr key={i} className="hover:bg-slate-50/50">
                <td className={labelTd}>{s?.stage ?? i + 1}</td>
                <td className={tdClass}>{membrane}</td>
                <td className={tdClass}>{arrayStr}</td>

                {/* Feed */}
                <td className={tdClass}>{fmt(s?.Qf)}</td>
                <td className={tdClass}>
                  {feedTds != null ? fmt(feedTds) : '-'}
                </td>

                {/* Product */}
                <td className={tdClass}>{fmt(grossQ)}</td>
                <td className={tdClass}>{fmt(netQ)}</td>
                <td className={tdClass}>
                  {permTds != null ? fmt(permTds) : '-'}
                </td>

                {/* Brine & Loss */}
                <td className={tdClass}>{fmt(brineQ)}</td>
                <td className={tdClass}>{fmt(bwLoss)}</td>
                <td className={tdClass}>
                  {brineTds != null ? fmt(brineTds) : '-'}
                </td>

                {/* Pressure */}
                <td className={tdClass}>{fmt(pIn)}</td>
                <td className={tdClass}>{fmt(dp)}</td>

                {/* Recovery */}
                <td className={tdClass}>{pct(grossRec)}</td>
                <td className={tdClass}>{pct(netRec)}</td>

                {/* Flux */}
                <td className={tdClass}>{fmt(flux)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
