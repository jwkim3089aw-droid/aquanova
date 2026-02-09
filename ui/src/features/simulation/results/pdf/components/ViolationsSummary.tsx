// ui/src/features/simulation/results/pdf/components/ViolationsSummary.tsx
import React from 'react';
import { safeArr } from '../utils';
import { Badge } from './Badge';

export function ViolationsSummary({ violations }: { violations: any[] }) {
  const rows = safeArr(violations);
  const count = rows.length;
  if (!count) return <Badge text="VIOL 0" tone="emerald" />;

  const top = rows.slice(0, 3).map((v) => v?.message || v?.key || 'violation');
  return (
    <div className="flex items-center gap-2">
      <Badge text={`VIOL ${count}`} tone="rose" />
      <div className="text-[10px] text-slate-500">
        {top.join(' · ')}
        {count > 3 ? ' · …' : ''}
      </div>
    </div>
  );
}
