// ui/src/features/simulation/components/FlowModals.tsx

import React, { useEffect, useLayoutEffect, useRef, useState } from 'react';
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

function roundTo(v: number, dp: number): number {
  const p = Math.pow(10, dp);
  return Math.round(v * p) / p;
}

function fmtNumber(v: any, dp = 1): string {
  const x = Number(v);
  if (!Number.isFinite(x)) return '0';
  const s = x.toFixed(dp);
  return s.replace(/\.0+$/, '');
}

function fmtInputNumber(v: any, maxDp = 3): string {
  if (v === '' || v === null || v === undefined) return '';
  const x = Number(v);
  if (!Number.isFinite(x)) return '';
  const s = x.toFixed(maxDp);
  return s.replace(/\.?0+$/, '');
}

// mg/L -> meq/L
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
// WAVE-style Charge Balance Adjustment (옵션 A 구현)
// ------------------------------------------------------------------
type ChargeBalanceMode = 'off' | 'anions' | 'cations' | 'all';

type ChargeBalanceMeta = {
  mode: ChargeBalanceMode;
  raw_c_meq: number;
  raw_a_meq: number;
  raw_delta_meq: number;
  adj_c_meq: number;
  adj_a_meq: number;
  adj_delta_meq: number;
  adjustments_mgL: Record<string, number>; // key -> (adj - raw)
  note?: string;
};

function cloneChem(chem: any): any {
  return JSON.parse(JSON.stringify(chem ?? {}));
}

// deltaMeq를 특정 이온에 반영 (mg/L로 환산해서 더/빼기)
function applyDeltaMeqToIon(
  chem: any,
  ionKey: string,
  mw: number,
  z: number,
  deltaMeq: number,
): { remainingMeq: number; appliedMgL: number } {
  const absz = Math.abs(z) || 1;
  const mgDelta = (deltaMeq * mw) / absz;

  const before = n0(chem?.[ionKey]);
  const after = Math.max(0, before + mgDelta);

  chem[ionKey] = roundTo(after, 3);

  const appliedMgL = after - before; // can be negative
  // ✅ signed meq change (appliedMgL can be negative)
  const appliedMeqSigned = (appliedMgL / (mw || 1)) * absz;

  return { remainingMeq: deltaMeq - appliedMeqSigned, appliedMgL };
}

function diffAdjustmentsMgL(
  raw: any,
  adj: any,
  keys: string[],
): Record<string, number> {
  const out: Record<string, number> = {};
  for (const k of keys) {
    const dv = roundTo(n0(adj?.[k]) - n0(raw?.[k]), 3);
    if (Math.abs(dv) >= 0.001) out[k] = dv;
  }
  return out;
}

// Anions만 조정
function adjustAnionsToBalance(chemRaw: any): { chemAdj: any; note?: string } {
  const chem = cloneChem(chemRaw);

  const c = sumMeqL(chem, CATIONS);
  const a = sumMeqL(chem, ANIONS);
  const delta = c - a; // +면 anions가 부족, -면 anions가 과잉

  const order: IonDef[] = [
    ANIONS.find((x) => x.label === 'Cl')!,
    ANIONS.find((x) => x.label === 'HCO3')!,
    ANIONS.find((x) => x.label === 'SO4')!,
    ANIONS.find((x) => x.label === 'NO3')!,
    ANIONS.find((x) => x.label === 'Br')!,
    ANIONS.find((x) => x.label === 'CO3')!,
    ANIONS.find((x) => x.label === 'PO4')!,
    ANIONS.find((x) => x.label === 'F')!,
  ].filter(Boolean) as IonDef[];

  let remaining = delta; // anions meq change needed (signed)
  for (const ion of order) {
    if (Math.abs(remaining) < 1e-6) break;
    const r = applyDeltaMeqToIon(chem, ion.key, ion.mw, ion.z, remaining);
    remaining = r.remainingMeq;
  }

  let note: string | undefined;
  if (Math.abs(remaining) >= 1e-3) {
    note = '전하 보정(Anions)에서 일부 잔여 오차가 남았습니다(클램핑/0 하한).';
  }
  return { chemAdj: chem, note };
}

