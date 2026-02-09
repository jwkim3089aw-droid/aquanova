// ui/src/features/simulation/components/FlowModals.tsx

import React, { useEffect, useState } from 'react';
import { Node } from 'reactflow';

import {
  Field,
  Input,
  HRROEditor,
  ROEditor,
  UFEditor,
  NFEditor,
  MFEditor,
  PumpEditor,
} from '..';

import MembraneSelect from './MembraneSelect';
import { WATER_CATALOG } from '../data/water_catalog';

import {
  UnitData,
  FlowData,
  EndpointData,
  UnitKind,
  ChemistryInput,
  unitLabel,
  UnitMode,
  clampf,
  SetNodesFn,
  SetEdgesFn,
} from '../model/types';

import { updateUnitCfg } from '../model/logic';

// ------------------------------------------------------------------
// 공통: 모달이 열려있을 때 Delete/Backspace가 ReactFlow로 새는 걸 차단
// ------------------------------------------------------------------
function useBlockDeleteKeysWhenOpen(isOpen: boolean) {
  useEffect(() => {
    if (!isOpen) return;

    const handleKeyDownCapture = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement;

      // input/textarea에서는 정상 동작
      const tag = (target?.tagName || '').toUpperCase();
      if (tag === 'INPUT' || tag === 'TEXTAREA') return;

      if (e.key === 'Delete' || e.key === 'Backspace') {
        e.preventDefault();
        e.stopPropagation();
        e.stopImmediatePropagation();
      }
    };

    window.addEventListener('keydown', handleKeyDownCapture, true);
    return () =>
      window.removeEventListener('keydown', handleKeyDownCapture, true);
  }, [isOpen]);
}

// -----------------------------
// WAVE 스타일 이온 분석
// -----------------------------
type IonDef = { label: string; key: string; mw: number; z: number };

const MW = {
  NH4: 18.04,
  K: 39.098,
  Na: 22.99,
  Mg: 24.305,
  Ca: 40.078,
  Sr: 87.62,
  Ba: 137.327,
  Fe: 55.845,
  Mn: 54.938,

  HCO3: 61.017,
  NO3: 62.005,
  Cl: 35.453,
  F: 18.998,
  SO4: 96.06,
  Br: 79.904,
  PO4: 94.97,
  CO3: 60.01,

  SiO2: 60.08,
  B: 10.811,
  CO2: 44.009,
};

const CATIONS: IonDef[] = [
  { label: 'NH4', key: 'nh4_mgL', mw: MW.NH4, z: +1 },
  { label: 'K', key: 'k_mgL', mw: MW.K, z: +1 },
  { label: 'Na', key: 'na_mgL', mw: MW.Na, z: +1 },
  { label: 'Mg', key: 'mg_mgL', mw: MW.Mg, z: +2 },
  { label: 'Ca', key: 'ca_mgL', mw: MW.Ca, z: +2 },
  { label: 'Sr', key: 'sr_mgL', mw: MW.Sr, z: +2 },
  { label: 'Ba', key: 'ba_mgL', mw: MW.Ba, z: +2 },
  // WAVE 느낌으로 기본 +2 가정
  { label: 'Fe', key: 'fe_mgL', mw: MW.Fe, z: +2 },
  { label: 'Mn', key: 'mn_mgL', mw: MW.Mn, z: +2 },
];

const ANIONS: IonDef[] = [
  { label: 'HCO3', key: 'hco3_mgL', mw: MW.HCO3, z: -1 },
  { label: 'NO3', key: 'no3_mgL', mw: MW.NO3, z: -1 },
  { label: 'Cl', key: 'cl_mgL', mw: MW.Cl, z: -1 },
  { label: 'F', key: 'f_mgL', mw: MW.F, z: -1 },
  { label: 'SO4', key: 'so4_mgL', mw: MW.SO4, z: -2 },
  { label: 'Br', key: 'br_mgL', mw: MW.Br, z: -1 },
  { label: 'PO4', key: 'po4_mgL', mw: MW.PO4, z: -3 },
  { label: 'CO3', key: 'co3_mgL', mw: MW.CO3, z: -2 },
];

