// ui/src/features/simulation/components/FlowModals.tsx

import React, { useEffect, useMemo, useState } from 'react';
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
// 공통: 모달 열렸을 때 Delete/Backspace가 ReactFlow로 새는 걸 캡쳐 단계에서 차단
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
// WAVE-style ionic analysis
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
// Helper: Ion Row (WAVE-style 4-column view)
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
    <div className="grid grid-cols-[44px_1fr_78px_78px] gap-2 items-center px-2 py-1 rounded-md bg-slate-950/60 border border-slate-800 hover:border-slate-700 transition-colors">
      <div className="text-[11px] font-semibold text-slate-300">
        {def.label}
      </div>

      <input
        type="number"
        className="w-full bg-transparent text-right text-[12px] text-slate-100 outline-none font-mono tabular-nums"
        value={value ?? ''}
        placeholder="0"
        onFocus={(e) => e.currentTarget.select()}
        onChange={(e) => {
          const raw = e.target.value;
          const v = raw === '' ? 0 : Number(raw);
          onChange(Number.isFinite(v) ? v : 0);
        }}
      />

      <div className="text-right text-[10px] font-mono text-slate-400 tabular-nums">
        {showDerived ? ppm.toFixed(1) : '—'}
      </div>

      <div className="text-right text-[10px] font-mono text-slate-400 tabular-nums">
        {showDerived ? meqL.toFixed(4) : '—'}
      </div>
    </div>
  );
}

