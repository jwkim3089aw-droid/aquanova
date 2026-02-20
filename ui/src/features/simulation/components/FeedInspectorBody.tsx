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

// 헬퍼 함수
function num0(s: string): number {
  if (s.trim() === '') return 0;
  const n = Number(s);
  return Number.isFinite(n) ? n : 0;
}
function numOrNull(s: string): number | null {
  if (s.trim() === '') return null;
  const n = Number(s);
  return Number.isFinite(n) ? n : null;
}

// 카드 스타일
const Card = ({ children, title, className = '' }: any) => (
  <div
    className={`bg-slate-900/40 border border-slate-800/60 rounded-lg p-2 ${className}`}
  >
    {title && (
      <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-2">
        {title}
      </div>
    )}
    {children}
  </div>
);

export function FeedInspectorBody(props: any) {
  const {
    localFeed,
    setLocalFeed,
    localChem,
    setLocalChem,
    quick,
    setQuick,
    cbMode,
    setCbMode,
    unitMode,
    derived,
  } = props;

  const { waterTypeOptions, subtypeSuggestions, applyPreset } = useFeedPreset(
    localFeed,
    setLocalFeed,
    setLocalChem,
  );

  const { applyQuickEntry } = useSaltQuickEntry(quick, setQuick, setLocalChem);
  const { applyBalanceIntoTable } = useChargeBalanceActions(
    localChem,
    cbMode,
    setLocalChem,
  );

  return (
    <div className="h-full w-full grid grid-cols-12 gap-3">
      {/* 🔴 [LEFT COLUMN] 설정 영역: WAVE 레이아웃 적용 */}
      <div className="col-span-12 xl:col-span-4 flex flex-col gap-2 h-full overflow-y-auto custom-scrollbar pr-1">
        {/* 프리셋 로더 (상단 고정) */}
        <select
          className="w-full bg-slate-950 border border-slate-700 rounded px-2 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-blue-500 shrink-0"
          onChange={(e) => applyPreset(e.target.value)}
          defaultValue=""
        >
          <option value="" disabled>
            -- 프리셋 불러오기 --
          </option>
          <optgroup label="해수">
            {WATER_CATALOG.filter((w) => w.category === 'Seawater').map((w) => (
              <option key={w.id} value={w.id}>
                {w.name}
              </option>
            ))}
          </optgroup>
          <optgroup label="기수/지하수/기타">
            {WATER_CATALOG.filter((w) => w.category !== 'Seawater').map((w) => (
              <option key={w.id} value={w.id}>
                {w.name}
              </option>
            ))}
          </optgroup>
        </select>

        {/* 1. Feed Parameters (WAVE 좌측 상단) */}
        <Card title="Feed Parameters" className="shrink-0">
          <div className="flex flex-col gap-2">
            <div className="flex items-center gap-2">
              <span className="text-[10px] text-slate-500 w-20">
                Water Type:
              </span>
              <select
                className="flex-1 h-7 bg-slate-950 border border-slate-700 rounded px-1 text-xs text-slate-200"
                value={String(localFeed.water_type ?? '')}
                onChange={(e) =>
                  setLocalFeed((p: any) => ({
                    ...p,
                    water_type: e.target.value,
                  }))
                }
              >
                <option value="">Select Type...</option>
                {waterTypeOptions.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-[10px] text-slate-500 w-20">Sub-type:</span>
              <input
                type="text"
                list="water-subtype-suggestions"
                className="flex-1 h-7 bg-slate-950 border border-slate-700 rounded px-2 text-xs text-slate-200"
                value={String(localFeed.water_subtype ?? '')}
                onChange={(e) =>
                  setLocalFeed((p: any) => ({
                    ...p,
                    water_subtype: e.target.value,
                  }))
                }
              />
              <datalist id="water-subtype-suggestions">
                {subtypeSuggestions.map((s) => (
                  <option key={s} value={s} />
                ))}
              </datalist>
            </div>
            <div className="flex gap-2 mt-1">
              <div className="flex-1">
                <div className="text-[9px] text-slate-500 mb-0.5">
                  Flow ({unitLabel('flow', unitMode)})
                </div>
                <Input
                  className="h-6 w-full font-bold text-emerald-400 text-center font-mono text-xs"
                  value={localFeed.flow_m3h}
                  onChange={(e) =>
                    setLocalFeed((p: any) => ({
                      ...p,
                      flow_m3h: num0(e.target.value),
                    }))
                  }
                />
              </div>
              <div className="flex-1">
                <div className="text-[9px] text-slate-500 mb-0.5">pH @25°C</div>
                <Input
                  className="h-6 w-full text-center font-mono text-xs"
                  value={localFeed.ph}
                  onChange={(e) =>
                    setLocalFeed((p: any) => ({
                      ...p,
                      ph: clampf(num0(e.target.value), 0, 14),
                    }))
                  }
                />
              </div>
            </div>
          </div>
        </Card>

        {/* 2. Temperature (WAVE 우측 상단 - 3칸 분할) */}
        <Card
          title={`Temperature (${unitLabel('temp', unitMode)})`}
          className="shrink-0 bg-slate-800/30"
        >
          <div className="flex gap-2">
            <div className="flex-1">
              <div className="text-[9px] text-slate-500 text-center mb-0.5">
                Minimum
              </div>
              <Input
                className="h-7 w-full text-center font-mono text-xs"
                value={localFeed.temp_min_C ?? ''}
                placeholder="-"
                onChange={(e) =>
                  setLocalFeed((p: any) => ({
                    ...p,
                    temp_min_C: numOrNull(e.target.value),
                  }))
                }
              />
            </div>
            <div className="flex-1">
              <div className="text-[9px] text-slate-500 text-center mb-0.5">
                Design
              </div>
              <Input
                className="h-7 w-full text-center font-mono text-xs border-blue-500/50"
                value={localFeed.temperature_C}
                onChange={(e) =>
                  setLocalFeed((p: any) => ({
                    ...p,
                    temperature_C: num0(e.target.value),
                  }))
                }
              />
            </div>
            <div className="flex-1">
              <div className="text-[9px] text-slate-500 text-center mb-0.5">
                Maximum
              </div>
              <Input
                className="h-7 w-full text-center font-mono text-xs"
                value={localFeed.temp_max_C ?? ''}
                placeholder="-"
                onChange={(e) =>
                  setLocalFeed((p: any) => ({
                    ...p,
                    temp_max_C: numOrNull(e.target.value),
                  }))
                }
              />
            </div>
          </div>
        </Card>

        {/* 3. Solid & Organic Content (WAVE 중앙 - 항상 노출) */}
        <Card title="Solid & Organic Content" className="shrink-0">
          <div className="grid grid-cols-2 gap-x-4 gap-y-2">
            <div className="flex items-center justify-between">
              <span className="text-[10px] text-slate-500">
                Turbidity (NTU)
              </span>
              <Input
                className="h-6 w-14 text-right font-mono text-xs"
                value={localFeed.turbidity_ntu ?? ''}
                onChange={(e) =>
                  setLocalFeed((p: any) => ({
                    ...p,
                    turbidity_ntu: numOrNull(e.target.value),
                  }))
                }
              />
            </div>
            <div className="flex items-center justify-between">
              <span className="text-[10px] text-slate-500">TSS (mg/L)</span>
              <Input
                className="h-6 w-14 text-right font-mono text-xs"
                value={localFeed.tss_mgL ?? ''}
                onChange={(e) =>
                  setLocalFeed((p: any) => ({
                    ...p,
                    tss_mgL: numOrNull(e.target.value),
                  }))
                }
              />
            </div>
            <div className="flex items-center justify-between">
              <span className="text-[10px] text-slate-500">SDI 15</span>
              <Input
                className="h-6 w-14 text-right font-mono text-xs"
                value={localFeed.sdi15 ?? ''}
                onChange={(e) =>
                  setLocalFeed((p: any) => ({
                    ...p,
                    sdi15: numOrNull(e.target.value),
                  }))
                }
              />
            </div>
            <div className="flex items-center justify-between">
              <span className="text-[10px] text-slate-500">TOC (mg/L)</span>
              <Input
                className="h-6 w-14 text-right font-mono text-xs"
                value={localFeed.toc_mgL ?? ''}
                onChange={(e) =>
                  setLocalFeed((p: any) => ({
                    ...p,
                    toc_mgL: numOrNull(e.target.value),
                  }))
                }
              />
            </div>
          </div>
        </Card>

        {/* 4. Charge Balance & Quick Salt */}
        <div className="flex gap-2">
          <Card title="Quick Entry" className="flex-1 shrink-0">
            <div className="flex gap-1 mb-1">
              <div className="flex-1">
                <Input
                  className="h-6 w-full text-right font-mono text-xs"
                  placeholder="NaCl mg/L"
                  value={quick.nacl_mgL}
                  onChange={(e) =>
                    setQuick({ ...quick, nacl_mgL: num0(e.target.value) })
                  }
                />
              </div>
              <div className="flex-1">
                <Input
                  className="h-6 w-full text-right font-mono text-xs"
                  placeholder="MgSO4 mg/L"
                  value={quick.mgso4_mgL}
                  onChange={(e) =>
                    setQuick({ ...quick, mgso4_mgL: num0(e.target.value) })
                  }
                />
              </div>
            </div>
            <button
              onClick={applyQuickEntry}
              className="w-full py-1 rounded text-[10px] font-bold text-slate-400 bg-slate-800 hover:text-slate-200 border border-slate-700"
            >
              적용
            </button>
          </Card>

          <Card
            title="Charge Balance"
            className="flex-1 shrink-0 flex flex-col"
          >
            <select
              className="w-full h-6 bg-slate-950 border border-slate-700 rounded px-1 text-[10px] text-slate-200 mb-1"
              value={cbMode}
              onChange={(e) => setCbMode(e.target.value as ChargeBalanceMode)}
            >
              <option value="off">OFF</option>
              <option value="anions">Anions</option>
              <option value="cations">Cations</option>
            </select>
            <div className="text-[9px] text-slate-500 text-center mb-1">
              Δ:{' '}
              <span
                className={
                  derived.rawChargeBalance_meqL === 0 ? '' : 'text-amber-500'
                }
              >
                {fmtNumber(derived.rawChargeBalance_meqL, 3)}
              </span>{' '}
              →{' '}
              <span className="text-emerald-500">
                {cbMode !== 'off'
                  ? fmtNumber(derived.chargeBalance_meqL, 3)
                  : '-'}
              </span>
            </div>
            <button
              onClick={applyBalanceIntoTable}
              disabled={cbMode === 'off'}
              className="w-full py-1 rounded text-[10px] font-bold text-emerald-500 bg-emerald-900/20 border border-emerald-900/30 disabled:opacity-30 mt-auto"
            >
              자동 보정
            </button>
          </Card>
        </div>
      </div>

      {/* 🔵 [RIGHT COLUMN] 결과 영역 (이온 리스트) */}
      <div className="col-span-12 xl:col-span-8 flex flex-col gap-3 h-full overflow-hidden">
        {/* 상단 KPI */}
        <div className="flex gap-3 h-[70px] shrink-0">
          <div className="flex-1 bg-slate-900/60 border border-slate-800 rounded-lg p-3 flex flex-col justify-center">
            <div className="text-[10px] font-bold text-slate-500 uppercase">
              TDS {cbMode !== 'off' && '(보정)'}
            </div>
            <div className="text-2xl font-mono text-emerald-400 font-bold flex items-baseline gap-1">
              {fmtNumber(derived.totalTDS, 1)}{' '}
              <span className="text-xs font-normal text-slate-600">mg/L</span>
            </div>
          </div>
          <div className="flex-1 bg-slate-900/60 border border-slate-800 rounded-lg p-3 flex flex-col justify-center">
            <div className="text-[10px] font-bold text-slate-500 uppercase">
              Hardness
            </div>
            <div className="text-xl font-mono text-blue-300 font-semibold flex items-baseline gap-1">
              {fmtNumber(derived.calcHardness, 1)}{' '}
              <span className="text-[10px] font-normal text-slate-600">
                as CaCO3
              </span>
            </div>
          </div>
          <div className="flex-1 bg-slate-900/60 border border-slate-800 rounded-lg p-3 flex flex-col justify-center">
            <div className="text-[10px] font-bold text-slate-500 uppercase">
              Alkalinity
            </div>
            <div className="text-xl font-mono text-blue-300 font-semibold flex items-baseline gap-1">
              {fmtNumber(derived.calcAlkalinity, 1)}{' '}
              <span className="text-[10px] font-normal text-slate-600">
                as CaCO3
              </span>
            </div>
          </div>
          <div className="w-32 bg-slate-900/40 border border-slate-800 rounded-lg p-3 flex flex-col justify-center">
            <div className="text-[10px] font-bold text-slate-500 uppercase">
              Cond.
            </div>
            <div className="text-lg font-mono text-slate-300 flex items-baseline gap-1">
              {fmtNumber(derived.estConductivity_uScm, 0)}{' '}
              <span className="text-[10px] text-slate-600">µS</span>
            </div>
          </div>
        </div>

        {/* 하단 이온 테이블 */}
        <div className="flex-1 bg-slate-900/20 border border-slate-800/50 rounded-lg p-1 min-h-0 overflow-hidden flex flex-col">
          <div className="flex items-center justify-between px-3 py-2 shrink-0">
            <div className="text-xs font-bold text-slate-300 flex items-center gap-2">
              <span className="w-1.5 h-1.5 bg-blue-500 rounded-full"></span>
              Ion Composition
            </div>
          </div>

          <div className="flex-1 overflow-y-auto px-2 pb-2 custom-scrollbar">
            <div className="grid grid-cols-3 gap-4 h-full">
              <IonTable
                title="CATIONS (+)"
                defs={CATIONS}
                chem={localChem}
                accent="text-blue-300"
                onChange={(k: any, v: any) =>
                  setLocalChem({ ...localChem, [k]: v })
                }
                showDerived
                compact={true}
              />
              <IonTable
                title="ANIONS (-)"
                defs={ANIONS}
                chem={localChem}
                accent="text-rose-300"
                onChange={(k: any, v: any) =>
                  setLocalChem({ ...localChem, [k]: v })
                }
                showDerived
                compact={true}
              />
              <IonTable
                title="NEUTRALS"
                defs={NEUTRALS}
                chem={localChem}
                accent="text-emerald-300"
                onChange={(k: any, v: any) =>
                  setLocalChem({ ...localChem, [k]: v })
                }
                showDerived={false}
                compact={true}
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
