// ui/src/features/simulation/hooks/useChargeBalanceActions.ts
import { useCallback, useMemo } from 'react';
import { applyChargeBalance, type ChargeBalanceMode } from '../chemistry';

export function useChargeBalanceActions(
  localChem: any,
  cbMode: ChargeBalanceMode,
  setLocalChem: React.Dispatch<React.SetStateAction<any>>,
) {
  const cbModeLabel = useMemo<Record<ChargeBalanceMode, string>>(
    () => ({
      off: 'OFF(원본 그대로)',
      anions: 'Anions(Cl 우선)',
      cations: 'Cations(Na 우선)',
      all: 'All(양·음이온 스케일)',
    }),
    [],
  );

  // WAVE처럼 “표에 반영”(입력값 자체를 보정값으로 덮어쓰기)
  const applyBalanceIntoTable = useCallback(() => {
    if (cbMode === 'off') return;
    const r = applyChargeBalance(localChem, cbMode);
    setLocalChem((prev: any) => ({ ...prev, ...r.chemUsed }));
  }, [cbMode, localChem, setLocalChem]);

  return { cbModeLabel, applyBalanceIntoTable };
}
