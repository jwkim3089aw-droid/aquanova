// ui/src/features/simulation/results/pdf/components/KVGrid.tsx
import React from 'react';
import { fmt } from '../utils';

export function KVGrid({
  items,
  cols = 3,
}: {
  items: { k: string; v: any; unit?: string }[];
  cols?: 2 | 3 | 4;
}) {
  const gridCols =
    cols === 2 ? 'grid-cols-2' : cols === 4 ? 'grid-cols-4' : 'grid-cols-3';

  return (
    <div className={`grid ${gridCols} gap-2`}>
      {items.map((it) => (
        <div
          key={it.k}
          className="rounded-lg border border-slate-200 bg-slate-50/40 px-3 py-2"
        >
          <div className="text-[10px] font-extrabold uppercase tracking-widest text-slate-500">
            {it.k}
          </div>
          <div className="mt-1 font-mono text-sm font-black text-slate-900">
            {it.v == null ? '-' : fmt(it.v)}
            {it.unit ? (
              <span className="ml-1 text-[10px] text-slate-500 font-bold">
                {it.unit}
              </span>
            ) : null}
          </div>
        </div>
      ))}
    </div>
  );
}
