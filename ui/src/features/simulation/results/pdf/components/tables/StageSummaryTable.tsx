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
  // ✅ 종이 출력(A4)에 맞게 공간을 최대한 절약하는 커스텀 클래스
  // 1. !px-1.5 !py-1 : 좌우 위아래 여백 최소화
  // 2. text-[8.5px] / text-[9px] : 폰트 크기 미세 축소
  // 3. tracking-tighter : 자간 축소
  // 4. whitespace-pre-wrap : 우리가 넣은 \n (엔터) 위치에서만 예쁘게 줄바꿈됨
  // 5. break-keep : 단어 중간에서 찢어지는 현상 방지
  const tightTh = `${THEME.TH} !px-1.5 !py-1.5 text-[8.5px] tracking-tighter text-center whitespace-pre-wrap break-keep leading-tight`;
  const tightTd = `${THEME.TD} !px-1.5 !py-1.5 text-[9px] tracking-tighter text-center break-keep`;
  const tightTdLabel = `${THEME.TD_LABEL} !px-1.5 !py-1.5 text-[9px] tracking-tighter text-center whitespace-nowrap`;

  return (
    <div className={THEME.TABLE_WRAP}>
      {/* 가로 스크롤은 제거하고 전체 100% 폭을 쓰도록 설정 */}
      <table className={`${THEME.TABLE} table-fixed`}>
        <thead>
          <tr>
            <th className={tightTh}>Stage</th>
            <th className={tightTh}>Type</th>
            <th className={tightTh}>Recovery</th>
            {/* 단어와 단위(unit) 사이를 \n으로 명시적 줄바꿈 처리 */}
            <th className={tightTh}>{`Flux\n(${u.flux})`}</th>
            <th className={tightTh}>{`NDP\n(${u.pressure})`}</th>
            <th className={tightTh}>{`SEC\n(kWh/m³)`}</th>
            <th className={tightTh}>{`p_in\n(${u.pressure})`}</th>
            <th className={tightTh}>{`p_out\n(${u.pressure})`}</th>
            <th className={tightTh}>{`Qp\n(${u.flow})`}</th>
            <th className={tightTh}>{`Cp\n(mg/L)`}</th>
          </tr>
        </thead>
        <tbody>
          {stages.map((s: any, i: number) => {
            const flux = s?.flux_lmh ?? s?.jw_avg_lmh ?? null;
            const sec = s?.sec_kwhm3 ?? s?.sec_kwh_m3 ?? null;
            return (
              <tr key={i} className={THEME.TR}>
                <td className={tightTdLabel}>{s?.stage ?? i + 1}</td>
                <td className={tightTd}>{s?.module_type ?? '-'}</td>
                <td className={tightTd}>{pct(s?.recovery_pct)}</td>
                <td className={tightTd}>{fmt(flux)}</td>
                <td className={tightTd}>{fmt(s?.ndp_bar)}</td>
                <td className={tightTd}>{fmt(sec)}</td>
                <td className={tightTd}>{fmt(s?.p_in_bar)}</td>
                <td className={tightTd}>{fmt(s?.p_out_bar)}</td>
                <td className={tightTd}>{fmt(s?.Qp)}</td>
                <td className={tightTd}>{fmt(s?.Cp)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>

      <div className="px-3 py-2 text-[10px] text-slate-500 bg-white border-t border-slate-200">
        * 상세(Qf/Qc/Cf/Cc, element profile 등)는 아래 패널에서(존재 시) 추가로
        표시됩니다. 또한 Raw(접기)에서 전체 키를 확인할 수 있습니다.
      </div>
    </div>
  );
}
