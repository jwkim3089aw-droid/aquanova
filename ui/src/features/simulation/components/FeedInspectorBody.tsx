// ui/src/features/simulation/components/FeedInspectorBody.tsx
import React from 'react';

import { Field, Input } from '..';
import { WATER_CATALOG } from '../data/water_catalog';

import { UnitMode, clampf, unitLabel } from '../model/types';

import { IonTable } from './IonTable';

import {
  CATIONS,
  ANIONS,
  NEUTRALS,
  fmtNumber,
  type ChargeBalanceMode,
} from '../chemistry';

import { useFeedPreset } from '../hooks/useFeedPreset';
import { useSaltQuickEntry, type QuickState } from '../hooks/useSaltQuickEntry';
import { useChargeBalanceActions } from '../hooks/useChargeBalanceActions';
import type { FeedDerived } from '../hooks/useFeedChargeBalance';

interface FeedInspectorBodyProps {
  localFeed: any;
  setLocalFeed: React.Dispatch<React.SetStateAction<any>>;

  localChem: any;
  setLocalChem: React.Dispatch<React.SetStateAction<any>>;

  quick: QuickState;
  setQuick: React.Dispatch<React.SetStateAction<QuickState>>;

  detailsOpen: boolean;
  setDetailsOpen: React.Dispatch<React.SetStateAction<boolean>>;

  cbMode: ChargeBalanceMode;
  setCbMode: React.Dispatch<React.SetStateAction<ChargeBalanceMode>>;

  unitMode: UnitMode;
  compact: boolean;

  derived: FeedDerived;
}

