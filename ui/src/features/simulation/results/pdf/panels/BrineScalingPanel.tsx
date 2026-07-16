// ui/src/features/simulation/results/pdf/panels/BrineScalingPanel.tsx
import React from 'react';

export function BrineScalingPanel({ chemistry }: { chemistry: any }) {
  const brine = chemistry?.final_brine;

  if (!brine) {
    return null;
  }

  // WAVE 스타일의 밀도 높은 테두리 디자인
  const thClass =
    'py-1.5 px-3 text-[11px] font-bold text-slate-800 border border-slate-400 bg-slate-200 text-left';
  const tdLabelClass =
    'py-1 px-3 text-[11px] font-semibold text-slate-700 border border-slate-300 bg-slate-50';
  const tdValueClass =
    'py-1 px-3 text-[11px] text-right tabular-nums border border-slate-300';
  const tdStatusClass =
    'py-1 px-3 text-[10px] text-center font-bold border border-slate-300 uppercase tracking-wide';

  // 상태 판별 함수 (WAVE 스타일의 엄격한 기준 적용)
  const evaluate = (
    val: number | undefined | null,
    warnLimit: number,
    errLimit: number,
  ) => {
    if (val == null) return { status: '-', color: 'text-slate-500' };
    if (val > errLimit)
      return { status: '초과 (Exceeded)', color: 'text-red-700 bg-red-50' };
    if (val > warnLimit)
      return { status: '경고 (Warning)', color: 'text-amber-600 bg-amber-50' };
    return { status: '정상 (OK)', color: 'text-emerald-700' };
  };

  const metrics = [
    {
      label: '랑겔리아 포화 지수 (LSI)',
      val: brine.lsi,
      limit: 1.8,
      warn: 0.5,
      unit: '',
    },
    {
      label: '스티프 & 데이비스 지수 (S&DSI)',
      val: brine.s_dsi,
      limit: 1.8,
      warn: 0.5,
      unit: '',
    },
    {
      label: '황산칼슘 포화도 (CaSO4)',
      val: brine.caso4_sat_pct,
      limit: 100,
      warn: 80,
      unit: '%',
    },
    {
      label: '황산바륨 포화도 (BaSO4)',
      val: brine.baso4_sat_pct,
      limit: 100,
      warn: 80,
      unit: '%',
    },
    {
      label: '실리카 포화도 (SiO2)',
      val: brine.sio2_sat_pct,
      limit: 100,
      warn: 80,
      unit: '%',
    },
    // 백엔드 확장을 대비한 추가 항목들 (데이터가 들어오면 자동으로 표기됨)
    {
      label: '황산스트론튬 포화도 (SrSO4)',
      val: brine.srso4_sat_pct,
      limit: 100,
      warn: 80,
      unit: '%',
    },
    {
      label: '불화칼슘 포화도 (CaF2)',
      val: brine.caf2_sat_pct,
      limit: 100,
      warn: 80,
      unit: '%',
    },
  ].filter((m) => m.val != null);

  if (metrics.length === 0) return null;

  return (
    <div className="w-full print:break-inside-avoid">
      {/* 섹션 타이틀: 뱃지를 없애고 세련된 세로선(Border) 강조 적용 */}
      <div className="text-[12px] font-bold text-slate-800 mb-2 pl-2 border-l-2 border-slate-800 uppercase tracking-wider">
        용해도 및 스케일링 지표 (농축수 기준) - Solubility & Scaling
      </div>

      <table className="w-full border-collapse border-2 border-slate-500">
        <thead>
          <tr>
            <th className={thClass}>평가 항목 (Parameter)</th>
            <th className={`${thClass} text-right`}>결과값 (Value)</th>
            <th className={`${thClass} text-right`}>제한 기준 (Limit)</th>
            <th className={`${thClass} text-center`}>상태 (Status)</th>
          </tr>
        </thead>
        <tbody>
          {metrics.map((m, i) => {
            const { status, color } = evaluate(m.val, m.warn, m.limit);
            const displayVal =
              typeof m.val === 'number' ? m.val.toFixed(2) : '-';
            const limitTxt = `최대 ${m.limit}${m.unit}`;

            return (
              <tr key={i} className="hover:bg-slate-50/50">
                <td className={tdLabelClass}>{m.label}</td>
                <td className={`${tdValueClass} font-mono text-slate-900`}>
                  {displayVal}
                  {m.unit}
                </td>
                <td className={`${tdValueClass} text-slate-500`}>{limitTxt}</td>
                <td className={`${tdStatusClass} ${color}`}>{status}</td>
              </tr>
            );
          })}
        </tbody>
      </table>

      {/* 엔지니어링 리포트 특유의 하단 각주(Footnote) */}
      <div className="mt-1 text-[9px] text-slate-500 italic">
        * 경고(Warning): 값이 용해도 한계에 근접하고 있음을 나타냅니다. 한계를
        초과(Exceeded)한 경우 스케일 방지제(Antiscalant) 투입 또는 설계 변경이
        필요합니다.
      </div>
    </div>
  );
}