function StatCard({
  label,
  value,
  unit,
  tone = 'default',
}: {
  label: string;
  value: string;
  unit?: string;
  tone?: 'default' | 'good' | 'warn';
}) {
  const toneCls =
    tone === 'good'
      ? 'text-emerald-300'
      : tone === 'warn'
        ? 'text-amber-300'
        : 'text-slate-200';

  return (
    <div className="px-3 py-2 rounded-lg border border-slate-800 bg-slate-950/40">
      <div className="text-[10px] text-slate-500 uppercase tracking-wider">
        {label}
      </div>
      <div className={`text-sm font-mono ${toneCls} tabular-nums`}>
        {value}{' '}
        {unit ? (
          <span className="text-[10px] text-slate-500">{unit}</span>
        ) : null}
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

  // ✅ 훅 순서 고정
  useBlockDeleteKeysWhenOpen(isOpen);

  const [localFeed, setLocalFeed] = useState<any>(feed);
  const [localChem, setLocalChem] = useState<any>(feedChemistry || {});
  const [localCfg, setLocalCfg] = useState<any>(null);
  const [quick, setQuick] = useState({ nacl_mgL: 0, mgso4_mgL: 0 });

  // ✅ “필요할 때만 펼치기” 열렸을 때만 스크롤 허용
  const [detailsOpen, setDetailsOpen] = useState(false);

  const isFeedNode = selEndpoint?.data.role === 'feed';
  const isProductNode = selEndpoint?.data.role === 'product';

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
    setDetailsOpen(false);

    if (selUnit && (selUnit.data as any).type === 'unit') {
      setLocalCfg(JSON.parse(JSON.stringify((selUnit.data as any).cfg)));
    } else {
      setLocalCfg(null);
    }
  }, [isOpen, selEndpoint?.id, selUnit?.id, feed, feedChemistry]);

  // 파생값
  const derived = useMemo(() => {
    const cationSum = sumMgL(localChem, CATIONS);
    const anionSum = sumMgL(localChem, ANIONS);
    const neutralSum = sumMgL(localChem, NEUTRALS);
    const totalTDS = cationSum + anionSum + neutralSum;

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

    // Conductivity (uS/cm) — 초기 근사
    const estConductivity_uScm = totalTDS * 1.7;

    return {
      cationSum,
      anionSum,
      neutralSum,
      totalTDS,
      cationMeq,
      anionMeq,
      chargeBalance_meqL,
      calcHardness,
      calcAlkalinity,
      estConductivity_uScm,
    };
  }, [localChem]);

  // ✅ 훅 호출 이후에만 조건부 return
  if (!isOpen || (!selEndpoint && !selUnit)) return null;

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
    if (isFeedNode) {
      const chemOut = {
        ...localChem,
        alkalinity_mgL_as_CaCO3: derived.calcAlkalinity,
        calcium_hardness_mgL_as_CaCO3: derived.calcHardness,
      };

      setFeed({ ...localFeed, tds_mgL: derived.totalTDS });
      setFeedChemistry(chemOut);
    } else if (selUnit && localCfg) {
      updateUnitCfg(selUnit.id, localCfg, setNodes);
    }
    onClose();
  };

  // ✅ Feed 모달은 크게(한 페이지 구성), 스크롤은 “상세 펼침” 시에만
  const modalShellClass = isFeedNode
    ? 'w-[calc(100vw-24px)] h-[calc(100vh-24px)] max-w-[1680px]'
    : 'w-[1040px] max-h-[85vh]';

  const bodyClass = isFeedNode
    ? detailsOpen
      ? 'flex-1 overflow-y-auto p-4 scrollbar-thin scrollbar-thumb-slate-700 scrollbar-track-transparent'
      : 'flex-1 overflow-hidden p-4'
    : 'flex-1 overflow-y-auto p-5 scrollbar-thin scrollbar-thumb-slate-700 scrollbar-track-transparent';

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-[2px]"
      onClick={onClose}
    >
      <div
        className={`${modalShellClass} flex flex-col rounded-2xl border border-slate-800 bg-slate-950 shadow-2xl ring-1 ring-white/5 overflow-hidden`}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3 border-b border-slate-800 bg-slate-900/50 shrink-0">
          <div className="flex items-center gap-2">
            <div
              className={`w-2 h-2 rounded-full ${
                selEndpoint ? 'bg-blue-500' : 'bg-emerald-500'
              }`}
            />
            <h2 className="text-sm font-bold text-slate-100 tracking-wide">
              {isFeedNode
                ? '원수(Feed) 수질 입력'
                : selUnit
                  ? `${(selUnit.data as UnitData).kind} 설정`
                  : '설정'}
            </h2>
            {isFeedNode ? (
              <span className="text-[11px] text-slate-500">
                (이온 조성 → TDS/경도/알칼리도 자동 계산)
              </span>
            ) : null}
          </div>

          <div className="flex items-center gap-2">
            {isProductNode ? (
              <button
                onClick={onClose}
                className="px-3 py-1 rounded text-xs font-medium text-slate-300 bg-slate-800 border border-slate-700 hover:bg-slate-700"
              >
                닫기
              </button>
            ) : (
              <>
                <button
                  onClick={onClose}
                  className="px-3 py-1 rounded text-xs font-medium text-slate-400 hover:text-slate-200 transition-colors"
                >
                  취소
                </button>
                <button
                  onClick={handleApply}
                  className="px-4 py-1 rounded text-xs font-bold text-white bg-blue-600 hover:bg-blue-500 shadow-lg shadow-blue-900/20 transition-all active:scale-95"
                >
                  적용
                </button>
              </>
            )}
          </div>
        </div>

        {/* Body */}
        <div className={bodyClass}>
          {isFeedNode ? (
            <div className="space-y-3">
              {/* 상단: 프리셋 + 기본 입력 */}
              <div className="grid grid-cols-12 gap-3">
                {/* Preset */}
                <div className="col-span-12 lg:col-span-7 p-3 rounded-xl border border-slate-800 bg-slate-950/30">
                  <div className="flex items-center justify-between mb-2">
                    <div className="text-[11px] font-bold text-slate-300 tracking-wider">
                      🌊 프리셋 라이브러리
                    </div>
                    <div className="text-[10px] text-slate-500">
                      표준 조성 불러오기
                    </div>
                  </div>
                  <select
                    className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-blue-500 cursor-pointer"
                    onChange={(e) => applyPreset(e.target.value)}
                    defaultValue=""
                  >
                    <option value="" disabled>
                      -- 물 조성 선택 --
                    </option>
                    <optgroup label="Seawater">
                      {WATER_CATALOG.filter(
                        (w) => w.category === 'Seawater',
                      ).map((w) => (
                        <option key={w.id} value={w.id}>
                          {w.name}
                        </option>
                      ))}
                    </optgroup>
                    <optgroup label="Brackish Water">
                      {WATER_CATALOG.filter(
                        (w) => w.category === 'Brackish',
                      ).map((w) => (
                        <option key={w.id} value={w.id}>
                          {w.name}
                        </option>
                      ))}
                    </optgroup>
                    <optgroup label="Wastewater & Reuse">
                      {WATER_CATALOG.filter((w) =>
                        ['Waste', 'Reuse'].includes(w.category),
                      ).map((w) => (
                        <option key={w.id} value={w.id}>
                          {w.name}
                        </option>
                      ))}
                    </optgroup>
                  </select>
                </div>

                {/* 핵심 값 + Quick Entry */}
                <div className="col-span-12 lg:col-span-5 p-3 rounded-xl border border-slate-800 bg-slate-950/30">
                  <div className="grid grid-cols-2 gap-2">
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

                    <Field label="pH (25°C 기준)">
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
                      <Field label={`유량 (${unitLabel('flow', unitMode)})`}>
                        <Input
                          className="h-9 font-bold text-emerald-300 text-right font-mono"
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

                  {/* Quick Entry */}
                  <div className="mt-3 pt-3 border-t border-slate-800/80">
                    <div className="flex items-center justify-between mb-2">
                      <div className="text-[11px] font-bold text-slate-300 tracking-wider">
                        ⚡ 빠른 입력(염)
                      </div>
                      <div className="text-[10px] text-slate-500">
                        입력값을 이온에 분배
                      </div>
                    </div>

                    <div className="grid grid-cols-2 gap-2">
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

                      <div className="col-span-2 flex justify-end">
                        <button
                          onClick={applyQuickEntry}
                          className="px-3 py-1.5 rounded-md text-xs font-bold text-white bg-slate-700 hover:bg-slate-600 border border-slate-600"
                        >
                          이온에 적용
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              {/* 통계 */}
              <div className="grid grid-cols-2 lg:grid-cols-6 gap-2">
                <StatCard
                  label="TDS"
                  value={derived.totalTDS.toFixed(2)}
                  unit="mg/L"
                  tone="good"
                />
                <StatCard
                  label="경도(Hardness)"
                  value={derived.calcHardness.toFixed(1)}
                  unit="as CaCO3"
                />
                <StatCard
                  label="알칼리도(Alkalinity)"
                  value={derived.calcAlkalinity.toFixed(1)}
                  unit="as CaCO3"
                />
                <StatCard
                  label="전하 밸런스"
                  value={derived.chargeBalance_meqL.toFixed(6)}
                  unit="meq/L"
                  tone={
                    Math.abs(derived.chargeBalance_meqL) > 0.5
                      ? 'warn'
                      : 'default'
                  }
                />
                <StatCard
                  label="전도도(추정)"
                  value={derived.estConductivity_uScm.toFixed(1)}
                  unit="µS/cm"
                />
                <StatCard
                  label="meq 합"
                  value={`C ${derived.cationMeq.toFixed(3)} / A ${derived.anionMeq.toFixed(3)}`}
                />
              </div>

              {/* 이온 조성 */}
              <div className="grid grid-cols-12 gap-3">
                <div className="col-span-12 flex items-end justify-between">
                  <div className="flex items-center gap-2">
                    <div className="w-1.5 h-4 rounded bg-blue-500" />
                    <h3 className="text-sm font-bold text-slate-200">
                      이온 조성 입력(전체)
                    </h3>
                  </div>
                  <div className="text-[10px] text-slate-500">
                    mg/L 입력 · CaCO3 환산(ppm) · meq/L 자동 계산
                  </div>
                </div>

                {/* Cations */}
                <div className="col-span-12 lg:col-span-4 p-3 rounded-xl border border-slate-800 bg-slate-950/25">
                  <div className="flex items-center justify-between mb-2">
                    <div className="text-[11px] font-bold text-blue-300 uppercase tracking-wider">
                      Cations (+)
                    </div>
                    <div className="text-[11px] font-mono text-slate-400 tabular-nums">
                      {derived.cationSum.toFixed(2)} mg/L
                    </div>
                  </div>
                  <div className="grid grid-cols-[44px_1fr_78px_78px] gap-2 px-2 mb-2 text-[10px] text-slate-500 uppercase tracking-wider">
                    <div>Ion</div>
                    <div className="text-right">mg/L</div>
                    <div className="text-right">ppm CaCO3</div>
                    <div className="text-right">meq/L</div>
                  </div>
                  <div className="space-y-1">
                    {CATIONS.map((d) => (
                      <IonRow
                        key={d.key}
                        def={d}
                        value={localChem?.[d.key]}
                        onChange={(v) =>
                          setLocalChem({ ...localChem, [d.key]: v })
                        }
                        showDerived
                      />
                    ))}
                  </div>
                </div>

                {/* Anions */}
                <div className="col-span-12 lg:col-span-4 p-3 rounded-xl border border-slate-800 bg-slate-950/25">
                  <div className="flex items-center justify-between mb-2">
                    <div className="text-[11px] font-bold text-rose-300 uppercase tracking-wider">
                      Anions (-)
                    </div>
                    <div className="text-[11px] font-mono text-slate-400 tabular-nums">
                      {derived.anionSum.toFixed(2)} mg/L
                    </div>
                  </div>
                  <div className="grid grid-cols-[44px_1fr_78px_78px] gap-2 px-2 mb-2 text-[10px] text-slate-500 uppercase tracking-wider">
                    <div>Ion</div>
                    <div className="text-right">mg/L</div>
                    <div className="text-right">ppm CaCO3</div>
                    <div className="text-right">meq/L</div>
                  </div>
                  <div className="space-y-1">
                    {ANIONS.map((d) => (
                      <IonRow
                        key={d.key}
                        def={d}
                        value={localChem?.[d.key]}
                        onChange={(v) =>
                          setLocalChem({ ...localChem, [d.key]: v })
                        }
                        showDerived
                      />
                    ))}
                  </div>
                </div>

                {/* Neutrals */}
                <div className="col-span-12 lg:col-span-4 p-3 rounded-xl border border-slate-800 bg-slate-950/25">
                  <div className="flex items-center justify-between mb-2">
                    <div className="text-[11px] font-bold text-emerald-300 uppercase tracking-wider">
                      Neutrals
                    </div>
                    <div className="text-[11px] font-mono text-slate-400 tabular-nums">
                      {derived.neutralSum.toFixed(2)} mg/L
                    </div>
                  </div>
                  <div className="grid grid-cols-[44px_1fr_78px_78px] gap-2 px-2 mb-2 text-[10px] text-slate-500 uppercase tracking-wider">
                    <div>Ion</div>
                    <div className="text-right">mg/L</div>
                    <div className="text-right">ppm CaCO3</div>
                    <div className="text-right">meq/L</div>
                  </div>
                  <div className="space-y-1">
                    {NEUTRALS.map((d) => (
                      <IonRow
                        key={d.key}
                        def={d}
                        value={localChem?.[d.key]}
                        onChange={(v) =>
                          setLocalChem({ ...localChem, [d.key]: v })
                        }
                        showDerived={false}
                      />
                    ))}
                  </div>
                </div>
              </div>

              {/* ✅ 상세 입력(필요할 때만 펼치기) : 열릴 때 detailsOpen=true → 그때만 스크롤 생김 */}
              <details
                className="rounded-xl border border-slate-800 bg-slate-950/20"
                open={detailsOpen}
                onToggle={(e) =>
                  setDetailsOpen((e.currentTarget as HTMLDetailsElement).open)
                }
              >
                <summary className="cursor-pointer select-none px-3 py-2 text-sm font-semibold text-slate-200 flex items-center justify-between">
                  <span>상세 입력(수질 메타/고형물/메모)</span>
                  <span className="text-[11px] text-slate-500">
                    (필요할 때만 펼치기)
                  </span>
                </summary>

                <div className="px-3 pb-3 pt-1 space-y-3">
                  <div className="grid grid-cols-12 gap-3">
                    <div className="col-span-12 lg:col-span-8 p-3 rounded-xl border border-slate-800 bg-slate-950/20">
                      <div className="grid grid-cols-12 gap-3">
                        <div className="col-span-12 md:col-span-6">
                          <Field label="Water Type(선택)">
                            <Input
                              className="h-9"
                              value={localFeed.water_type ?? ''}
                              placeholder="예) Seawater"
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
                          <Field label="Water Sub-type(선택)">
                            <Input
                              className="h-9"
                              value={localFeed.water_subtype ?? ''}
                              placeholder="예) Open intake"
                              onChange={(e) =>
                                setLocalFeed({
                                  ...localFeed,
                                  water_subtype: e.target.value,
                                })
                              }
                            />
                          </Field>
                        </div>

                        <div className="col-span-12 md:col-span-4">
                          <Field label="온도 최소(°C)">
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
                          <Field label="설계 온도(°C)">
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
                          <Field label="온도 최대(°C)">
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
                          <Field label="추가 메모(선택)">
                            <textarea
                              className="w-full h-20 bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-blue-500"
                              value={localFeed.feed_note ?? ''}
                              placeholder="예) 계절 변동, 취수 조건, 전처리 특이사항 등"
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
                    </div>

                    <div className="col-span-12 lg:col-span-4 p-3 rounded-xl border border-slate-800 bg-slate-950/20">
                      <div className="text-[11px] font-bold text-slate-300 tracking-wider mb-2">
                        고형물 / 유기물(선택)
                      </div>
                      <div className="grid grid-cols-2 gap-2">
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
                        <Field label="TSS(mg/L)">
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
                        <Field label="TOC(mg/L)">
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
                </div>
              </details>
            </div>
          ) : selUnit && localCfg ? (
            (() => {
              const u = selUnit.data as UnitData;
              const kind = u.kind as UnitKind;
              const proxyUnit = { ...u, cfg: localCfg };
              const updateCfg = (newCfg: any) => setLocalCfg(newCfg);

              if (kind === 'HRRO')
                return <HRROEditor node={proxyUnit} onChange={updateCfg} />;
              if (kind === 'RO')
                return (
                  <ROEditor node={proxyUnit} onChange={updateCfg as any} />
                );
              if (kind === 'UF')
                return (
                  <UFEditor node={proxyUnit} onChange={updateCfg as any} />
                );
              if (kind === 'NF')
                return (
                  <NFEditor node={proxyUnit} onChange={updateCfg as any} />
                );
              if (kind === 'MF')
                return (
                  <MFEditor node={proxyUnit} onChange={updateCfg as any} />
                );
              if (kind === 'PUMP')
                return (
                  <PumpEditor node={proxyUnit as any} onChange={updateCfg} />
                );

              return (
                <div className="text-sm text-red-300">
                  Unknown Unit Type: {kind}
                </div>
              );
            })()
          ) : isProductNode ? (
            <div className="h-full flex flex-col items-center justify-center text-slate-500 opacity-60">
              <div className="text-4xl mb-2">🏁</div>
              <p className="text-sm font-medium">최종 생산수(Product)</p>
              <p className="text-xs">시뮬레이션 실행 후 결과가 표시됩니다.</p>
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
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-[2px]"
      onClick={onClose}
    >
      <div
        className="w-full max-w-md rounded-xl border border-slate-700 bg-slate-950 p-0 shadow-2xl overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-5 py-3 border-b border-slate-800 bg-slate-900/50">
          <h2 className="text-sm font-bold text-slate-100 tracking-wide">
            전역 옵션(Global)
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
                  자동 설정 모드
                </span>
                <span className="text-[10px] text-blue-300/70">
                  유량 기반으로 소자 수를 자동 계산
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
              <Field label="Vessel 당 Elements">
                <Input
                  disabled={optAuto}
                  className="text-center"
                  value={optSegments}
                  onChange={(e) => setOptSegments(Number(e.target.value))}
                />
              </Field>
              <div className="col-span-1" />
              <Field label="펌프 효율 (0-1)">
                <Input
                  disabled={optAuto}
                  className="text-center"
                  value={optPumpEff}
                  step={0.01}
                  onChange={(e) => setOptPumpEff(Number(e.target.value))}
                />
              </Field>
              <Field label="ERD 효율 (0-1)">
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
            저장 & 닫기
          </button>
        </div>
      </div>
    </div>
  );
}
