// ui/src/features/simulation/components/GlobalOptionsModal.tsx
import React from 'react';
import { Field, Input } from '..';
import { useBlockDeleteKeysWhenOpen } from '../hooks/useBlockDeleteKeysWhenOpen';
import { OpexState } from '../model/types';

interface GlobalOptionsProps {
  isOpen: boolean;
  onClose: () => void;
  optSegments: number;
  setOptSegments: (v: number) => void;
  optPumpEff: number;
  setOptPumpEff: (v: number) => void;
  optErdEff: number;
  setOptErdEff: (v: number) => void;
  opexConfig: OpexState;
  setOpexConfig: (v: OpexState) => void;
}

export function GlobalOptionsModal(props: GlobalOptionsProps) {
  const {
    isOpen,
    onClose,
    optSegments,
    setOptSegments,
    optPumpEff,
    setOptPumpEff,
    optErdEff,
    setOptErdEff,
    opexConfig,
    setOpexConfig,
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
            글로벌 프로젝트 옵션
          </h2>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-white transition-colors"
          >
            ✕
          </button>
        </div>

        <div className="p-5 space-y-6 max-h-[75vh] overflow-y-auto">
          {/* 시스템 공통 설정 */}
          <div className="space-y-4">
            <h3 className="text-xs font-bold text-slate-500 uppercase tracking-wider">
              시스템 기본 변수
            </h3>
            <div className="grid grid-cols-2 gap-4">
              <Field label="베셀 당 엘리먼트 수">
                <Input
                  className="text-center"
                  value={optSegments}
                  onChange={(e) => setOptSegments(Number(e.target.value))}
                />
              </Field>
              <div className="col-span-1" />
              <Field label="펌프 효율 (0~1)">
                <Input
                  className="text-center"
                  value={optPumpEff}
                  step={0.01}
                  onChange={(e) => setOptPumpEff(Number(e.target.value))}
                />
              </Field>
              <Field label="ERD 효율 (0~1)">
                <Input
                  className="text-center"
                  value={optErdEff}
                  step={0.01}
                  onChange={(e) => setOptErdEff(Number(e.target.value))}
                />
              </Field>
            </div>
          </div>

          {/* OPEX 단가 설정 */}
          <div className="space-y-4 pt-4 border-t border-slate-800">
            <h3 className="text-xs font-bold text-slate-500 uppercase tracking-wider flex items-center gap-2">
              <span className="text-emerald-400">💰</span> 운영비(OPEX) 단가
              설정
            </h3>
            <div className="grid grid-cols-2 gap-4">
              <Field label="전력 단가 ($/kWh)">
                <Input
                  type="number"
                  step="0.01"
                  className="text-right tabular-nums"
                  value={opexConfig.electricity_price_kwh}
                  onChange={(e) =>
                    setOpexConfig({
                      ...opexConfig,
                      electricity_price_kwh: Number(e.target.value),
                    })
                  }
                />
              </Field>
              <Field label="스케일 방지제 단가 ($/kg)">
                <Input
                  type="number"
                  step="0.1"
                  className="text-right tabular-nums"
                  value={opexConfig.antiscalant_price_kg}
                  onChange={(e) =>
                    setOpexConfig({
                      ...opexConfig,
                      antiscalant_price_kg: Number(e.target.value),
                    })
                  }
                />
              </Field>
              <Field label="산/염기 단가 ($/kg)">
                <Input
                  type="number"
                  step="0.1"
                  className="text-right tabular-nums"
                  value={opexConfig.acid_base_price_kg}
                  onChange={(e) =>
                    setOpexConfig({
                      ...opexConfig,
                      acid_base_price_kg: Number(e.target.value),
                    })
                  }
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
            저장 및 닫기
          </button>
        </div>
      </div>
    </div>
  );
}
