// ui/src/features/simulation/results/pdf/components/JsonDetails.tsx
import React from 'react';
import { Database } from 'lucide-react';
import { pretty, summarizeValue, trunc } from '../utils';

export function JsonDetails({
  titleKo,
  obj,
  defaultOpen = false,
  maxChars = 12000,
}: {
  titleKo: string;
  obj: any;
  defaultOpen?: boolean;
  maxChars?: number;
}) {
  const has =
    obj != null &&
    ((typeof obj === 'object' && Object.keys(obj).length > 0) ||
      (Array.isArray(obj) && obj.length > 0) ||
      (typeof obj !== 'object' && String(obj).length > 0));

  if (!has) {
    return <div className="text-[10px] text-slate-500">No data.</div>;
  }

  return (
    <details
      className="rounded-xl border border-slate-200 bg-slate-50/40 p-3"
      open={defaultOpen}
    >
      <summary className="cursor-pointer text-[11px] font-extrabold text-slate-700 flex items-center gap-2">
        <Database className="w-4 h-4 opacity-70" />
        {titleKo}
        <span className="text-[10px] text-slate-500 font-bold">
          ({summarizeValue(obj)})
        </span>
      </summary>
      <pre className="mt-3 whitespace-pre-wrap break-words font-mono text-[9px] leading-snug text-slate-700">
        {trunc(pretty(obj), maxChars)}
      </pre>
    </details>
  );
}
