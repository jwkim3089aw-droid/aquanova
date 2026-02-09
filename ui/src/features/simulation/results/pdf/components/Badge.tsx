// ui/src/features/simulation/results/pdf/components/Badge.tsx
import React from 'react';

export function Badge({
  text,
  tone = 'slate',
}: {
  text: string;
  tone?: 'slate' | 'emerald' | 'rose' | 'amber' | 'blue' | 'violet';
}) {
  const map: Record<string, string> = {
    slate: 'bg-slate-100 text-slate-700 border-slate-200',
    emerald: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    rose: 'bg-rose-50 text-rose-700 border-rose-200',
    amber: 'bg-amber-50 text-amber-800 border-amber-200',
    blue: 'bg-blue-50 text-blue-700 border-blue-200',
    violet: 'bg-violet-50 text-violet-700 border-violet-200',
  };

  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded-full border text-[10px] font-bold ${map[tone]}`}
    >
      {text}
    </span>
  );
}
