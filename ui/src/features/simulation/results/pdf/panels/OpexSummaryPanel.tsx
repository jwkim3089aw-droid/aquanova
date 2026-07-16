// ui/src/features/simulation/results/pdf/panels/OpexSummaryPanel.tsx
import React from 'react';
import { Section } from '../components/Section';

interface EconomicsOut {
  unit_cost: number;
  energy_cost_per_m3: number;
  chem_cost_per_m3: number;
  energy_portion_pct: number;
  chem_portion_pct: number;
  daily_total_cost: number;
  currency: string;
}

interface OpexSummaryPanelProps {
  economics?: EconomicsOut | null;
}

export const OpexSummaryPanel: React.FC<OpexSummaryPanelProps> = ({
  economics,
}) => {
  if (!economics || economics.unit_cost === 0) {
    return null;
  }

  const {
    unit_cost,
    energy_cost_per_m3,
    chem_cost_per_m3,
    energy_portion_pct,
    chem_portion_pct,
    daily_total_cost,
    currency,
  } = economics;

  // 💡 B2B Report Strict Table Theme 적용
  const tableClass = 'w-full border-collapse border-2 border-slate-500';
  const thClass =
    'py-1.5 px-3 text-[11px] font-bold text-slate-800 border border-slate-400 bg-slate-200 text-center uppercase tracking-wider';
  const tdClass =
    'py-1 px-3 text-[11px] text-slate-900 border border-slate-300 text-right tabular-nums';
  const tdLabelClass =
    'py-1 px-3 text-[11px] font-bold text-slate-700 border border-slate-300 bg-slate-50 text-left';

  return (
    <Section
      title="경제성 평가 요약 (Economics & OPEX Summary)"
      className="break-inside-avoid"
    >
      <div className="w-full">
        {/* Top: Highlighted KPIs (Summary Bar) */}
        <div className="flex items-center justify-between px-4 py-2.5 mb-3 bg-slate-100 border border-slate-400 shadow-sm rounded-sm">
          <div className="flex flex-col">
            <span className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">
              총 생산 단가 (Total Unit Cost)
            </span>
            <span className="text-lg font-black text-slate-900 font-mono tracking-tight">
              {currency}
              {unit_cost.toFixed(4)}{' '}
              <span className="text-xs text-slate-600 font-sans">/ m³</span>
            </span>
          </div>
          <div className="h-8 border-r-2 border-slate-300"></div>
          <div className="flex flex-col text-right">
            <span className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">
              총 일일 운영비 (Total Daily Cost)
            </span>
            <span className="text-lg font-black text-slate-900 font-mono tracking-tight">
              {currency}
              {daily_total_cost.toLocaleString(undefined, {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2,
              })}{' '}
              <span className="text-xs text-slate-600 font-sans">/ day</span>
            </span>
          </div>
        </div>

        {/* Bottom: Cost Breakdown Details (Strict Table Theme) */}
        <table className={tableClass}>
          <thead>
            <tr>
              <th className={thClass} style={{ width: '40%' }}>
                비용 항목 (Cost Category)
              </th>
              <th className={thClass} style={{ width: '30%' }}>
                단가 (Specific Cost)
              </th>
              <th className={thClass} style={{ width: '30%' }}>
                비중 (Portion)
              </th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td className={tdLabelClass}>전력비 (Energy Cost)</td>
              <td className={tdClass}>
                {currency}
                {energy_cost_per_m3.toFixed(4)} / m³
              </td>
              <td className={`${tdClass} text-slate-700 font-bold`}>
                {energy_portion_pct.toFixed(1)}%
              </td>
            </tr>
            <tr>
              <td className={tdLabelClass}>약품비 (Chemical Cost)</td>
              <td className={tdClass}>
                {currency}
                {chem_cost_per_m3.toFixed(4)} / m³
              </td>
              <td className={`${tdClass} text-slate-700 font-bold`}>
                {chem_portion_pct.toFixed(1)}%
              </td>
            </tr>
          </tbody>
        </table>

        {/* Visual Stacked Bar (Simple & Clean) */}
        <div className="w-full h-1.5 flex overflow-hidden bg-slate-200 mt-0.5 shadow-inner">
          <div
            style={{ width: `${energy_portion_pct}%` }}
            className="h-full bg-slate-700"
            title={`Energy: ${energy_portion_pct}%`}
          ></div>
          <div
            style={{ width: `${chem_portion_pct}%` }}
            className="h-full bg-slate-400"
            title={`Chemical: ${chem_portion_pct}%`}
          ></div>
        </div>
      </div>
    </Section>
  );
};
