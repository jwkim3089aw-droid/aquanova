// ui\src\features\simulation\chemistry\conversions.ts
import type { IonDef } from './ions';
import { n0 } from './format';

// mg/L -> meq/L
export function mgL_to_meqL(mgL: number, mw: number, z: number): number {
  if (!mw || !z) return 0;
  return (mgL / mw) * Math.abs(z);
}

// meq/L -> ppm as CaCO3
export function meqL_to_ppmCaCO3(meqL: number): number {
  return meqL * 50.0;
}

export function sumMgL(chem: any, defs: IonDef[]) {
  return defs.reduce((acc, d) => acc + n0(chem?.[d.key]), 0);
}

export function sumMeqL(chem: any, defs: IonDef[]) {
  return defs.reduce(
    (acc, d) => acc + mgL_to_meqL(n0(chem?.[d.key]), d.mw, d.z),
    0,
  );
}