export function FeedInspectorBody(props: FeedInspectorBodyProps) {
  const {
    localFeed,
    setLocalFeed,
    localChem,
    setLocalChem,
    quick,
    setQuick,
    detailsOpen,
    setDetailsOpen,
    cbMode,
    setCbMode,
    unitMode,
    compact,
    derived,
  } = props;

  const { waterTypeOptions, subtypeSuggestions, applyPreset } = useFeedPreset(
    localFeed,
    setLocalFeed,
    setLocalChem,
  );

  const { applyQuickEntry } = useSaltQuickEntry(quick, setQuick, setLocalChem);

  const { cbModeLabel, applyBalanceIntoTable } = useChargeBalanceActions(
    localChem,
    cbMode,
    setLocalChem,
  );

  return (
    <div className={compact ? 'space-y-3' : 'space-y-4'}>
      {/* Top */}
      <div className="grid grid-cols-12 gap-4">
        <div className="col-span-12 lg:col-span-7 p-3 bg-slate-900/40 border border-slate-800 rounded-lg">
          <label className="text-[10px] font-bold text-blue-400 mb-2 uppercase tracking-wider block">
            프리셋 라이브러리
          </label>

          <select
            className="w-full bg-slate-950 border border-slate-700 rounded px-2 py-2 text-xs text-slate-200 focus:outline-none focus:border-blue-500 cursor-pointer"
            onChange={(e) => applyPreset(e.target.value)}
            defaultValue=""
          >
            <option value="" disabled>
              -- 물 조성 선택 --
            </option>

            <optgroup label="해수">
              {WATER_CATALOG.filter((w) => w.category === 'Seawater').map(
                (w) => (
                  <option key={w.id} value={w.id}>
                    {w.name}
                  </option>
                ),
              )}
            </optgroup>

            <optgroup label="기수/지하수">
              {WATER_CATALOG.filter((w) => w.category === 'Brackish').map(
                (w) => (
                  <option key={w.id} value={w.id}>
                    {w.name}
                  </option>
                ),
              )}
            </optgroup>

            <optgroup label="지표수(강/호수)">
              {WATER_CATALOG.filter((w) => w.category === 'Surface').map(
                (w) => (
                  <option key={w.id} value={w.id}>
                    {w.name}
                  </option>
                ),
              )}
            </optgroup>

            <optgroup label="폐수(산업/공정)">
              {WATER_CATALOG.filter((w) => w.category === 'Waste').map((w) => (
                <option key={w.id} value={w.id}>
                  {w.name}
                </option>
              ))}
            </optgroup>

            <optgroup label="재이용수(하수처리수)">
              {WATER_CATALOG.filter((w) => w.category === 'Reuse').map((w) => (
                <option key={w.id} value={w.id}>
                  {w.name}
                </option>
              ))}
            </optgroup>
          </select>

          <div className="mt-3 grid grid-cols-12 gap-3">
            <div className="col-span-12 md:col-span-4">
              <label className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block mb-1">
                원수 분류
              </label>
              <select
                className="w-full h-9 bg-slate-950 border border-slate-700 rounded px-2 text-xs text-slate-200 focus:outline-none focus:border-blue-500"
                value={String(localFeed.water_type ?? '')}
                onChange={(e) =>
                  setLocalFeed({ ...localFeed, water_type: e.target.value })
                }
              >
                <option value="">(선택)</option>
                {waterTypeOptions.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
            </div>

            <div className="col-span-12 md:col-span-8">
              <label className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block mb-1">
                원수 세부 분류(출처)
              </label>
              <input
                type="text"
                list="water-subtype-suggestions"
                className="w-full h-9 bg-slate-950 border border-slate-700 rounded px-2 text-xs text-slate-200 focus:outline-none focus:border-blue-500"
                value={String(localFeed.water_subtype ?? '')}
                placeholder="예: 태평양 평균 / 아라비아만 / 냉각탑 블로다운 ..."
                onChange={(e) =>
                  setLocalFeed({ ...localFeed, water_subtype: e.target.value })
                }
              />
              <datalist id="water-subtype-suggestions">
                {subtypeSuggestions.map((s) => (
                  <option key={s} value={s} />
                ))}
              </datalist>
            </div>
          </div>

          <div className="mt-3">
            <label className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block mb-1">
              추가 정보(메모)
            </label>
            <textarea
              className="w-full h-16 bg-slate-950 border border-slate-700 rounded px-2 py-2 text-xs text-slate-200 focus:outline-none focus:border-blue-500"
              value={localFeed.feed_note ?? ''}
              placeholder="(선택) 원수 특이사항/전처리/샘플링 정보 등"
              onChange={(e) =>
                setLocalFeed({ ...localFeed, feed_note: e.target.value })
              }
            />
          </div>
        </div>

        <div className="col-span-12 lg:col-span-5 p-3 bg-slate-900/40 border border-slate-800 rounded-lg">
          <div className="grid grid-cols-2 gap-3">
            <Field label={`온도 (${unitLabel('temp', unitMode)})`}>
              <Input
                className="h-9 text-center font-mono"
                value={localFeed.temperature_C}
                onChange={(e) =>
                  setLocalFeed({
                    ...localFeed,
                    temperature_C: Number(e.target.value),
                  })
                }
              />
            </Field>

            <Field label="pH (@25°C)">
              <Input
                className="h-9 text-center font-mono"
                value={localFeed.ph}
                min={0}
                max={14}
                onChange={(e) =>
                  setLocalFeed({
                    ...localFeed,
                    ph: clampf(Number(e.target.value), 0, 14),
                  })
                }
              />
            </Field>

            <div className="col-span-2">
              <Field label={`유입 유량 (${unitLabel('flow', unitMode)})`}>
                <Input
                  className="h-9 font-bold text-emerald-400 text-right font-mono"
                  value={localFeed.flow_m3h}
                  onChange={(e) =>
                    setLocalFeed({
                      ...localFeed,
                      flow_m3h: Number(e.target.value),
                    })
                  }
                />
              </Field>
            </div>
          </div>

          {/* Quick entry */}
          <div className="mt-3 pt-3 border-t border-slate-800/80">
            <div className="flex items-center justify-between mb-2">
              <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">
                빠른 입력(염 혼합)
              </div>
              <div className="text-[10px] text-slate-500">
                입력값을 이온으로 분해
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <Field label="NaCl (mg/L)">
                <Input
                  className="h-9 text-right font-mono"
                  value={quick.nacl_mgL}
                  onChange={(e) =>
                    setQuick({ ...quick, nacl_mgL: Number(e.target.value) })
                  }
                />
              </Field>

              <Field label="MgSO4 (mg/L)">
                <Input
                  className="h-9 text-right font-mono"
                  value={quick.mgso4_mgL}
                  onChange={(e) =>
                    setQuick({ ...quick, mgso4_mgL: Number(e.target.value) })
                  }
                />
              </Field>

              <div className="col-span-2 flex justify-end">
                <button
                  onClick={applyQuickEntry}
                  className="px-3 py-2 rounded text-xs font-bold text-white bg-slate-700 hover:bg-slate-600 border border-slate-600"
                >
                  이온에 반영
                </button>
              </div>
            </div>
          </div>

          {/* Charge balance */}
          <div className="mt-3 pt-3 border-t border-slate-800/80">
            <div className="flex items-center justify-between mb-2">
              <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">
                전하 밸런스 보정(WAVE)
              </div>
              <div className="text-[10px] text-slate-500">
                C≈A 되도록 자동 보정
              </div>
            </div>

            <div className="grid grid-cols-12 gap-2 items-center">
              <div className="col-span-8">
                <select
                  className="w-full h-9 bg-slate-950 border border-slate-700 rounded px-2 text-xs text-slate-200 focus:outline-none focus:border-blue-500"
                  value={cbMode}
                  onChange={(e) =>
                    setCbMode(e.target.value as ChargeBalanceMode)
                  }
                >
                  <option value="off">OFF(원본 그대로)</option>
                  <option value="anions">Anions(Cl 우선)</option>
                  <option value="cations">Cations(Na 우선)</option>
                  <option value="all">All(양·음이온 스케일)</option>
                </select>
              </div>

              <div className="col-span-4 flex justify-end">
                <button
                  onClick={applyBalanceIntoTable}
                  disabled={cbMode === 'off'}
                  className={`px-3 py-2 rounded text-xs font-bold border ${
                    cbMode === 'off'
                      ? 'text-slate-500 bg-slate-900/30 border-slate-800 cursor-not-allowed'
                      : 'text-white bg-slate-700 hover:bg-slate-600 border-slate-600'
                  }`}
                  title="WAVE처럼 이온표 숫자 자체를 보정값으로 덮어씁니다."
                >
                  표에 반영
                </button>
              </div>

              <div className="col-span-12 text-[10px] text-slate-500">
                모드:{' '}
                <span className="text-slate-200 font-semibold">
                  {cbModeLabel[cbMode]}
                </span>
                {' · '} 원본 Δ(C-A):{' '}
                <span className="font-mono text-slate-300">
                  {fmtNumber(derived.rawChargeBalance_meqL, 3)}
                </span>{' '}
                meq/L {' → '} 보정 Δ(C-A):{' '}
                <span className="font-mono text-emerald-300">
                  {fmtNumber(derived.chargeBalance_meqL, 3)}
                </span>{' '}
                meq/L
              </div>

              {derived.adjustmentText && (
                <div className="col-span-12 text-[10px] text-slate-500">
                  보정내용(상위):{' '}
                  <span className="text-slate-300 font-mono">
                    {derived.adjustmentText}
                  </span>
                </div>
              )}

              {derived.cbNote && (
                <div className="col-span-12 text-[10px] text-amber-300/80">
                  {derived.cbNote}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* KPI */}
      <div className="grid grid-cols-12 gap-3">
        <div className="col-span-12 md:col-span-4 bg-slate-900/55 border border-slate-800 rounded-lg p-3">
          <div className="text-[10px] font-bold text-slate-500 uppercase">
            TDS {cbMode !== 'off' ? '(보정 적용)' : ''}
          </div>
          <div className="text-xl font-mono text-emerald-400 font-bold">
            {fmtNumber(derived.totalTDS, 1)}{' '}
            <span className="text-xs font-normal text-slate-600">mg/L</span>
          </div>
          {cbMode !== 'off' && (
            <div className="text-[10px] text-slate-500 mt-1">
              원본:{' '}
              <span className="font-mono">
                {fmtNumber(derived.rawTotalTDS, 1)}
              </span>{' '}
              mg/L
            </div>
          )}
        </div>

        <div className="col-span-12 md:col-span-4 bg-slate-900/55 border border-slate-800 rounded-lg p-3">
          <div className="text-[10px] font-bold text-slate-500 uppercase">
            경도(Hardness)
          </div>
          <div className="text-xl font-mono text-blue-300 font-semibold">
            {fmtNumber(derived.calcHardness, 1)}{' '}
            <span className="text-xs font-normal text-slate-600">as CaCO3</span>
          </div>
        </div>

        <div className="col-span-12 md:col-span-4 bg-slate-900/55 border border-slate-800 rounded-lg p-3">
          <div className="text-[10px] font-bold text-slate-500 uppercase">
            알칼리도(Alkalinity)
          </div>
          <div className="text-xl font-mono text-blue-300 font-semibold">
            {fmtNumber(derived.calcAlkalinity, 1)}{' '}
            <span className="text-xs font-normal text-slate-600">as CaCO3</span>
          </div>
        </div>

        <div className="col-span-12 grid grid-cols-3 gap-3">
          <div className="bg-slate-900/35 border border-slate-800 rounded-lg p-3">
            <div className="text-[10px] text-slate-500 uppercase">
              전하 밸런스
            </div>
            <div className="text-sm font-mono text-slate-200">
              {fmtNumber(derived.chargeBalance_meqL, 3)}{' '}
              <span className="text-slate-500">meq/L</span>
            </div>
            {cbMode !== 'off' && (
              <div className="text-[10px] text-slate-500 mt-1">
                원본:{' '}
                <span className="font-mono">
                  {fmtNumber(derived.rawChargeBalance_meqL, 3)}
                </span>{' '}
                meq/L
              </div>
            )}
          </div>

          <div className="bg-slate-900/35 border border-slate-800 rounded-lg p-3">
            <div className="text-[10px] text-slate-500 uppercase">
              전도도(추정)
            </div>
            <div className="text-sm font-mono text-slate-200">
              {fmtNumber(derived.estConductivity_uScm, 0)}{' '}
              <span className="text-slate-500">µS/cm</span>
            </div>
          </div>

          <div className="bg-slate-900/35 border border-slate-800 rounded-lg p-3">
            <div className="text-[10px] text-slate-500 uppercase">meq/L 합</div>
            <div className="text-sm font-mono text-slate-200">
              C {fmtNumber(derived.cationMeq, 3)} / A{' '}
              {fmtNumber(derived.anionMeq, 3)}
            </div>
            {cbMode !== 'off' && (
              <div className="text-[10px] text-slate-500 mt-1">
                원본: C{' '}
                <span className="font-mono">
                  {fmtNumber(derived.rawCationMeq, 3)}
                </span>{' '}
                / A{' '}
                <span className="font-mono">
                  {fmtNumber(derived.rawAnionMeq, 3)}
                </span>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Ions */}
      <div className="pt-1">
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-xs font-bold text-slate-300 flex items-center gap-2">
            <span className="w-1 h-4 bg-blue-500 rounded-sm" />
            이온 조성 입력(전체)
          </h3>
          <div className="text-[10px] text-slate-500">
            mg/L 입력 → ppm(CaCO3)/meq/L 자동 계산
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
          <IonTable
            title="CATIONS (+)"
            defs={CATIONS}
            chem={localChem}
            accent="text-blue-300"
            onChange={(k, v) => setLocalChem({ ...localChem, [k]: v })}
            showDerived
            compact={compact}
          />
          <IonTable
            title="ANIONS (-)"
            defs={ANIONS}
            chem={localChem}
            accent="text-rose-300"
            onChange={(k, v) => setLocalChem({ ...localChem, [k]: v })}
            showDerived
            compact={compact}
          />
          <IonTable
            title="NEUTRALS"
            defs={NEUTRALS}
            chem={localChem}
            accent="text-emerald-300"
            onChange={(k, v) => setLocalChem({ ...localChem, [k]: v })}
            showDerived={false}
            compact={compact}
          />
        </div>
      </div>

      {/* Details */}
      <div className="pt-2">
        <div className="flex items-center justify-between">
          <h3 className="text-xs font-bold text-slate-300 flex items-center gap-2">
            <span className="w-1 h-4 bg-slate-500 rounded-sm" />
            상세 입력 (필요할 때만 펼치기)
          </h3>
          <button
            onClick={() => setDetailsOpen((v) => !v)}
            className="px-3 py-1.5 rounded text-xs font-bold text-slate-200 bg-slate-800 border border-slate-700 hover:bg-slate-700"
          >
            {detailsOpen ? '접기' : '펼치기'}
          </button>
        </div>

        {detailsOpen && (
          <div className="mt-3 grid grid-cols-12 gap-4">
            <div className="col-span-12 lg:col-span-8 p-3 bg-slate-900/30 border border-slate-800 rounded-lg">
              <div className="grid grid-cols-12 gap-3">
                <div className="col-span-12 md:col-span-4">
                  <Field label="최저 온도 (°C)">
                    <Input
                      className="h-9 text-right font-mono"
                      value={localFeed.temp_min_C ?? ''}
                      onChange={(e) =>
                        setLocalFeed({
                          ...localFeed,
                          temp_min_C: Number(e.target.value),
                        })
                      }
                    />
                  </Field>
                </div>
                <div className="col-span-12 md:col-span-4">
                  <Field label="설계 온도 (°C)">
                    <Input
                      className="h-9 text-right font-mono"
                      value={localFeed.temperature_C ?? ''}
                      onChange={(e) =>
                        setLocalFeed({
                          ...localFeed,
                          temperature_C: Number(e.target.value),
                        })
                      }
                    />
                  </Field>
                </div>
                <div className="col-span-12 md:col-span-4">
                  <Field label="최고 온도 (°C)">
                    <Input
                      className="h-9 text-right font-mono"
                      value={localFeed.temp_max_C ?? ''}
                      onChange={(e) =>
                        setLocalFeed({
                          ...localFeed,
                          temp_max_C: Number(e.target.value),
                        })
                      }
                    />
                  </Field>
                </div>
              </div>
            </div>

            <div className="col-span-12 lg:col-span-4 p-3 bg-slate-900/30 border border-slate-800 rounded-lg">
              <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-2">
                고형물/유기물(참고)
              </div>
              <div className="grid grid-cols-2 gap-2">
                <Field label="탁도 (NTU)">
                  <Input
                    className="h-9 text-right font-mono"
                    value={localFeed.turbidity_ntu ?? ''}
                    onChange={(e) =>
                      setLocalFeed({
                        ...localFeed,
                        turbidity_ntu: Number(e.target.value),
                      })
                    }
                  />
                </Field>
                <Field label="TSS (mg/L)">
                  <Input
                    className="h-9 text-right font-mono"
                    value={localFeed.tss_mgL ?? ''}
                    onChange={(e) =>
                      setLocalFeed({
                        ...localFeed,
                        tss_mgL: Number(e.target.value),
                      })
                    }
                  />
                </Field>
                <Field label="SDI15">
                  <Input
                    className="h-9 text-right font-mono"
                    value={localFeed.sdi15 ?? ''}
                    onChange={(e) =>
                      setLocalFeed({
                        ...localFeed,
                        sdi15: Number(e.target.value),
                      })
                    }
                  />
                </Field>
                <Field label="TOC (mg/L)">
                  <Input
                    className="h-9 text-right font-mono"
                    value={localFeed.toc_mgL ?? ''}
                    onChange={(e) =>
                      setLocalFeed({
                        ...localFeed,
                        toc_mgL: Number(e.target.value),
                      })
                    }
                  />
                </Field>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
