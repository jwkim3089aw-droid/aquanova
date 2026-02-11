// ui/src/features/simulation/hooks/useFeedChargeBalance.ts
import { useMemo } from 'react';

import type { ChemistryInput } from '../model/types';
import {
  CATIONS,
  ANIONS,
  NEUTRALS,
  MW,
  applyChargeBalance,
  type ChargeBalanceMode,
  fmtNumber,
  n0,
  sumMeqL,
  sumMgL,
  mgL_to_meqL,
} from '../chemistry';

type ChargeBalanceMeta = {
  adjustments_mgL?: Record<string, number>;
  note?: string;
};

export interface FeedDerived {
  // chemistry (used table after balance mode)
  chemUsed: ChemistryInput;

  // sums (raw)
  rawTotalTDS: number;
  rawCationMeq: number;
  rawAnionMeq: number;
  rawChargeBalance_meqL: number;

  // sums (used/adjusted)
  totalTDS: number;
  cationMeq: number;
  anionMeq: number;
  chargeBalance_meqL: number;

  // derived KPIs
  calcHardness: number;
  calcAlkalinity: number;
  estConductivity_uScm: number;

  // charge balance meta rendering helpers
  adjustmentText: string;
  cbNote?: string;
}

/**
 * ✅ 중요: 이 훅은 내부에서 useMemo를 "항상" 호출해야 한다.
 */
export function useFeedChargeBalance(
  localChem: ChemistryInput,
  cbMode: ChargeBalanceMode,
): FeedDerived {
  return useMemo(() => {
    const out = applyChargeBalance(localChem, cbMode) as unknown as {
      chemUsed: ChemistryInput;
      meta?: ChargeBalanceMeta;
    };

    const chemUsed = out?.chemUsed ?? localChem;
    const meta = out?.meta;

    // raw
    const rawCationSum = sumMgL(localChem, CATIONS);
    const rawAnionSum = sumMgL(localChem, ANIONS);
    const rawNeutralSum = sumMgL(localChem, NEUTRALS);
    const rawTotalTDS = rawCationSum + rawAnionSum + rawNeutralSum;

    const rawCationMeq = sumMeqL(localChem, CATIONS);
    const rawAnionMeq = sumMeqL(localChem, ANIONS);
    const rawChargeBalance_meqL = rawCationMeq - rawAnionMeq;

    // used
    const cationSum = sumMgL(chemUsed, CATIONS);
    const anionSum = sumMgL(chemUsed, ANIONS);
    const neutralSum = sumMgL(chemUsed, NEUTRALS);
    const totalTDS = cationSum + anionSum + neutralSum;

    const cationMeq = sumMeqL(chemUsed, CATIONS);
    const anionMeq = sumMeqL(chemUsed, ANIONS);
    const chargeBalance_meqL = cationMeq - anionMeq;

    // hardness / alkalinity
    const ca_meq = mgL_to_meqL(n0(chemUsed?.ca_mgL), MW.Ca, +2);
    const mg_meq = mgL_to_meqL(n0(chemUsed?.mg_mgL), MW.Mg, +2);
    const calcHardness = (ca_meq + mg_meq) * 50.0;

    const hco3_meq = mgL_to_meqL(n0(chemUsed?.hco3_mgL), MW.HCO3, -1);
    const co3_meq = mgL_to_meqL(n0(chemUsed?.co3_mgL), MW.CO3, -2);
    const calcAlkalinity = (hco3_meq + co3_meq) * 50.0;

    const estConductivity_uScm = totalTDS * 1.7;

    const adjustmentText = (() => {
      const entries = Object.entries(meta?.adjustments_mgL ?? {});
      if (cbMode === 'off' || entries.length === 0) return '';
      const top = entries
        .sort(
          (a, b) =>
            Math.abs((b[1] as number) ?? 0) - Math.abs((a[1] as number) ?? 0),
        )
        .slice(0, 4)
        .map(([k, v]) => {
          const vv = Number(v) || 0;
          return `${k.replace('_mgL', '')} ${vv > 0 ? '+' : ''}${fmtNumber(vv, 3)} mg/L`;
        });
      return top.join(', ');
    })();

    return {
      chemUsed,

      rawTotalTDS,
      rawCationMeq,
      rawAnionMeq,
      rawChargeBalance_meqL,

      totalTDS,
      cationMeq,
      anionMeq,
      chargeBalance_meqL,

      calcHardness,
      calcAlkalinity,
      estConductivity_uScm,

      adjustmentText,
      cbNote: meta?.note,
    };
  }, [localChem, cbMode]);
}
