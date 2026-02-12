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

// 타입 정의 (동일)
type FeedDraft = {
  temperature_C: number;
  ph: number;
  flow_m3h: number;
  water_type?: string | null;
  water_subtype?: string | null;
  feed_note?: string | null;
  temp_min_C?: number | null;
  temp_max_C?: number | null;
  turbidity_ntu?: number | null;
  tss_mgL?: number | null;
  sdi15?: number | null;
  toc_mgL?: number | null;
  [k: string]: unknown;
};

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

// 카드 스타일 (패딩을 더 줄임: p-2)
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
    detailsOpen,
    setDetailsOpen,
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
      {/* 🔴 [LEFT COLUMN] 설정 영역: 고밀도 배치 (스크롤 제거 목적) */}
      <div className="col-span-12 xl:col-span-3 flex flex-col gap-2 h-full overflow-hidden">
        {/* 1. 통합 기본 설정 (Definition) */}
        {/* 프리셋, 분류, 운전조건, 메모를 모두 이 카드 하나에 담아 위계질서를 잡음 */}
        <Card
          title="원수 정의 및 조건 (Definition)"
          className="flex flex-col gap-2 shrink-0"
        >
          {/* A. 프리셋 */}
          <select
            className="w-full bg-slate-950 border border-slate-700 rounded px-2 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-blue-500"
            onChange={(e) => applyPreset(e.target.value)}
            defaultValue=""
          >
            <option value="" disabled>
              -- 프리셋 불러오기 --
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
            <optgroup label="기수/지하수/기타">
              {WATER_CATALOG.filter((w) => w.category !== 'Seawater').map(
                (w) => (
                  <option key={w.id} value={w.id}>
                    {w.name}
                  </option>
                ),
              )}
            </optgroup>
          </select>

          {/* B. 분류 + 출처 (한 줄 배치) */}
          <div className="flex gap-2">
            <div className="w-[35%]">
              <select
                className="w-full h-7 bg-slate-950 border border-slate-700 rounded px-1 text-xs text-slate-200"
                value={String(localFeed.water_type ?? '')}
                onChange={(e) =>
                  setLocalFeed((p: any) => ({
                    ...p,
                    water_type: e.target.value,
                  }))
                }
              >
                <option value="">(분류)</option>
                {waterTypeOptions.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex-1">
              <input
                type="text"
                list="water-subtype-suggestions"
                className="w-full h-7 bg-slate-950 border border-slate-700 rounded px-2 text-xs text-slate-200 placeholder:text-slate-600"
                value={String(localFeed.water_subtype ?? '')}
                onChange={(e) =>
                  setLocalFeed((p: any) => ({
                    ...p,
                    water_subtype: e.target.value,
                  }))
                }
                placeholder="세부 지점/출처 입력"
              />
              <datalist id="water-subtype-suggestions">
                {subtypeSuggestions.map((s) => (
                  <option key={s} value={s} />
                ))}
              </datalist>
            </div>
          </div>

          {/* C. 운전 조건 (3단 한 줄) */}
          <div className="flex gap-2 items-center bg-slate-950/30 p-1.5 rounded border border-slate-800/30">
            <div className="flex-1">
              <div className="text-[9px] text-slate-500 mb-0.5">
                유량({unitLabel('flow', unitMode)})
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
            <div className="w-px h-6 bg-slate-800"></div>
            <div className="flex-1">
              <div className="text-[9px] text-slate-500 mb-0.5">
                온도({unitLabel('temp', unitMode)})
              </div>
              <Input
                className="h-6 w-full text-center font-mono text-xs"
                value={localFeed.temperature_C}
                onChange={(e) =>
                  setLocalFeed((p: any) => ({
                    ...p,
                    temperature_C: num0(e.target.value),
                  }))
                }
              />
            </div>
            <div className="w-px h-6 bg-slate-800"></div>
            <div className="flex-1">
              <div className="text-[9px] text-slate-500 mb-0.5">pH</div>
              <Input
                className="h-6 w-full text-center font-mono text-xs"
                value={localFeed.ph}
                min={0}
                max={14}
                onChange={(e) =>
                  setLocalFeed((p: any) => ({
                    ...p,
                    ph: clampf(num0(e.target.value), 0, 14),
                  }))
                }
              />
            </div>
          </div>

          {/* D. 메모 (여기로 복귀!) */}
          <div>
            <div className="text-[9px] text-slate-500 mb-1 flex justify-between">
              <span>메모 / 특이사항</span>
              <span className="text-slate-600 italic">Optional</span>
            </div>
            <textarea
              className="w-full h-14 bg-slate-950 border border-slate-700 rounded px-2 py-1 text-xs text-slate-300 resize-none focus:outline-none focus:border-blue-500 placeholder:text-slate-700"
              placeholder="프로젝트명, 샘플링 날짜 등..."
              value={localFeed.feed_note ?? ''}
              onChange={(e) =>
                setLocalFeed((p: any) => ({ ...p, feed_note: e.target.value }))
              }
            />
          </div>
        </Card>

        {/* 2. 도구 모음 (Tools) - 남는 공간 활용 */}
        <div className="flex-1 flex flex-col gap-2 min-h-0">
          {/* Quick Salt */}
          <Card title="빠른 입력 (Quick Salt)" className="shrink-0">
            <div className="flex gap-2 mb-2">
              <div className="flex-1">
                <div className="text-[9px] text-slate-500 mb-0.5">NaCl</div>
                <Input
                  className="h-7 w-full text-right font-mono text-xs"
                  value={quick.nacl_mgL}
                  onChange={(e) =>
                    setQuick({ ...quick, nacl_mgL: num0(e.target.value) })
                  }
                />
              </div>
              <div className="flex-1">
                <div className="text-[9px] text-slate-500 mb-0.5">MgSO4</div>
                <Input
                  className="h-7 w-full text-right font-mono text-xs"
                  value={quick.mgso4_mgL}
                  onChange={(e) =>
                    setQuick({ ...quick, mgso4_mgL: num0(e.target.value) })
                  }
                />
              </div>
            </div>
            <button
              onClick={applyQuickEntry}
              className="w-full py-1.5 rounded text-[10px] font-bold text-slate-400 bg-slate-800 hover:text-slate-200 hover:bg-slate-700 transition-colors border border-slate-700"
            >
              ▼ 이온 농도에 추가
            </button>
          </Card>

          {/* Charge Balance */}
          <Card
            title="전하 밸런스 (WAVE Mode)"
            className="flex-1 min-h-0 flex flex-col"
          >
            <div className="flex flex-col gap-2">
              <select
                className="w-full h-7 bg-slate-950 border border-slate-700 rounded px-1 text-xs text-slate-200"
                value={cbMode}
                onChange={(e) => setCbMode(e.target.value as ChargeBalanceMode)}
              >
                <option value="off">OFF (원본 유지)</option>
                <option value="anions">Anions (음이온 기준)</option>
                <option value="cations">Cations (양이온 기준)</option>
                <option value="all">All (전체 보정)</option>
              </select>

              <div className="flex justify-between items-center text-[10px] bg-slate-950/50 p-1.5 rounded border border-slate-800/50">
                <span className="text-slate-500">Input Δ:</span>
                <span
                  className={`font-mono ${derived.rawChargeBalance_meqL === 0 ? 'text-slate-500' : 'text-amber-500'}`}
                >
                  {fmtNumber(derived.rawChargeBalance_meqL, 3)}
                </span>
                <span className="text-slate-700">|</span>
                <span className="text-slate-500">Rslt Δ:</span>
                <span className="font-mono text-emerald-500">
                  {cbMode !== 'off'
                    ? fmtNumber(derived.chargeBalance_meqL, 3)
                    : '-'}
                </span>
              </div>

              <button
                onClick={applyBalanceIntoTable}
                disabled={cbMode === 'off'}
                className="w-full py-2 rounded text-[11px] font-bold text-emerald-500 bg-emerald-900/10 border border-emerald-900/30 hover:bg-emerald-900/20 disabled:opacity-30 disabled:cursor-not-allowed mt-auto"
              >
                ▶ 표(Table) 값 자동 보정
              </button>
            </div>
          </Card>
        </div>
      </div>

      {/* 🔵 [RIGHT COLUMN] 결과 영역 (변동 없음, 메모 제거됨) */}
      <div className="col-span-12 xl:col-span-9 flex flex-col gap-3 h-full overflow-hidden">
        {/* 상단 KPI */}
        <div className="flex gap-3 h-[70px] shrink-0">
          <div className="flex-1 bg-slate-900/60 border border-slate-800 rounded-lg p-3 flex flex-col justify-center relative overflow-hidden group">
            <div className="text-[10px] font-bold text-slate-500 uppercase z-10">
              TDS {cbMode !== 'off' && '(보정)'}
            </div>
            <div className="text-2xl font-mono text-emerald-400 font-bold z-10 flex items-baseline gap-1">
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
              이온 조성표 (Ion Composition)
            </div>
            <button
              onClick={() => setDetailsOpen(!detailsOpen)}
              className="text-[10px] text-slate-500 hover:text-slate-300 underline"
            >
              {detailsOpen ? '닫기' : 'SS/SDI/TOC 추가'}
            </button>
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
              <div className="flex flex-col gap-3">
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

                {/* 상세 입력 (Neutrals 아래 배치) */}
                {detailsOpen && (
                  <div className="bg-slate-900 border border-slate-700 p-2 rounded animate-in fade-in slide-in-from-top-2 duration-200">
                    <div className="grid grid-cols-2 gap-2">
                      <Field label="Turbidity">
                        <Input
                          className="h-7 text-right"
                          value={localFeed.turbidity_ntu ?? ''}
                          onChange={(e: any) =>
                            setLocalFeed((p: any) => ({
                              ...p,
                              turbidity_ntu: numOrNull(e.target.value),
                            }))
                          }
                        />
                      </Field>
                      <Field label="TSS">
                        <Input
                          className="h-7 text-right"
                          value={localFeed.tss_mgL ?? ''}
                          onChange={(e: any) =>
                            setLocalFeed((p: any) => ({
                              ...p,
                              tss_mgL: numOrNull(e.target.value),
                            }))
                          }
                        />
                      </Field>
                      <Field label="SDI 15">
                        <Input
                          className="h-7 text-right"
                          value={localFeed.sdi15 ?? ''}
                          onChange={(e: any) =>
                            setLocalFeed((p: any) => ({
                              ...p,
                              sdi15: numOrNull(e.target.value),
                            }))
                          }
                        />
                      </Field>
                      <Field label="TOC">
                        <Input
                          className="h-7 text-right"
                          value={localFeed.toc_mgL ?? ''}
                          onChange={(e: any) =>
                            setLocalFeed((p: any) => ({
                              ...p,
                              toc_mgL: numOrNull(e.target.value),
                            }))
                          }
                        />
                      </Field>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
