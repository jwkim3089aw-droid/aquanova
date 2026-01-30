// ui\src\features\simulation\editors\GlobalEditors.tsx
import React, { useState, useEffect } from 'react';
import { Info, ArrowLeftRight, ChevronUp, ChevronDown } from 'lucide-react';

// ✅ [경로 수정 완료] components 폴더가 editors와 같은 레벨에 있음
import { Field, Input } from '../components/Common';
import {
  ChemistryInput,
  UnitKind,
  OLConfig,
  HRROConfig,
  UnitMode,
  convPress,
  unitLabel,
  ROConfig,
  NFConfig,
  UFConfig,
  MFConfig,
} from '../model/types';

// ==============================
// Feed chemistry card (Compact & Safe)
// ==============================

export function FeedChemistryCard({
  value,
  onChange,
}: {
  value: ChemistryInput;
  onChange: (patch: Partial<ChemistryInput>) => void;
}) {
  const v = value;
  return (
    // [Safety] 키보드 이벤트 전파 차단
    <div
      className="rounded-xl border border-slate-800 bg-slate-950/50 p-3 mt-2"
      onKeyDown={(e) => e.stopPropagation()}
    >
      <div className="flex items-center justify-between mb-2 pb-2 border-b border-slate-800/50">
        <div className="text-xs font-bold text-slate-200">
          Feed Chemistry{' '}
          <span className="text-slate-500 font-normal">(Optional)</span>
        </div>
        <div className="text-[10px] text-slate-500 flex items-center gap-1">
          <Info className="w-3 h-3" />
          <span>Used for scaling calc</span>
        </div>
      </div>
      <div className="grid grid-cols-2 gap-x-2 gap-y-3 text-xs">
        <Field label="Alkalinity (as CaCO₃)">
          <Input
            className="h-7 text-right bg-slate-900 border-slate-700 focus:border-blue-500"
            value={v.alkalinity_mgL_as_CaCO3 ?? ''}
            onChange={(e) =>
              onChange({
                alkalinity_mgL_as_CaCO3:
                  e.target.value === '' ? null : Number(e.target.value),
              })
            }
          />
        </Field>
        <Field label="Ca Hardness (as CaCO₃)">
          <Input
            className="h-7 text-right bg-slate-900 border-slate-700 focus:border-blue-500"
            value={v.calcium_hardness_mgL_as_CaCO3 ?? ''}
            onChange={(e) =>
              onChange({
                calcium_hardness_mgL_as_CaCO3:
                  e.target.value === '' ? null : Number(e.target.value),
              })
            }
          />
        </Field>
        <Field label="Sulfate (mg/L)">
          <Input
            className="h-7 text-right bg-slate-900 border-slate-700 focus:border-blue-500"
            value={v.sulfate_mgL ?? ''}
            onChange={(e) =>
              onChange({
                sulfate_mgL:
                  e.target.value === '' ? null : Number(e.target.value),
              })
            }
          />
        </Field>
        <Field label="Barium (mg/L)">
          <Input
            className="h-7 text-right bg-slate-900 border-slate-700 focus:border-blue-500"
            value={v.barium_mgL ?? ''}
            onChange={(e) =>
              onChange({
                barium_mgL:
                  e.target.value === '' ? null : Number(e.target.value),
              })
            }
          />
        </Field>
        <Field label="Strontium (mg/L)">
          <Input
            className="h-7 text-right bg-slate-900 border-slate-700 focus:border-blue-500"
            value={v.strontium_mgL ?? ''}
            onChange={(e) =>
              onChange({
                strontium_mgL:
                  e.target.value === '' ? null : Number(e.target.value),
              })
            }
          />
        </Field>
        <Field label="Silica (mg/L as SiO₂)">
          <Input
            className="h-7 text-right bg-slate-900 border-slate-700 focus:border-blue-500"
            value={v.silica_mgL_SiO2 ?? ''}
            onChange={(e) =>
              onChange({
                silica_mgL_SiO2:
                  e.target.value === '' ? null : Number(e.target.value),
              })
            }
          />
        </Field>
      </div>
    </div>
  );
}