// Cations만 조정
function adjustCationsToBalance(chemRaw: any): { chemAdj: any; note?: string } {
  const chem = cloneChem(chemRaw);

  const c = sumMeqL(chem, CATIONS);
  const a = sumMeqL(chem, ANIONS);
  const delta = c - a; // +면 cations 과잉, -면 cations 부족

  // 목표: cations 변화량 = (a - c) = -delta
  let remaining = -delta;

  const order: IonDef[] = [
    CATIONS.find((x) => x.label === 'Na')!,
    CATIONS.find((x) => x.label === 'Ca')!,
    CATIONS.find((x) => x.label === 'Mg')!,
    CATIONS.find((x) => x.label === 'K')!,
    CATIONS.find((x) => x.label === 'NH4')!,
    CATIONS.find((x) => x.label === 'Sr')!,
    CATIONS.find((x) => x.label === 'Ba')!,
    CATIONS.find((x) => x.label === 'Fe')!,
    CATIONS.find((x) => x.label === 'Mn')!,
  ].filter(Boolean) as IonDef[];

  for (const ion of order) {
    if (Math.abs(remaining) < 1e-6) break;
    const r = applyDeltaMeqToIon(chem, ion.key, ion.mw, ion.z, remaining);
    remaining = r.remainingMeq;
  }

  let note: string | undefined;
  if (Math.abs(remaining) >= 1e-3) {
    note = '전하 보정(Cations)에서 일부 잔여 오차가 남았습니다(클램핑/0 하한).';
  }
  return { chemAdj: chem, note };
}

// All(스케일)
function adjustAllScaleToBalance(chemRaw: any): {
  chemAdj: any;
  note?: string;
} {
  const chem = cloneChem(chemRaw);

  const c = sumMeqL(chem, CATIONS);
  const a = sumMeqL(chem, ANIONS);

  if (c <= 0 && a <= 0) return { chemAdj: chem };
  if (c > 0 && a > 0) {
    const target = (c + a) / 2;
    const sC = target / c;
    const sA = target / a;

    for (const d of CATIONS) chem[d.key] = roundTo(n0(chem[d.key]) * sC, 3);
    for (const d of ANIONS) chem[d.key] = roundTo(n0(chem[d.key]) * sA, 3);
    return { chemAdj: chem };
  }

  if (c > 0 && a <= 0) return adjustAnionsToBalance(chemRaw);
  return adjustCationsToBalance(chemRaw);
}

function applyChargeBalance(
  chemRaw: any,
  mode: ChargeBalanceMode,
): { chemUsed: any; meta: ChargeBalanceMeta } {
  const rawC = sumMeqL(chemRaw, CATIONS);
  const rawA = sumMeqL(chemRaw, ANIONS);
  const rawDelta = rawC - rawA;

  let chemAdj = cloneChem(chemRaw);
  let note: string | undefined;

  if (mode === 'anions') {
    const r = adjustAnionsToBalance(chemRaw);
    chemAdj = r.chemAdj;
    note = r.note;
  } else if (mode === 'cations') {
    const r = adjustCationsToBalance(chemRaw);
    chemAdj = r.chemAdj;
    note = r.note;
  } else if (mode === 'all') {
    const r = adjustAllScaleToBalance(chemRaw);
    chemAdj = r.chemAdj;
    note = r.note;
  } else {
    chemAdj = cloneChem(chemRaw);
  }

  const adjC = sumMeqL(chemAdj, CATIONS);
  const adjA = sumMeqL(chemAdj, ANIONS);
  const adjDelta = adjC - adjA;

  const allKeys = [
    ...CATIONS.map((d) => d.key),
    ...ANIONS.map((d) => d.key),
    ...NEUTRALS.map((d) => d.key),
  ];

  const adjustments_mgL = diffAdjustmentsMgL(chemRaw, chemAdj, allKeys);

  const meta: ChargeBalanceMeta = {
    mode,
    raw_c_meq: rawC,
    raw_a_meq: rawA,
    raw_delta_meq: rawDelta,
    adj_c_meq: adjC,
    adj_a_meq: adjA,
    adj_delta_meq: adjDelta,
    adjustments_mgL,
    note,
  };

  const chemUsed = mode === 'off' ? chemRaw : chemAdj;
  return { chemUsed, meta };
}

