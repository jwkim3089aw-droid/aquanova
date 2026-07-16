// ui/src/features/simulation/results/pdf/panels/ChemicalDosingPanel.tsx
// ui/src/features/simulation/results/pdf/panels/ChemicalDosingPanel.tsx
import React from 'react';
import { THEME } from '../theme';
import { fmt } from '../utils';

export function ChemicalDosingPanel({ dosing }: { dosing: any; u?: any }) {
  if (!dosing) return null;

  const items = dosing.dosing_items || [];
  const phTarget = dosing.target_ph ?? '-';
  const actualPh = dosing.actual_ph ?? '-';

  // 💡 첨부해주신 이미지(BrineScalingPanel)와 완벽하게 동일한 깔끔한 Slate 테마 적용
  const tableClass = 'w-full border-collapse border-2 border-slate-500';
  const thClass =
    'py-1.5 px-3 text-[11px] font-bold text-slate-800 border border-slate-400 bg-slate-200 text-center';
  const tdClass =
    'py-1 px-3 text-[11px] text-slate-900 border border-slate-300 text-center tabular-nums';
  const tdLabelClass =
    'py-1 px-3 text-[11px] font-semibold text-slate-700 border border-slate-300 bg-slate-50 text-center';

  return (
    <div className="w-full print:break-inside-avoid">
      {/* 💡 수정됨: font-mono를 부모에서 제거하고 items-center로 수직 정렬을 맞춤 */}
      <div className="flex items-center gap-4 mb-2 px-3 text-[10px] text-slate-600 bg-slate-50 py-1.5 rounded border border-slate-300 shadow-sm">
        <span className="font-bold text-slate-800">
          설정 목표 pH:{' '}
          <span className="font-mono text-[11px] ml-0.5">{phTarget}</span>
        </span>
        <span className="text-slate-300">|</span>
        <span className="font-bold text-blue-800">
          최종 평형 pH (이론값):{' '}
          <span className="font-mono text-[11px] ml-0.5">{fmt(actualPh)}</span>
        </span>
      </div>

      <table className={tableClass}>
        <thead>
          <tr>
            <th className={thClass}>투입 목적 (Purpose)</th>
            <th className={thClass}>약품 종류 (Chemical Type)</th>
            <th className={thClass}>투입 농도 (Dosage)</th>
            <th className={thClass}>일일 소모량 (Consumption)</th>
          </tr>
        </thead>
        <tbody>
          {items.length > 0 ? (
            items.map((item: any, idx: number) => (
              <tr key={idx} className="hover:bg-slate-50/50">
                <td className={tdLabelClass}>{item.purpose}</td>
                <td className={tdClass}>{item.chemical_name}</td>
                <td className={tdClass}>{fmt(item.dose_mgL)} ppm (mg/L)</td>
                <td className={tdClass}>
                  <span className="font-bold text-slate-800">
                    {fmt(item.usage_kg_day, 3)} kg/일
                  </span>
                </td>
              </tr>
            ))
          ) : (
            <tr>
              <td
                colSpan={4}
                className="py-4 text-center text-[10px] text-slate-400 italic border border-slate-300"
              >
                현재 수질 조건에서 추가적인 약품 투입이 필요하지 않습니다.
              </td>
            </tr>
          )}
        </tbody>
      </table>

      {/* 약품 투입 관련 기술적 경고 */}
      {dosing.warnings?.length > 0 && (
        <div className="mt-2 p-2 bg-amber-50 border border-amber-200 rounded text-[10px] text-amber-800 shadow-sm">
          <div className="font-bold flex items-center gap-1 mb-1">
            <span>⚠️</span> 약품 투입 관련 주의사항 (Dosing Warnings)
          </div>
          <ul className="list-disc ml-5 space-y-0.5">
            {dosing.warnings.map((w: string, i: number) => (
              <li key={i} className="leading-tight">
                {w}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