const NEUTRALS: IonDef[] = [
  { label: 'SiO2', key: 'sio2_mgL', mw: MW.SiO2, z: 0 },
  { label: 'B', key: 'b_mgL', mw: MW.B, z: 0 },
  { label: 'CO2', key: 'co2_mgL', mw: MW.CO2, z: 0 },
];

function n0(v: any): number {
  const x = Number(v);
  return Number.isFinite(x) ? x : 0;
}

// mg/L -> meq/L : (mg/L / MW[g/mol]) = mmol/L, meq/L = mmol/L * |z|
function mgL_to_meqL(mgL: number, mw: number, z: number): number {
  if (!mw || !z) return 0;
  return (mgL / mw) * Math.abs(z);
}

// meq/L -> ppm as CaCO3
function meqL_to_ppmCaCO3(meqL: number): number {
  return meqL * 50.0;
}

function sumMgL(chem: any, defs: IonDef[]) {
  return defs.reduce((acc, d) => acc + n0(chem?.[d.key]), 0);
}

function sumMeqL(chem: any, defs: IonDef[]) {
  return defs.reduce(
    (acc, d) => acc + mgL_to_meqL(n0(chem?.[d.key]), d.mw, d.z),
    0,
  );
}

// ------------------------------------------------------------------
// 공통 UI: 카드
// ------------------------------------------------------------------
function Card({
  title,
  subtitle,
  right,
  children,
}: {
  title: string;
  subtitle?: string;
  right?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900/30 overflow-hidden">
      <div className="px-4 py-3 border-b border-slate-800 flex items-start justify-between gap-3 bg-slate-900/20">
        <div className="min-w-0">
          <div className="text-xs font-bold text-slate-100">{title}</div>
          {subtitle ? (
            <div className="text-[11px] text-slate-400 mt-0.5">{subtitle}</div>
          ) : null}
        </div>
        {right ? <div className="shrink-0">{right}</div> : null}
      </div>
      <div className="p-4">{children}</div>
    </div>
  );
}

// ------------------------------------------------------------------
// Helper: Ion Row (한 줄 입력/파생값)
// ------------------------------------------------------------------
function IonRow({
  def,
  value,
  onChange,
  showDerived = true,
}: {
  def: IonDef;
  value: any;
  onChange: (v: number) => void;
  showDerived?: boolean;
}) {
  const mgL = n0(value);
  const meqL = showDerived ? mgL_to_meqL(mgL, def.mw, def.z) : 0;
  const ppm = showDerived ? meqL_to_ppmCaCO3(meqL) : 0;

  return (
    <div className="grid grid-cols-12 gap-2 items-center px-3 py-2 rounded-xl border border-slate-800 bg-slate-950/40 hover:bg-slate-950/60 transition-colors">
      <div className="col-span-2 text-[11px] font-semibold text-slate-200">
        {def.label}
      </div>

      <div className="col-span-4">
        <input
          type="number"
          className="w-full bg-transparent text-right text-sm text-slate-100 outline-none font-mono placeholder:text-slate-600"
          value={value ?? ''}
          placeholder="0"
          onFocus={(e) => e.currentTarget.select()}
          onChange={(e) => {
            const raw = e.target.value;
            const v = raw === '' ? 0 : Number(raw);
            onChange(Number.isFinite(v) ? v : 0);
          }}
        />
      </div>

      <div className="col-span-3 text-right text-xs font-mono text-slate-400">
        {showDerived ? ppm.toFixed(2) : '—'}
      </div>

      <div className="col-span-3 text-right text-xs font-mono text-slate-400">
        {showDerived ? meqL.toFixed(4) : '—'}
      </div>
    </div>
  );
}