// ------------------------------------------------------------------
// Compact Ion Table (WAVE-like)
// ------------------------------------------------------------------
function IonTable({
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
                className={`grid grid-cols-4 gap-2 items-center px-2 ${compact ? 'py-[5px]' : 'py-1'} rounded border border-slate-800/70 bg-slate-950/40 hover:border-slate-700 transition-colors`}
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

    water_type?: string | null;
    water_subtype?: string | null;
    turbidity_ntu?: number | null;
    tss_mgL?: number | null;
    sdi15?: number | null;
    toc_mgL?: number | null;

    temp_min_C?: number | null;
    temp_max_C?: number | null;
    feed_note?: string | null;

    // (옵션) UI 설정 저장용
    charge_balance_mode?: ChargeBalanceMode | null;

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

const WATER_TYPE_OPTIONS = [
  { value: '해수', label: '해수' },
  { value: '기수', label: '기수/지하수' },
  { value: '지표수', label: '지표수(강/호수)' },
  { value: '폐수', label: '폐수(산업/공정)' },
  { value: '재이용수', label: '재이용수(하수처리수)' },
];

function categoryToWaterType(category: string | undefined | null): string {
  if (category === 'Seawater') return '해수';
  if (category === 'Brackish') return '기수';
  if (category === 'Surface') return '지표수';
  if (category === 'Waste') return '폐수';
  if (category === 'Reuse') return '재이용수';
  return '기수';
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
  const [detailsOpen, setDetailsOpen] = useState(false);

  // ✅ “한 화면 맞춤” 모드
  const [fitMode, setFitMode] = useState(true);
  const [fitScale, setFitScale] = useState(1);

  // ✅ 글씨 너무 작아지는 문제 방지: minScale 이하로는 스크롤 허용
  const [fitNeedsScroll, setFitNeedsScroll] = useState(false);

  const bodyRef = useRef<HTMLDivElement | null>(null);
  const contentRef = useRef<HTMLDivElement | null>(null);

  // ✅ 전하 보정 모드 (WAVE)
  const [cbMode, setCbMode] = useState<ChargeBalanceMode>('anions');

  useEffect(() => {
    if (!isOpen) return;

    const minT = (feed as any)?.temp_min_C ?? feed.temperature_C;
    const maxT = (feed as any)?.temp_max_C ?? feed.temperature_C;

    setLocalFeed({
      ...feed,
      water_type: feed?.water_type == null ? '' : String(feed.water_type),
      water_subtype:
        feed?.water_subtype == null ? '' : String(feed.water_subtype),
      temp_min_C: minT,
      temp_max_C: maxT,
      feed_note: (feed as any)?.feed_note ?? '',
    });

    setLocalChem(feedChemistry || {});
    setQuick({ nacl_mgL: 0, mgso4_mgL: 0 });
    setDetailsOpen(false);

    const saved = (feed as any)?.charge_balance_mode as
      | ChargeBalanceMode
      | undefined;
    setCbMode(saved ?? 'anions');

    if (selUnit && (selUnit.data as any).type === 'unit') {
      setLocalCfg(JSON.parse(JSON.stringify((selUnit.data as any).cfg)));
    } else {
      setLocalCfg(null);
    }

    setFitScale(1);
    setFitNeedsScroll(false);
  }, [isOpen, selEndpoint?.id, selUnit?.id, feed, feedChemistry]);

  // ✅ Fit 스케일 계산
  const fitActive = fitMode && !detailsOpen;

  useLayoutEffect(() => {
    if (!isOpen) return;

    if (!fitActive) {
      setFitScale(1);
      setFitNeedsScroll(false);
      return;
    }

    const body = bodyRef.current;
    const content = contentRef.current;
    if (!body || !content) return;

    const minScale = 0.85; // ✅ 가독성 최소 배율(추천: 0.85~0.9)

    const compute = () => {
      const b = bodyRef.current;
      const c = contentRef.current;
      if (!b || !c) return;

      const availH = Math.max(0, b.clientHeight - 8);
      const availW = Math.max(0, b.clientWidth - 8);

      // ✅ transform scale은 scrollWidth/Height에 영향 거의 없음(=unscaled 기준)
      const needH = c.scrollHeight;
      const needW = c.scrollWidth;

      if (needH <= 0 || needW <= 0 || availH <= 0 || availW <= 0) return;

      const sH = availH / needH;
      const sW = availW / needW;
      const raw = Math.min(1, sH, sW) * 0.98;

      const needsScroll = raw < minScale;

      if (needsScroll) {
        setFitNeedsScroll(true);
        setFitScale(1);
      } else {
        setFitNeedsScroll(false);
        setFitScale(raw);
      }

      // ✅ 스케일 모드(스크롤 없음)에서는 열릴 때 위로 리셋
      requestAnimationFrame(() => {
        const bb = bodyRef.current;
        if (!bb) return;
        if (!needsScroll) {
          bb.scrollTop = 0;
          bb.scrollLeft = 0;
        }
      });
    };

    compute();

    const ro = new ResizeObserver(() => compute());
    ro.observe(body);
    ro.observe(content);

    window.addEventListener('resize', compute);
    return () => {
      ro.disconnect();
      window.removeEventListener('resize', compute);
    };
  }, [isOpen, fitActive]);

  if (!isOpen || (!selEndpoint && !selUnit)) return null;

  const isFeedNode = selEndpoint?.data.role === 'feed';
  const isProductNode = selEndpoint?.data.role === 'product';

  // ✅ 전하 보정 적용 (KPI/Apply에 사용)
  const { chemUsed, meta: cbMeta } = applyChargeBalance(localChem, cbMode);

  // ✅ 원본 기준(참고용)
  const rawCationSum = sumMgL(localChem, CATIONS);
  const rawAnionSum = sumMgL(localChem, ANIONS);
  const rawNeutralSum = sumMgL(localChem, NEUTRALS);
  const rawTotalTDS = rawCationSum + rawAnionSum + rawNeutralSum;

  const rawCationMeq = sumMeqL(localChem, CATIONS);
  const rawAnionMeq = sumMeqL(localChem, ANIONS);
  const rawChargeBalance_meqL = rawCationMeq - rawAnionMeq;

  // ✅ 보정/사용 기준
  const cationSum = sumMgL(chemUsed, CATIONS);
  const anionSum = sumMgL(chemUsed, ANIONS);
  const neutralSum = sumMgL(chemUsed, NEUTRALS);
  const totalTDS = cationSum + anionSum + neutralSum;

  const cationMeq = sumMeqL(chemUsed, CATIONS);
  const anionMeq = sumMeqL(chemUsed, ANIONS);
  const chargeBalance_meqL = cationMeq - anionMeq;

  const ca_meq = mgL_to_meqL(n0(chemUsed?.ca_mgL), MW.Ca, +2);
  const mg_meq = mgL_to_meqL(n0(chemUsed?.mg_mgL), MW.Mg, +2);
  const calcHardness = (ca_meq + mg_meq) * 50.0;

  const hco3_meq = mgL_to_meqL(n0(chemUsed?.hco3_mgL), MW.HCO3, -1);
  const co3_meq = mgL_to_meqL(n0(chemUsed?.co3_mgL), MW.CO3, -2);
  const calcAlkalinity = (hco3_meq + co3_meq) * 50.0;

  const estConductivity_uScm = totalTDS * 1.7;

  const subtypeSuggestions = (() => {
    const wt = String(localFeed?.water_type ?? '');
    if (!wt) return [];
    const cats: Record<string, string> = {
      해수: 'Seawater',
      기수: 'Brackish',
      지표수: 'Surface',
      폐수: 'Waste',
      재이용수: 'Reuse',
    };
    const cat = cats[wt];
    if (!cat) return [];
    return WATER_CATALOG.filter((p) => p.category === (cat as any)).map(
      (p) => p.name,
    );
  })();

  const applyPreset = (presetId: string) => {
    const preset = WATER_CATALOG.find((p) => p.id === presetId);
    if (!preset) return;

    const ions = preset.ions;
    const calcTDS = Object.values(ions).reduce((sum, v) => sum + (v || 0), 0);

    const wt =
      (preset as any).water_type ?? categoryToWaterType(preset.category);
    const ws = (preset as any).water_subtype ?? preset.name;

    setLocalFeed((prev: any) => ({
      ...prev,
      temperature_C: preset.temp_C,
      ph: preset.ph,
      water_type: wt,
      water_subtype: ws,
      tds_mgL: calcTDS,
      temp_min_C: prev?.temp_min_C ?? preset.temp_C,
      temp_max_C: prev?.temp_max_C ?? preset.temp_C,
      feed_note: (prev?.feed_note ?? '').trim()
        ? prev.feed_note
        : `${preset.desc}`,
    }));

    const r3 = (x: any) => roundTo(n0(x), 3);

    setLocalChem({
      nh4_mgL: r3(ions.NH4),
      k_mgL: r3(ions.K),
      na_mgL: r3(ions.Na),
      mg_mgL: r3(ions.Mg),
      ca_mgL: r3(ions.Ca),
      sr_mgL: r3(ions.Sr),
      ba_mgL: r3(ions.Ba),
      fe_mgL: r3(ions.Fe),
      mn_mgL: r3(ions.Mn),

      hco3_mgL: r3(ions.HCO3),
      no3_mgL: r3(ions.NO3),
      cl_mgL: r3(ions.Cl),
      f_mgL: r3(ions.F),
      so4_mgL: r3(ions.SO4),
      br_mgL: r3(ions.Br),
      po4_mgL: r3(ions.PO4),
      co3_mgL: r3(ions.CO3),

      sio2_mgL: r3(ions.SiO2),
      b_mgL: r3(ions.B),
      co2_mgL: r3(ions.CO2),

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
      na_mgL: roundTo(n0(prev?.na_mgL) + addNa, 3),
      cl_mgL: roundTo(n0(prev?.cl_mgL) + addCl, 3),
      mg_mgL: roundTo(n0(prev?.mg_mgL) + addMg, 3),
      so4_mgL: roundTo(n0(prev?.so4_mgL) + addSO4, 3),
    }));

    setQuick({ nacl_mgL: 0, mgso4_mgL: 0 });
  };

  // ✅ WAVE처럼 “표에 반영”(입력값 자체를 보정값으로 덮어쓰기)
  const applyBalanceIntoTable = () => {
    const r = applyChargeBalance(localChem, cbMode);
    if (cbMode === 'off') return;
    setLocalChem({ ...localChem, ...r.chemUsed });
  };

  const handleApply = () => {
    if (isFeedNode) {
      const chemForApply = cbMode === 'off' ? localChem : chemUsed;

      const chemOut = {
        ...chemForApply,
        alkalinity_mgL_as_CaCO3: calcAlkalinity,
        calcium_hardness_mgL_as_CaCO3: calcHardness,
      };

      setFeed({
        ...localFeed,
        tds_mgL: roundTo(totalTDS, 2),
        water_type: (localFeed.water_type ?? '') || null,
        water_subtype: (localFeed.water_subtype ?? '') || null,
        charge_balance_mode: cbMode,
      });
      setFeedChemistry(chemOut);
    } else if (selUnit && localCfg) {
      updateUnitCfg(selUnit.id, localCfg, setNodes);
    }
    onClose();
  };

  const compact = fitActive;

  const cbModeLabel: Record<ChargeBalanceMode, string> = {
    off: 'OFF(원본 그대로)',
    anions: 'Anions(Cl 우선)',
    cations: 'Cations(Na 우선)',
    all: 'All(양·음이온 스케일)',
  };

  const adjustmentText = (() => {
    const entries = Object.entries(cbMeta.adjustments_mgL);
    if (cbMode === 'off' || entries.length === 0) return '';
    const top = entries
      .sort((a, b) => Math.abs(b[1]) - Math.abs(a[1]))
      .slice(0, 4)
      .map(
        ([k, v]) =>
          `${k.replace('_mgL', '')} ${v > 0 ? '+' : ''}${fmtNumber(v, 3)} mg/L`,
      );
    return top.join(', ');
  })();

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-[2px]"
      onClick={onClose}
    >
      <div
        className="w-[min(1420px,96vw)] max-h-[96vh] flex flex-col rounded-xl border border-slate-800 bg-slate-950 shadow-2xl ring-1 ring-white/5 overflow-hidden"
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
                ? '원수(FEED) 수질 분석'
                : selUnit
                  ? `${(selUnit.data as UnitData).kind} 설정`
                  : '설정'}
            </h2>
            {isFeedNode && (
              <span className="text-[11px] text-slate-500">
                (이온 조성 → TDS/경도/알칼리도 자동 계산)
              </span>
            )}
          </div>

          <div className="flex items-center gap-2">
            {isFeedNode && (
              <button
                onClick={() => setFitMode((v) => !v)}
                className={`px-3 py-1 rounded text-xs font-bold border transition-colors ${
                  fitMode
                    ? 'text-emerald-200 bg-emerald-900/20 border-emerald-900/40 hover:bg-emerald-900/30'
                    : 'text-slate-200 bg-slate-800 border-slate-700 hover:bg-slate-700'
                }`}
                title="상세 닫힘 상태에서 화면에 맞게 자동 축소/확대합니다."
              >
                화면 맞춤 {fitMode ? 'ON' : 'OFF'}
              </button>
            )}

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
        <div
          ref={bodyRef}
          className={`flex-1 ${
            fitActive
              ? fitNeedsScroll
                ? 'overflow-auto'
                : 'overflow-hidden'
              : 'overflow-y-auto'
          } ${compact ? 'p-3' : 'p-4'} scrollbar-thin scrollbar-thumb-slate-700 scrollbar-track-transparent`}
        >
          {/* ✅ 핵심 수정:
              contentSize wrapper 제거 (ReferenceError + 찝힘 원인)
              contentRef에만 scale 적용 */}
          <div
            ref={contentRef}
            className={fitActive ? 'mx-auto w-full max-w-full' : 'w-full'}
            style={
              fitActive && !fitNeedsScroll
                ? {
                    transform: `scale(${fitScale})`,
                    transformOrigin: 'top center',
                    width: '100%',
                    maxWidth: '100%',
                  }
                : undefined
            }
          >
            {isFeedNode ? (
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
                        {WATER_CATALOG.filter(
                          (w) => w.category === 'Seawater',
                        ).map((w) => (
                          <option key={w.id} value={w.id}>
                            {w.name}
                          </option>
                        ))}
                      </optgroup>

                      <optgroup label="기수/지하수">
                        {WATER_CATALOG.filter(
                          (w) => w.category === 'Brackish',
                        ).map((w) => (
                          <option key={w.id} value={w.id}>
                            {w.name}
                          </option>
                        ))}
                      </optgroup>

                      <optgroup label="지표수(강/호수)">
                        {WATER_CATALOG.filter(
                          (w) => w.category === 'Surface',
                        ).map((w) => (
                          <option key={w.id} value={w.id}>
                            {w.name}
                          </option>
                        ))}
                      </optgroup>

                      <optgroup label="폐수(산업/공정)">
                        {WATER_CATALOG.filter(
                          (w) => w.category === 'Waste',
                        ).map((w) => (
                          <option key={w.id} value={w.id}>
                            {w.name}
                          </option>
                        ))}
                      </optgroup>

                      <optgroup label="재이용수(하수처리수)">
                        {WATER_CATALOG.filter(
                          (w) => w.category === 'Reuse',
                        ).map((w) => (
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
                            setLocalFeed({
                              ...localFeed,
                              water_type: e.target.value,
                            })
                          }
                        >
                          <option value="">(선택)</option>
                          {WATER_TYPE_OPTIONS.map((o) => (
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
                            setLocalFeed({
                              ...localFeed,
                              water_subtype: e.target.value,
                            })
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
                          setLocalFeed({
                            ...localFeed,
                            feed_note: e.target.value,
                          })
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
                        <Field
                          label={`유입 유량 (${unitLabel('flow', unitMode)})`}
                        >
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
                            className="px-3 py-2 rounded text-xs font-bold text-white bg-slate-700 hover:bg-slate-600 border border-slate-600"
                          >
                            이온에 반영
                          </button>
                        </div>
                      </div>
                    </div>

                    {/* ✅ 전하 보정 (WAVE) */}
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
                          {' · '}
                          원본 Δ(C-A):{' '}
                          <span className="font-mono text-slate-300">
                            {fmtNumber(rawChargeBalance_meqL, 3)}
                          </span>{' '}
                          meq/L
                          {' → '}
                          보정 Δ(C-A):{' '}
                          <span className="font-mono text-emerald-300">
                            {fmtNumber(chargeBalance_meqL, 3)}
                          </span>{' '}
                          meq/L
                        </div>
                        {adjustmentText && (
                          <div className="col-span-12 text-[10px] text-slate-500">
                            보정내용(상위):{' '}
                            <span className="text-slate-300 font-mono">
                              {adjustmentText}
                            </span>
                          </div>
                        )}
                        {cbMeta.note && (
                          <div className="col-span-12 text-[10px] text-amber-300/80">
                            {cbMeta.note}
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
                      {fmtNumber(totalTDS, 1)}{' '}
                      <span className="text-xs font-normal text-slate-600">
                        mg/L
                      </span>
                    </div>
                    {cbMode !== 'off' && (
                      <div className="text-[10px] text-slate-500 mt-1">
                        원본:{' '}
                        <span className="font-mono">
                          {fmtNumber(rawTotalTDS, 1)}
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
                      {fmtNumber(calcHardness, 1)}{' '}
                      <span className="text-xs font-normal text-slate-600">
                        as CaCO3
                      </span>
                    </div>
                  </div>

                  <div className="col-span-12 md:col-span-4 bg-slate-900/55 border border-slate-800 rounded-lg p-3">
                    <div className="text-[10px] font-bold text-slate-500 uppercase">
                      알칼리도(Alkalinity)
                    </div>
                    <div className="text-xl font-mono text-blue-300 font-semibold">
                      {fmtNumber(calcAlkalinity, 1)}{' '}
                      <span className="text-xs font-normal text-slate-600">
                        as CaCO3
                      </span>
                    </div>
                  </div>

                  <div className="col-span-12 grid grid-cols-3 gap-3">
                    <div className="bg-slate-900/35 border border-slate-800 rounded-lg p-3">
                      <div className="text-[10px] text-slate-500 uppercase">
                        전하 밸런스
                      </div>
                      <div className="text-sm font-mono text-slate-200">
                        {fmtNumber(chargeBalance_meqL, 3)}{' '}
                        <span className="text-slate-500">meq/L</span>
                      </div>
                      {cbMode !== 'off' && (
                        <div className="text-[10px] text-slate-500 mt-1">
                          원본:{' '}
                          <span className="font-mono">
                            {fmtNumber(rawChargeBalance_meqL, 3)}
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
                        {fmtNumber(estConductivity_uScm, 0)}{' '}
                        <span className="text-slate-500">µS/cm</span>
                      </div>
                    </div>

                    <div className="bg-slate-900/35 border border-slate-800 rounded-lg p-3">
                      <div className="text-[10px] text-slate-500 uppercase">
                        meq/L 합
                      </div>
                      <div className="text-sm font-mono text-slate-200">
                        C {fmtNumber(cationMeq, 3)} / A {fmtNumber(anionMeq, 3)}
                      </div>
                      {cbMode !== 'off' && (
                        <div className="text-[10px] text-slate-500 mt-1">
                          원본: C{' '}
                          <span className="font-mono">
                            {fmtNumber(rawCationMeq, 3)}
                          </span>{' '}
                          / A{' '}
                          <span className="font-mono">
                            {fmtNumber(rawAnionMeq, 3)}
                          </span>
                        </div>
                      )}
                    </div>
                  </div>
                </div>

                {/* Ions (입력은 원본 그대로) */}
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
                      onChange={(k, v) =>
                        setLocalChem({ ...localChem, [k]: v })
                      }
                      showDerived
                      compact={compact}
                    />
                    <IonTable
                      title="ANIONS (-)"
                      defs={ANIONS}
                      chem={localChem}
                      accent="text-rose-300"
                      onChange={(k, v) =>
                        setLocalChem({ ...localChem, [k]: v })
                      }
                      showDerived
                      compact={compact}
                    />
                    <IonTable
                      title="NEUTRALS"
                      defs={NEUTRALS}
                      chem={localChem}
                      accent="text-emerald-300"
                      onChange={(k, v) =>
                        setLocalChem({ ...localChem, [k]: v })
                      }
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
                <p className="text-sm font-medium">최종 생산수</p>
                <p className="text-xs">시뮬레이션 결과에서 확인</p>
              </div>
            ) : (
              <div className="text-sm text-slate-400">
                선택된 노드가 없습니다.
              </div>
            )}
          </div>
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
