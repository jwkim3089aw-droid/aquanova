// ui/src/features/simulation/editors/UnitForms/PumpSection.tsx

import React from 'react';
import { Field, Input } from '../../components/Common';
import { BaseMembraneConfig } from '../../model/types';
import { GROUP_CLS, INPUT_CLS } from './utils';

export function PumpSection({
  cfg,
  onChange,
  defaultPressure,
}: {
  cfg: BaseMembraneConfig;
  onChange: (patch: Partial<BaseMembraneConfig>) => void;
  defaultPressure: number;
}) {
  const isEnabled = cfg.enable_pump ?? true;

  return (
    <div
      className={`${GROUP_CLS} border-emerald-900/30 bg-emerald-900/10 !mb-0 shrink-0`}
    >
      <div className="flex items-center justify-between mb-1.5 pb-1 border-b border-emerald-900/20">
        <h4 className="text-[11px] font-bold text-emerald-400 flex items-center gap-1.5 uppercase tracking-wide">
          ⚡ 고압 펌프 (HP Pump)
        </h4>
        <label className="flex items-center gap-1.5 cursor-pointer select-none hover:bg-emerald-900/20 px-1.5 py-0.5 rounded transition-colors">
          <input
            type="checkbox"
            checked={isEnabled}
            onChange={(e) => onChange({ enable_pump: e.target.checked })}
            className="w-3 h-3 rounded border-slate-600 bg-slate-800 text-emerald-500 focus:ring-0"
          />
          <span className="text-[10px] font-bold text-slate-300">
            {isEnabled ? '사용 (On)' : '우회 (Bypass)'}
          </span>
        </label>
      </div>

      {isEnabled && (
        <div className="grid grid-cols-2 gap-3 mt-2">
          <Field label="목표 압력 (Target Pressure)">
            <div className="flex items-center gap-1.5">
              <Input
                type="number"
                step={0.1}
                value={cfg.pump_pressure_bar ?? defaultPressure}
                onChange={(e) =>
                  onChange({ pump_pressure_bar: Number(e.target.value) })
                }
                className={`${INPUT_CLS} text-emerald-400 font-bold bg-emerald-950/40 border-emerald-800/50`}
              />
              <span className="text-[10px] text-slate-500 w-6">bar</span>
            </div>
          </Field>
          <Field label="펌프 효율 (Efficiency)">
            <div className="flex items-center gap-1.5">
              <Input
                type="number"
                step={1}
                min={1}
                max={100}
                value={cfg.pump_efficiency_pct ?? 75}
                onChange={(e) =>
                  onChange({ pump_efficiency_pct: Number(e.target.value) })
                }
                className={INPUT_CLS}
              />
              <span className="text-[10px] text-slate-500 w-6">%</span>
            </div>
          </Field>
        </div>
      )}
    </div>
  );
}