function IonSection({
  title,
  sumMgL,
  defs,
  chem,
  setChem,
  showDerived,
  accent = 'slate',
}: {
  title: string;
  sumMgL: number;
  defs: IonDef[];
  chem: any;
  setChem: (v: any) => void;
  showDerived: boolean;
  accent?: 'blue' | 'rose' | 'emerald' | 'slate';
}) {
  const accentMap: Record<string, string> = {
    blue: 'border-blue-900/30',
    rose: 'border-rose-900/30',
    emerald: 'border-emerald-900/30',
    slate: 'border-slate-800',
  };

  const accentTextMap: Record<string, string> = {
    blue: 'text-blue-300',
    rose: 'text-rose-300',
    emerald: 'text-emerald-300',
    slate: 'text-slate-300',
  };

  return (
    <div className={`rounded-2xl border ${accentMap[accent]} bg-slate-950/20`}>
      <div className="px-4 py-3 border-b border-slate-800 flex items-center justify-between">
        <div className={`text-xs font-extrabold ${accentTextMap[accent]}`}>
          {title}
        </div>
        <div className="text-xs font-mono text-slate-400">
          {sumMgL.toFixed(2)} mg/L
        </div>
      </div>

      <div className="p-4">
        <div className="grid grid-cols-12 gap-2 px-3 mb-2 text-[10px] text-slate-500 uppercase tracking-wider">
          <div className="col-span-2">Ion</div>
          <div className="col-span-4 text-right">mg/L</div>
          <div className="col-span-3 text-right">ppm CaCO3</div>
          <div className="col-span-3 text-right">meq/L</div>
        </div>

        <div className="space-y-2">
          {defs.map((d) => (
            <IonRow
              key={d.key}
              def={d}
              value={chem?.[d.key]}
              onChange={(v) => setChem({ ...chem, [d.key]: v })}
              showDerived={showDerived}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

// ------------------------------------------------------------------
// Unit / Feed Settings Modal
// ------------------------------------------------------------------
interface InspectorProps {
  isOpen: boolean;
  onClose: () => void;
  selEndpoint: (Node<FlowData> & { data: EndpointData }) | null;
  selUnit: Node<FlowData> | null;

  feed: {
    flow_m3h: number;
    tds_mgL: number;
    temperature_C: number;
    ph: number;
    pressure_bar?: number;

    // WAVE-style feed meta
    water_type?: string | null;
    water_subtype?: string | null;
    turbidity_ntu?: number | null;
    tss_mgL?: number | null;
    sdi15?: number | null;
    toc_mgL?: number | null;

    // UI-only (WAVE min/max temp, memo)
    temp_min_C?: number | null;
    temp_max_C?: number | null;
    feed_note?: string | null;

    [k: string]: any;
  };

  setFeed: (v: any) => void;
  feedChemistry: ChemistryInput;
  setFeedChemistry: React.Dispatch<React.SetStateAction<ChemistryInput>>;
  unitMode: UnitMode;
  setNodes: SetNodesFn;
  setEdges: SetEdgesFn;
  setSelectedNodeId: (id: string | null) => void;
}

export function UnitInspectorModal(props: InspectorProps) {
  const {
    isOpen,
    onClose,
    selEndpoint,
    selUnit,
    feed,
    setFeed,
    feedChemistry,
    setFeedChemistry,
    unitMode,
    setNodes,
  } = props;

  useBlockDeleteKeysWhenOpen(isOpen);

  const [localFeed, setLocalFeed] = useState<any>(feed);
  const [localChem, setLocalChem] = useState<any>(feedChemistry);
  const [localCfg, setLocalCfg] = useState<any>(null);
  const [quick, setQuick] = useState({ nacl_mgL: 0, mgso4_mgL: 0 });

  // 로컬 상태 초기화
  useEffect(() => {
    if (!isOpen) return;

    const minT = (feed as any)?.temp_min_C ?? feed.temperature_C;
    const maxT = (feed as any)?.temp_max_C ?? feed.temperature_C;

    setLocalFeed({
      ...feed,
      temp_min_C: minT,
      temp_max_C: maxT,
      feed_note: (feed as any)?.feed_note ?? '',
    });

    setLocalChem(feedChemistry || {});
    setQuick({ nacl_mgL: 0, mgso4_mgL: 0 });

    if (selUnit && (selUnit.data as any).type === 'unit') {
      setLocalCfg(JSON.parse(JSON.stringify((selUnit.data as any).cfg)));
    } else {
      setLocalCfg(null);
    }
  }, [isOpen, selEndpoint?.id, selUnit?.id, feed, feedChemistry]);

  // ✅ Hook 순서 문제 방지: hooks 이후에만 조건 return
  if (!isOpen || (!selEndpoint && !selUnit)) return null;

  // ---- 합계 (mg/L) ----
  const cationSum = sumMgL(localChem, CATIONS);
  const anionSum = sumMgL(localChem, ANIONS);
  const neutralSum = sumMgL(localChem, NEUTRALS);
  const totalTDS = cationSum + anionSum + neutralSum;

  // ---- 합계 (meq/L) ----
  const cationMeq = sumMeqL(localChem, CATIONS);
  const anionMeq = sumMeqL(localChem, ANIONS);
  const chargeBalance_meqL = cationMeq - anionMeq;

  // Hardness(as CaCO3) = (Ca meq + Mg meq) * 50
  const ca_meq = mgL_to_meqL(n0(localChem?.ca_mgL), MW.Ca, +2);
  const mg_meq = mgL_to_meqL(n0(localChem?.mg_mgL), MW.Mg, +2);
  const calcHardness = (ca_meq + mg_meq) * 50.0;

  // Alkalinity(as CaCO3) = (HCO3 meq + CO3 meq) * 50
  const hco3_meq = mgL_to_meqL(n0(localChem?.hco3_mgL), MW.HCO3, -1);
  const co3_meq = mgL_to_meqL(n0(localChem?.co3_mgL), MW.CO3, -2);
  const calcAlkalinity = (hco3_meq + co3_meq) * 50.0;

  // Conductivity (uS/cm) — 근사치
  const estConductivity_uScm = totalTDS * 1.7;

  const applyPreset = (presetId: string) => {
    const preset = WATER_CATALOG.find((p) => p.id === presetId);
    if (!preset) return;

    const ions = preset.ions;
    const calcTDS = Object.values(ions).reduce((sum, v) => sum + (v || 0), 0);

    setLocalFeed((prev: any) => ({
      ...prev,
      temperature_C: preset.temp_C,
      ph: preset.ph,
      tds_mgL: calcTDS,
      temp_min_C: prev?.temp_min_C ?? preset.temp_C,
      temp_max_C: prev?.temp_max_C ?? preset.temp_C,
    }));

    setLocalChem({
      nh4_mgL: ions.NH4,
      k_mgL: ions.K,
      na_mgL: ions.Na,
      mg_mgL: ions.Mg,
      ca_mgL: ions.Ca,
      sr_mgL: ions.Sr,
      ba_mgL: ions.Ba,
      fe_mgL: ions.Fe,
      mn_mgL: ions.Mn,

      hco3_mgL: ions.HCO3,
      no3_mgL: ions.NO3,
      cl_mgL: ions.Cl,
      f_mgL: ions.F,
      so4_mgL: ions.SO4,
      br_mgL: ions.Br,
      po4_mgL: ions.PO4,
      co3_mgL: ions.CO3,

      sio2_mgL: ions.SiO2,
      b_mgL: ions.B,
      co2_mgL: ions.CO2,

      alkalinity_mgL_as_CaCO3: null,
      calcium_hardness_mgL_as_CaCO3: null,
    });
  };

  const applyQuickEntry = () => {
    const nacl = Math.max(0, n0(quick.nacl_mgL));
    const mgso4 = Math.max(0, n0(quick.mgso4_mgL));

    const mwNaCl = MW.Na + MW.Cl;
    const addNa = mwNaCl > 0 ? nacl * (MW.Na / mwNaCl) : 0;
    const addCl = mwNaCl > 0 ? nacl * (MW.Cl / mwNaCl) : 0;

    const mwMgSO4 = MW.Mg + MW.SO4;
    const addMg = mwMgSO4 > 0 ? mgso4 * (MW.Mg / mwMgSO4) : 0;
    const addSO4 = mwMgSO4 > 0 ? mgso4 * (MW.SO4 / mwMgSO4) : 0;

    setLocalChem((prev: any) => ({
      ...prev,
      na_mgL: n0(prev?.na_mgL) + addNa,
      cl_mgL: n0(prev?.cl_mgL) + addCl,
      mg_mgL: n0(prev?.mg_mgL) + addMg,
      so4_mgL: n0(prev?.so4_mgL) + addSO4,
    }));

    setQuick({ nacl_mgL: 0, mgso4_mgL: 0 });
  };

  const handleApply = () => {
    if (selEndpoint?.data.role === 'feed') {
      const chemOut = {
        ...localChem,
        alkalinity_mgL_as_CaCO3: calcAlkalinity,
        calcium_hardness_mgL_as_CaCO3: calcHardness,
      };

      setFeed({ ...localFeed, tds_mgL: totalTDS });
      setFeedChemistry(chemOut);
    } else if (selUnit && localCfg) {
      updateUnitCfg(selUnit.id, localCfg, setNodes);
    }
    onClose();
  };

  const isProductNode = selEndpoint?.data.role === 'product';

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-[2px] p-4"
      onClick={onClose}
    >
      <div
        className="w-full max-w-6xl max-h-[88vh] flex flex-col rounded-2xl border border-slate-800 bg-slate-950 shadow-2xl ring-1 ring-white/5 overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* 헤더 */}
        <div className="flex items-center justify-between px-5 py-3 border-b border-slate-800 bg-slate-900/40 shrink-0">
          <div className="flex items-center gap-3">
            <div
              className={`w-2 h-2 rounded-full ${
                selEndpoint ? 'bg-blue-500' : 'bg-emerald-500'
              }`}
            />
            <div className="flex flex-col leading-tight">
              <div className="text-sm font-bold text-slate-100">
                {selEndpoint?.data.role === 'feed'
                  ? '원수(Feed) 수질 입력'
                  : selUnit
                    ? `${(selUnit.data as UnitData).kind} 설정`
                    : '설정'}
              </div>
              <div className="text-[11px] text-slate-400">
                {selEndpoint?.data.role === 'feed'
                  ? '이온 조성 기반으로 TDS/경도/알칼리도 등을 자동 계산합니다.'
                  : '선택된 유닛의 설정값을 편집합니다.'}
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {isProductNode ? (
              <button
                onClick={onClose}
                className="px-3 py-1.5 rounded-xl text-xs font-extrabold text-slate-200 bg-slate-800 border border-slate-700 hover:bg-slate-700"
              >
                닫기
              </button>
            ) : (
              <>
                <button
                  onClick={onClose}
                  className="px-3 py-1.5 rounded-xl text-xs font-extrabold text-slate-300 bg-slate-900/50 border border-slate-800 hover:border-slate-700 hover:text-slate-100"
                >
                  취소
                </button>
                <button
                  onClick={handleApply}
                  className="px-4 py-1.5 rounded-xl text-xs font-extrabold text-white bg-blue-600 hover:bg-blue-500 shadow-lg shadow-blue-900/20 active:scale-95 transition"
                >
                  적용
                </button>
              </>
            )}
          </div>
        </div>

        {/* 본문 */}
        <div className="flex-1 overflow-y-auto p-5 space-y-4 scrollbar-thin scrollbar-thumb-slate-700 scrollbar-track-transparent">
          {selEndpoint?.data.role === 'feed' ? (
            <div className="grid grid-cols-12 gap-4">
              {/* 좌측 */}
              <div className="col-span-12 lg:col-span-5 space-y-4">
                <Card
                  title="프리셋 라이브러리"
                  subtitle="표준 수질 조성을 빠르게 불러옵니다."
                >
                  <select
                    className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-blue-500 cursor-pointer"
                    onChange={(e) => applyPreset(e.target.value)}
                    defaultValue=""
                  >
                    <option value="" disabled>
                      -- 프리셋 선택 --
                    </option>

                    <optgroup label="해수(Seawater)">
                      {WATER_CATALOG.filter(
                        (w) => w.category === 'Seawater',
                      ).map((w) => (
                        <option key={w.id} value={w.id}>
                          {w.name}
                        </option>
                      ))}
                    </optgroup>

                    <optgroup label="기수/지하수(Brackish)">
                      {WATER_CATALOG.filter(
                        (w) => w.category === 'Brackish',
                      ).map((w) => (
                        <option key={w.id} value={w.id}>
                          {w.name}
                        </option>
                      ))}
                    </optgroup>

                    <optgroup label="하폐수/재이용(Waste & Reuse)">
                      {WATER_CATALOG.filter((w) =>
                        ['Waste', 'Reuse'].includes(w.category),
                      ).map((w) => (
                        <option key={w.id} value={w.id}>
                          {w.name}
                        </option>
                      ))}
                    </optgroup>
                  </select>
                </Card>

                <Card title="기본 조건" subtitle="원수 운전 조건을 입력합니다.">
                  <div className="grid grid-cols-12 gap-3">
                    <div className="col-span-6">
                      <Field label={`온도 (${unitLabel('temp', unitMode)})`}>
                        <Input
                          className="h-9 text-right font-mono"
                          value={localFeed.temperature_C}
                          onChange={(e) =>
                            setLocalFeed({
                              ...localFeed,
                              temperature_C: Number(e.target.value),
                            })
                          }
                        />
                      </Field>
                    </div>

                    <div className="col-span-6">
                      <Field label="pH (@25°C)">
                        <Input
                          className="h-9 text-right font-mono"
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
                    </div>

                    <div className="col-span-12">
                      <Field
                        label={`원수 유량 (${unitLabel('flow', unitMode)})`}
                      >
                        <Input
                          className="h-9 text-right font-mono font-bold text-emerald-300"
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

                    <div className="col-span-12 pt-2 mt-1 border-t border-slate-800">
                      <div className="text-[11px] font-bold text-slate-300 mb-2">
                        빠른 입력(염 추가)
                      </div>

                      <div className="grid grid-cols-12 gap-3">
                        <div className="col-span-6">
                          <Field label="NaCl (mg/L)">
                            <Input
                              className="h-9 text-right font-mono"
                              value={quick.nacl_mgL}
                              onChange={(e) =>
                                setQuick({
                                  ...quick,
                                  nacl_mgL: Number(e.target.value),
                                })
                              }
                            />
                          </Field>
                        </div>

                        <div className="col-span-6">
                          <Field label="MgSO4 (mg/L)">
                            <Input
                              className="h-9 text-right font-mono"
                              value={quick.mgso4_mgL}
                              onChange={(e) =>
                                setQuick({
                                  ...quick,
                                  mgso4_mgL: Number(e.target.value),
                                })
                              }
                            />
                          </Field>
                        </div>

                        <div className="col-span-12 flex justify-end">
                          <button
                            onClick={applyQuickEntry}
                            className="px-3 py-2 rounded-xl text-xs font-extrabold text-slate-100 bg-slate-800 border border-slate-700 hover:bg-slate-700 hover:border-slate-600"
                          >
                            이온 항목에 반영
                          </button>
                        </div>
                      </div>
                    </div>
                  </div>
                </Card>

                <Card
                  title="원수 정보(선택)"
                  subtitle="수질 분류/온도 범위/메모를 기록합니다."
                >
                  <div className="grid grid-cols-12 gap-3">
                    <div className="col-span-12 md:col-span-6">
                      <Field label="수질 유형(Water Type)">
                        <Input
                          className="h-9"
                          value={localFeed.water_type ?? ''}
                          placeholder="(선택)"
                          onChange={(e) =>
                            setLocalFeed({
                              ...localFeed,
                              water_type: e.target.value,
                            })
                          }
                        />
                      </Field>
                    </div>

                    <div className="col-span-12 md:col-span-6">
                      <Field label="세부 유형(Sub-type)">
                        <Input
                          className="h-9"
                          value={localFeed.water_subtype ?? ''}
                          placeholder="(선택)"
                          onChange={(e) =>
                            setLocalFeed({
                              ...localFeed,
                              water_subtype: e.target.value,
                            })
                          }
                        />
                      </Field>
                    </div>

                    <div className="col-span-4">
                      <Field label="최저(°C)">
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

                    <div className="col-span-4">
                      <Field label="설계(°C)">
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

                    <div className="col-span-4">
                      <Field label="최고(°C)">
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

                    <div className="col-span-12">
                      <Field label="추가 메모">
                        <textarea
                          className="w-full h-20 bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-blue-500"
                          value={localFeed.feed_note ?? ''}
                          placeholder="(선택) 예: 계절 변동, 전처리 조건, 참고사항 등"
                          onChange={(e) =>
                            setLocalFeed({
                              ...localFeed,
                              feed_note: e.target.value,
                            })
                          }
                        />
                      </Field>
                    </div>
                  </div>
                </Card>

                <Card title="고형물 / 유기물 지표(선택)">
                  <div className="grid grid-cols-12 gap-3">
                    <div className="col-span-6">
                      <Field label="탁도(NTU)">
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
                    </div>

                    <div className="col-span-6">
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
                    </div>

                    <div className="col-span-6">
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
                    </div>

                    <div className="col-span-6">
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
                </Card>
              </div>

              {/* 우측 */}
              <div className="col-span-12 lg:col-span-7 space-y-4">
                <Card
                  title="요약"
                  subtitle="이온 합계를 기반으로 자동 계산됩니다."
                >
                  <div className="grid grid-cols-12 gap-3">
                    <div className="col-span-6 rounded-2xl border border-slate-800 bg-slate-950/40 p-3">
                      <div className="text-[11px] text-slate-400">총 TDS</div>
                      <div className="text-lg font-extrabold font-mono text-emerald-300">
                        {totalTDS.toFixed(2)}{' '}
                        <span className="text-xs font-bold text-slate-500">
                          mg/L
                        </span>
                      </div>
                    </div>

                    <div className="col-span-6 rounded-2xl border border-slate-800 bg-slate-950/40 p-3">
                      <div className="text-[11px] text-slate-400">
                        추정 전기전도도
                      </div>
                      <div className="text-lg font-extrabold font-mono text-slate-100">
                        {estConductivity_uScm.toFixed(2)}{' '}
                        <span className="text-xs font-bold text-slate-500">
                          µS/cm
                        </span>
                      </div>
                    </div>

                    <div className="col-span-6 rounded-2xl border border-slate-800 bg-slate-950/40 p-3">
                      <div className="text-[11px] text-slate-400">
                        경도(Hardness)
                      </div>
                      <div className="text-base font-bold font-mono text-slate-100">
                        {calcHardness.toFixed(1)}{' '}
                        <span className="text-xs text-slate-500">as CaCO3</span>
                      </div>
                    </div>

                    <div className="col-span-6 rounded-2xl border border-slate-800 bg-slate-950/40 p-3">
                      <div className="text-[11px] text-slate-400">
                        알칼리도(Alkalinity)
                      </div>
                      <div className="text-base font-bold font-mono text-slate-100">
                        {calcAlkalinity.toFixed(1)}{' '}
                        <span className="text-xs text-slate-500">as CaCO3</span>
                      </div>
                    </div>

                    <div className="col-span-6 rounded-2xl border border-slate-800 bg-slate-950/40 p-3">
                      <div className="text-[11px] text-slate-400">
                        전하 균형(Charge Balance)
                      </div>
                      <div className="text-base font-bold font-mono text-slate-100">
                        {chargeBalance_meqL.toFixed(6)}{' '}
                        <span className="text-xs text-slate-500">meq/L</span>
                      </div>
                    </div>

                    <div className="col-span-6 rounded-2xl border border-slate-800 bg-slate-950/40 p-3">
                      <div className="text-[11px] text-slate-400">
                        합계(meq/L)
                      </div>
                      <div className="text-base font-bold font-mono text-slate-100">
                        C {cationMeq.toFixed(4)} / A {anionMeq.toFixed(4)}
                      </div>
                    </div>
                  </div>
                </Card>

                {/* ✅ 이온 조성 입력: 한 번에 다 보기 */}
                <Card
                  title="이온 조성 입력"
                  subtitle="양이온/음이온/중성을 한 화면에서 동시에 입력합니다."
                >
                  <div className="grid grid-cols-12 gap-4">
                    <div className="col-span-12 xl:col-span-4">
                      <IonSection
                        title="양이온(+)"
                        sumMgL={cationSum}
                        defs={CATIONS}
                        chem={localChem}
                        setChem={setLocalChem}
                        showDerived={true}
                        accent="blue"
                      />
                    </div>

                    <div className="col-span-12 xl:col-span-4">
                      <IonSection
                        title="음이온(-)"
                        sumMgL={anionSum}
                        defs={ANIONS}
                        chem={localChem}
                        setChem={setLocalChem}
                        showDerived={true}
                        accent="rose"
                      />
                    </div>

                    <div className="col-span-12 xl:col-span-4">
                      <IonSection
                        title="중성(Neutrals)"
                        sumMgL={neutralSum}
                        defs={NEUTRALS}
                        chem={localChem}
                        setChem={setLocalChem}
                        showDerived={false}
                        accent="emerald"
                      />
                    </div>
                  </div>

                  <div className="mt-4 rounded-2xl border border-slate-800 bg-slate-950/30 p-3">
                    <div className="text-[11px] text-slate-400">
                      총 TDS는 위 이온 합계(mg/L)로 자동 계산되며, <b>적용</b>{' '}
                      시 원수 TDS에 반영됩니다.
                    </div>
                  </div>
                </Card>
              </div>
            </div>
          ) : selUnit && localCfg ? (
            (() => {
              const u = selUnit.data as UnitData;
              const kind = u.kind as UnitKind;
              const proxyUnit = { ...u, cfg: localCfg };
              const updateCfgLocal = (newCfg: any) => setLocalCfg(newCfg);

              if (kind === 'HRRO')
                return (
                  <HRROEditor node={proxyUnit} onChange={updateCfgLocal} />
                );
              if (kind === 'RO')
                return (
                  <ROEditor node={proxyUnit} onChange={updateCfgLocal as any} />
                );
              if (kind === 'UF')
                return (
                  <UFEditor node={proxyUnit} onChange={updateCfgLocal as any} />
                );
              if (kind === 'NF')
                return (
                  <NFEditor node={proxyUnit} onChange={updateCfgLocal as any} />
                );
              if (kind === 'MF')
                return (
                  <MFEditor node={proxyUnit} onChange={updateCfgLocal as any} />
                );
              if (kind === 'PUMP')
                return (
                  <PumpEditor
                    node={proxyUnit as any}
                    onChange={updateCfgLocal}
                  />
                );

              return (
                <div className="text-sm text-red-300">
                  알 수 없는 유닛 타입: {kind}
                </div>
              );
            })()
          ) : isProductNode ? (
            <div className="h-full flex flex-col items-center justify-center text-slate-500 opacity-70 py-16">
              <div className="text-4xl mb-3">🏁</div>
              <p className="text-sm font-bold">최종 생산수(Product)</p>
              <p className="text-xs mt-1">
                시뮬레이션 실행 후 결과가 표시됩니다
              </p>
            </div>
          ) : (
            <div className="text-sm text-slate-400">
              선택된 노드가 없습니다.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ------------------------------------------------------------------
// Global Options Modal
// ------------------------------------------------------------------
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
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-[2px] p-4"
      onClick={onClose}
    >
      <div
        className="w-full max-w-md rounded-2xl border border-slate-800 bg-slate-950 p-0 shadow-2xl overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-5 py-3 border-b border-slate-800 bg-slate-900/40">
          <h2 className="text-sm font-bold text-slate-100 uppercase tracking-wide">
            프로젝트 전역 옵션
          </h2>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-white transition-colors"
          >
            ✕
          </button>
        </div>

        <div className="p-5 space-y-5">
          <div className="flex items-center gap-3 p-3 bg-blue-900/10 border border-blue-900/30 rounded-2xl">
            <label className="flex items-center gap-3 w-full cursor-pointer">
              <input
                type="checkbox"
                className="w-4 h-4 rounded border-slate-600 bg-slate-800 text-blue-600 focus:ring-offset-0 focus:ring-0"
                checked={optAuto}
                onChange={(e) => setOptAuto(e.target.checked)}
              />
              <div className="flex flex-col">
                <span className="text-sm font-bold text-blue-100">
                  자동 구성 모드(Auto)
                </span>
                <span className="text-[10px] text-blue-300/70">
                  유량 기준으로 엘리먼트 수량을 자동 계산합니다
                </span>
              </div>
            </label>
          </div>

          <div className="space-y-4">
            <div>
              <label className="block text-[10px] font-bold text-slate-400 uppercase mb-1.5">
                기본 멤브레인 모델
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
              <Field label="베셀당 엘리먼트 수">
                <Input
                  disabled={optAuto}
                  className="text-center"
                  value={optSegments}
                  onChange={(e) => setOptSegments(Number(e.target.value))}
                />
              </Field>

              <div className="col-span-1" />

              <Field label="펌프 효율(0-1)">
                <Input
                  disabled={optAuto}
                  className="text-center"
                  value={optPumpEff}
                  step={0.01}
                  onChange={(e) => setOptPumpEff(Number(e.target.value))}
                />
              </Field>

              <Field label="ERD 효율(0-1)">
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
            className="px-5 py-2 bg-slate-100 hover:bg-white text-slate-900 rounded-2xl text-xs font-extrabold transition-colors shadow-lg"
          >
            저장 후 닫기
          </button>
        </div>
      </div>
    </div>
  );
}