// ==============================
// Stage list (Compact & Safe)
// ==============================

export function StageList({
  items,
  unitMode,
  onChangeItem,
  onMoveUp,
  onMoveDown,
  onBulk,
}: {
  items: {
    idx: number;
    id: string;
    kind: UnitKind;
    cfg: OLConfig | HRROConfig;
  }[];
  unitMode: UnitMode;
  onChangeItem: (id: string, cfg: OLConfig | HRROConfig) => void;
  onMoveUp: (id: string) => void;
  onMoveDown: (id: string) => void;
  onBulk: (mode: 'pressure' | 'recovery', value: number) => void;
}) {
  const [bulkMode, setBulkMode] = useState<'pressure' | 'recovery'>('pressure');
  const [bulkVal, setBulkVal] = useState<number>(16);

  useEffect(() => {
    setBulkVal(
      bulkMode === 'pressure'
        ? unitMode === 'SI'
          ? 16
          : convPress(16, 'SI', 'US')
        : 45,
    );
  }, [unitMode, bulkMode]);

  return (
    // [Safety] 키보드 이벤트 차단
    <div
      className="rounded-xl border border-slate-800 bg-slate-950/50 p-4 shadow-sm"
      onKeyDown={(e) => e.stopPropagation()}
    >
      <div className="flex items-center justify-between mb-3">
        <div className="text-sm font-bold text-slate-100">Stage Editor</div>
        <div className="text-[10px] text-slate-400 inline-flex items-center gap-1 bg-slate-900 px-2 py-0.5 rounded border border-slate-800">
          <ArrowLeftRight className="w-3 h-3" /> Bulk Edit
        </div>
      </div>

      <div className="mb-4 flex items-center gap-1 p-2 bg-slate-900/50 rounded-lg border border-slate-800">
        <select
          value={bulkMode}
          onChange={(e) =>
            setBulkMode(e.target.value as 'pressure' | 'recovery')
          }
          className="h-7 rounded border border-slate-700 bg-slate-800 px-2 text-slate-200 text-xs focus:outline-none focus:border-blue-500"
        >
          <option value="pressure">Pressure</option>
          <option value="recovery">Recovery</option>
        </select>
        <input
          className="h-7 w-20 rounded border border-slate-700 bg-slate-950 px-2 text-slate-100 text-xs text-right focus:outline-none focus:border-blue-500"
          type="number"
          step="any"
          value={bulkVal}
          onChange={(e) => setBulkVal(Number(e.target.value))}
          placeholder={
            bulkMode === 'pressure' ? unitLabel('press', unitMode) : '%'
          }
        />
        <button
          onClick={() => onBulk(bulkMode, bulkVal)}
          className="h-7 ml-auto px-3 rounded bg-blue-600 hover:bg-blue-500 text-white text-xs font-medium transition-colors"
        >
          Apply All
        </button>
      </div>

      <div className="space-y-2">
        {items.map((it, i) => (
          <div
            key={it.id}
            className="rounded border border-slate-800 bg-slate-900 p-2.5 hover:border-slate-600 transition-colors"
          >
            <div className="flex items-center justify-between mb-2">
              <div className="text-xs font-bold text-emerald-400">
                <span className="text-slate-500 mr-1">#{i + 1}</span> {it.kind}
              </div>
              <div className="flex items-center gap-0.5">
                <button
                  title="Move Up"
                  onClick={() => onMoveUp(it.id)}
                  className="p-1 rounded hover:bg-slate-700 text-slate-400 hover:text-white"
                >
                  <ChevronUp className="w-3 h-3" />
                </button>
                <button
                  title="Move Down"
                  onClick={() => onMoveDown(it.id)}
                  className="p-1 rounded hover:bg-slate-700 text-slate-400 hover:text-white"
                >
                  <ChevronDown className="w-3 h-3" />
                </button>
              </div>
            </div>

            {it.kind === 'HRRO'
              ? (() => {
                  const c = it.cfg as HRROConfig;
                  return (
                    <div className="grid grid-cols-2 gap-2 text-xs text-slate-100">
                      <Field label="Elements">
                        <Input
                          className="h-7 text-center bg-slate-950 border-slate-700"
                          value={c.elements}
                          onChange={(e) =>
                            onChangeItem(it.id, {
                              ...c,
                              elements: Number(e.target.value),
                            })
                          }
                        />
                      </Field>
                      <Field
                        label={`Set Press (${unitLabel('press', unitMode)})`}
                      >
                        <Input
                          className="h-7 text-center bg-slate-950 border-slate-700"
                          value={c.p_set_bar}
                          onChange={(e) =>
                            onChangeItem(it.id, {
                              ...c,
                              p_set_bar: Number(e.target.value),
                            })
                          }
                        />
                      </Field>
                    </div>
                  );
                })()
              : it.kind === 'UF'
                ? (() => {
                    const c = it.cfg as UFConfig;
                    return (
                      <div className="grid grid-cols-2 gap-2 text-xs text-slate-100">
                        <Field label="Elements">
                          <Input
                            className="h-7 text-center bg-slate-950 border-slate-700"
                            value={c.elements}
                            onChange={(e) =>
                              onChangeItem(it.id, {
                                ...c,
                                elements: Number(e.target.value),
                              } as OLConfig)
                            }
                          />
                        </Field>
                      </div>
                    );
                  })()
                : (() => {
                    const c = it.cfg as ROConfig | NFConfig | MFConfig;
                    return (
                      <div className="grid grid-cols-2 gap-2 text-xs text-slate-100">
                        <Field label="Elements">
                          <Input
                            className="h-7 text-center bg-slate-950 border-slate-700"
                            value={c.elements}
                            onChange={(e) =>
                              onChangeItem(it.id, {
                                ...c,
                                elements: Number(e.target.value),
                              } as OLConfig)
                            }
                          />
                        </Field>
                        <Field label="Mode">
                          <div className="flex items-center gap-2 h-7 px-1">
                            <label className="inline-flex items-center gap-1 cursor-pointer">
                              <input
                                type="radio"
                                className="text-blue-500 focus:ring-0 bg-slate-800 border-slate-600"
                                checked={c.mode === 'pressure'}
                                onChange={() =>
                                  onChangeItem(it.id, {
                                    ...c,
                                    mode: 'pressure',
                                  } as OLConfig)
                                }
                              />
                              Press
                            </label>
                            <label className="inline-flex items-center gap-1 cursor-pointer">
                              <input
                                type="radio"
                                className="text-blue-500 focus:ring-0 bg-slate-800 border-slate-600"
                                checked={c.mode === 'recovery'}
                                onChange={() =>
                                  onChangeItem(it.id, {
                                    ...c,
                                    mode: 'recovery',
                                  } as OLConfig)
                                }
                              />
                              Recov
                            </label>
                          </div>
                        </Field>
                        {c.mode === 'pressure' ? (
                          <Field
                            label={`Pressure (${unitLabel('press', unitMode)})`}
                          >
                            <Input
                              className="h-7 text-center bg-slate-950 border-slate-700 font-mono text-emerald-400"
                              value={c.pressure_bar ?? 16}
                              onChange={(e) =>
                                onChangeItem(it.id, {
                                  ...c,
                                  pressure_bar: Number(e.target.value),
                                } as OLConfig)
                              }
                            />
                          </Field>
                        ) : (
                          <Field label="Target Recovery (%)">
                            <Input
                              className="h-7 text-center bg-slate-950 border-slate-700 font-mono text-blue-400"
                              value={c.recovery_target_pct ?? 45}
                              onChange={(e) =>
                                onChangeItem(it.id, {
                                  ...c,
                                  recovery_target_pct: Number(e.target.value),
                                } as OLConfig)
                              }
                            />
                          </Field>
                        )}
                      </div>
                    );
                  })()}
          </div>
        ))}
      </div>
    </div>
  );
}
