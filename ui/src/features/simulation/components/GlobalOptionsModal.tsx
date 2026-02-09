// ui\src\features\simulation\components\GlobalOptionsModal.tsx
import React from 'react';

import { Field, Input } from '..';
import MembraneSelect from './MembraneSelect';
import { useBlockDeleteKeysWhenOpen } from '../hooks/useBlockDeleteKeysWhenOpen';

interface GlobalOptionsProps {
  isOpen: boolean;
  onClose: () => void;
  optAuto: boolean;
  setOptAuto: (v: boolean) => void;
  optMembrane: any;
  setOptMembrane: (v: any) => void;
  optSegments: number;
  setOptSegments: (v: number) => void;
  optPumpEff: number;
  setOptPumpEff: (v: number) => void;
  optErdEff: number;
  setOptErdEff: (v: number) => void;
  stageTypeHint: 'RO' | 'NF' | 'UF' | 'MF' | 'HRRO' | undefined;
}

export function GlobalOptionsModal(props: GlobalOptionsProps) {
  const {
    isOpen,
    onClose,
    optAuto,
    setOptAuto,
    optMembrane,
    setOptMembrane,
    optSegments,
    setOptSegments,
    optPumpEff,
    setOptPumpEff,
    optErdEff,
    setOptErdEff,
    stageTypeHint,
  } = props;

  useBlockDeleteKeysWhenOpen(isOpen);

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-[2px]"
      onClick={onClose}
    >
      <div
        className="w-full max-w-md rounded-xl border border-slate-700 bg-slate-950 p-0 shadow-2xl overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-5 py-3 border-b border-slate-800 bg-slate-900/50">
          <h2 className="text-sm font-bold text-slate-100 uppercase tracking-wide">
            Global Project Options
          </h2>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-white transition-colors"
          >
            ✕
          </button>
        </div>

        <div className="p-5 space-y-5">
          <div className="flex items-center gap-3 p-3 bg-blue-900/10 border border-blue-900/30 rounded-lg">
            <label className="flex items-center gap-3 w-full cursor-pointer">
              <input
                type="checkbox"
                className="w-4 h-4 rounded border-slate-600 bg-slate-800 text-blue-600 focus:ring-offset-0 focus:ring-0"
                checked={optAuto}
                onChange={(e) => setOptAuto(e.target.checked)}
              />
              <div className="flex flex-col">
                <span className="text-sm font-bold text-blue-100">
                  Auto-Configuration Mode
                </span>
                <span className="text-[10px] text-blue-300/70">
                  Automatically calculate element quantity based on flow
                </span>
              </div>
            </label>
          </div>

          <div className="space-y-4">
            <div>
              <label className="block text-[10px] font-bold text-slate-400 uppercase mb-1.5">
                Default Membrane Model
              </label>
              <MembraneSelect
                unitType={stageTypeHint || 'RO'}
                mode="catalog"
                model={
                  typeof optMembrane === 'string'
                    ? optMembrane
                    : optMembrane?.membrane_model
                }
                onChange={(v) => setOptMembrane(v)}
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <Field label="Elements per Vessel">
                <Input
                  disabled={optAuto}
                  className="text-center"
                  value={optSegments}
                  onChange={(e) => setOptSegments(Number(e.target.value))}
                />
              </Field>
              <div className="col-span-1" />
              <Field label="Pump Efficiency (0-1)">
                <Input
                  disabled={optAuto}
                  className="text-center"
                  value={optPumpEff}
                  step={0.01}
                  onChange={(e) => setOptPumpEff(Number(e.target.value))}
                />
              </Field>
              <Field label="ERD Efficiency (0-1)">
                <Input
                  disabled={optAuto}
                  className="text-center"
                  value={optErdEff}
                  step={0.01}
                  onChange={(e) => setOptErdEff(Number(e.target.value))}
                />
              </Field>
            </div>
          </div>
        </div>

        <div className="px-5 py-3 bg-slate-900/30 border-t border-slate-800 flex justify-end">
          <button
            onClick={onClose}
            className="px-5 py-1.5 bg-slate-100 hover:bg-white text-slate-900 rounded-md text-xs font-bold transition-colors shadow-lg"
          >
            Save & Close
          </button>
        </div>
      </div>
    </div>
  );
}
