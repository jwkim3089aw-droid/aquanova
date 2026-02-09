// ui\src\features\simulation\components\IonTable.tsx
import React from 'react';
import type { IonDef } from '../chemistry';
import { fmtInputNumber, fmtNumber, n0 } from '../chemistry';
import { meqL_to_ppmCaCO3, mgL_to_meqL } from '../chemistry';

export function IonTable({
  title,
  defs,
  chem,
  onChange,
  accent = 'text-slate-200',
  showDerived = true,
  compact = false,
}: {
  title: string;
  defs: IonDef[];
  chem: any;
  onChange: (key: string, v: number) => void;
  accent?: string;
  showDerived?: boolean;
  compact?: boolean;
}) {
  const mgSum = defs.reduce((acc, d) => acc + n0(chem?.[d.key]), 0);

  return (
    <div className="bg-slate-900/40 border border-slate-800 rounded-lg overflow-hidden">
      <div
        className={`px-3 ${compact ? 'py-1.5' : 'py-2'} flex items-center justify-between border-b border-slate-800 bg-slate-900/60`}
      >
        <div
          className={`text-[11px] font-bold uppercase tracking-wider ${accent}`}
        >
          {title}
        </div>
        <div className="text-[11px] font-mono text-slate-400">
          {fmtNumber(mgSum, 2)} mg/L
        </div>
      </div>

      <div className={`px-3 ${compact ? 'py-1.5' : 'py-2'}`}>
        <div className="grid grid-cols-4 gap-2 text-[10px] text-slate-500 uppercase tracking-wider px-2 mb-1">
          <div>이온</div>
          <div className="text-right">mg/L</div>
          <div className="text-right">ppm(CaCO3)</div>
          <div className="text-right">meq/L</div>
        </div>

        <div className="space-y-1">
          {defs.map((d) => {
            const mgL = n0(chem?.[d.key]);
            const meqL = showDerived ? mgL_to_meqL(mgL, d.mw, d.z) : 0;
            const ppm = showDerived ? meqL_to_ppmCaCO3(meqL) : 0;

            return (
              <div
                key={d.key}
                className={`grid grid-cols-4 gap-2 items-center px-2 ${
                  compact ? 'py-[5px]' : 'py-1'
                } rounded border border-slate-800/70 bg-slate-950/40 hover:border-slate-700 transition-colors`}
              >
                <div className="text-[11px] font-semibold text-slate-300 w-12">
                  {d.label}
                </div>

                <input
                  type="number"
                  step="any"
                  className="w-full bg-transparent text-right text-[12px] text-slate-200 outline-none font-mono"
                  value={fmtInputNumber(chem?.[d.key], 3)}
                  placeholder="0"
                  onFocus={(e) => e.currentTarget.select()}
                  onChange={(e) => {
                    const raw = e.target.value;
                    const v = raw === '' ? 0 : Number(raw);
                    onChange(d.key, Number.isFinite(v) ? v : 0);
                  }}
                />

                <div className="text-right text-[11px] font-mono text-slate-400">
                  {showDerived ? fmtNumber(ppm, 1) : '—'}
                </div>
                <div className="text-right text-[11px] font-mono text-slate-400">
                  {showDerived ? fmtNumber(meqL, 3) : '—'}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
