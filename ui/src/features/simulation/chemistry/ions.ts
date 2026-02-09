// ui\src\features\simulation\chemistry\ions.ts
// WAVE-style ionic analysis: ion definitions & MW

export type IonDef = { label: string; key: string; mw: number; z: number };

export const MW = {
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
} as const;

export const CATIONS: IonDef[] = [
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

export const ANIONS: IonDef[] = [
  { label: 'HCO3', key: 'hco3_mgL', mw: MW.HCO3, z: -1 },
  { label: 'NO3', key: 'no3_mgL', mw: MW.NO3, z: -1 },
  { label: 'Cl', key: 'cl_mgL', mw: MW.Cl, z: -1 },
  { label: 'F', key: 'f_mgL', mw: MW.F, z: -1 },
  { label: 'SO4', key: 'so4_mgL', mw: MW.SO4, z: -2 },
  { label: 'Br', key: 'br_mgL', mw: MW.Br, z: -1 },
  { label: 'PO4', key: 'po4_mgL', mw: MW.PO4, z: -3 },
  { label: 'CO3', key: 'co3_mgL', mw: MW.CO3, z: -2 },
];

export const NEUTRALS: IonDef[] = [
  { label: 'SiO2', key: 'sio2_mgL', mw: MW.SiO2, z: 0 },
  { label: 'B', key: 'b_mgL', mw: MW.B, z: 0 },
  { label: 'CO2', key: 'co2_mgL', mw: MW.CO2, z: 0 },
];
