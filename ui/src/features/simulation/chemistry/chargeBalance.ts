// ui\src\features\simulation\chemistry\chargeBalance.ts
import { ANIONS, CATIONS, NEUTRALS, type IonDef } from './ions';
import { n0, roundTo } from './format';
import { sumMeqL } from './conversions';

export type ChargeBalanceMode = 'off' | 'anions' | 'cations' | 'all';

export type ChargeBalanceMeta = {
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
  // signed meq change (appliedMgL can be negative)
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

export function applyChargeBalance(
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
