// ui/src/features/simulation/results/pdf/components/KPI.tsx
import React from 'react';

export function KPI({
  labelKo,
  valueText,
  hint,
  icon,
  tone = 'slate',
}: {
  labelKo: string;
  valueText: string;
  hint?: string;
  icon?: React.ReactNode;
  tone?: 'slate' | 'blue' | 'emerald' | 'amber';
}) {
  const tones: Record<string, string> = {
    slate: 'border-slate-200 bg-white',
    blue: 'border-blue-200 bg-blue-50/40',
    emerald: 'border-emerald-200 bg-emerald-50/40',
    amber: 'border-amber-200 bg-amber-50/40',
  };

  return (
    <div className={`rounded-xl border p-4 ${tones[tone]}`}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-[10px] font-extrabold uppercase tracking-widest text-slate-500">
            {labelKo}
          </div>
          <div className="text-xl font-mono font-black text-slate-900 mt-1">
            {valueText}
          </div>
          {hint ? (
            <div className="text-[10px] text-slate-500 mt-1">{hint}</div>
          ) : null}
        </div>
        <div className="opacity-60">{icon}</div>
      </div>
    </div>
  );
}
