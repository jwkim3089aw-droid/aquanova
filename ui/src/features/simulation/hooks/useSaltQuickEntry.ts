// ui/src/features/simulation/hooks/useSaltQuickEntry.ts
import { useCallback } from 'react';
import { MW, n0, roundTo } from '../chemistry';

export type QuickState = { nacl_mgL: number; mgso4_mgL: number };

export function useSaltQuickEntry(
  quick: QuickState,
  setQuick: React.Dispatch<React.SetStateAction<QuickState>>,
  setLocalChem: React.Dispatch<React.SetStateAction<any>>,
) {
  const applyQuickEntry = useCallback(() => {
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
  }, [quick, setLocalChem, setQuick]);

  return { applyQuickEntry };
}
