// ui/src/features/simulation/hooks/flow/utils.ts
import { clone } from '../../model/logic';
import { normalizeWaterType } from '../../model/feedWater';
import type { FeedState, ChemistryInput } from '../../model/types';
import type { WaterChemistryInput, IonCompositionInput } from '@/api/types';

export const SESSION_KEY = 'AQUANOVA_SESSION_V1';

export const DEFAULT_FEED: FeedState = {
  flow_m3h: 20,
  tds_mgL: 2000,
  temperature_C: 25,
  ph: 7.0,
  pressure_bar: 0.0,
  water_type: 'RO/NF Well Water',
  water_subtype: null,
  fouling: {
    turbidity_ntu: null,
    tss_mgL: null,
    sdi15: null,
    toc_mgL: null,
    cod_mgL: null,
    bod_mgL: null,
  },
  temp_min_C: null,
  temp_max_C: null,
  feed_note: null,
  charge_balance_mode: null,
};

export function migrateFeedState(raw: any): FeedState {
  if (!raw) return clone(DEFAULT_FEED);
  const safeWaterType =
    normalizeWaterType(raw.water_type) || 'RO/NF Well Water';
  return {
    ...raw,
    water_type: safeWaterType,
    fouling: {
      turbidity_ntu: raw.fouling?.turbidity_ntu ?? raw.turbidity_ntu ?? null,
      tss_mgL: raw.fouling?.tss_mgL ?? raw.tss_mgL ?? null,
      sdi15: raw.fouling?.sdi15 ?? raw.sdi15 ?? null,
      toc_mgL: raw.fouling?.toc_mgL ?? raw.toc_mgL ?? null,
      cod_mgL: raw.fouling?.cod_mgL ?? null,
      bod_mgL: raw.fouling?.bod_mgL ?? null,
    },
  };
}

export function hasAnyNumber(
  obj: Record<string, any> | null | undefined,
): boolean {
  if (!obj) return false;
  return Object.values(obj).some(
    (v) => typeof v === 'number' && Number.isFinite(v),
  );
}

export function mapChemistryToBackend(ui: ChemistryInput | null | undefined): {
  chemistry?: WaterChemistryInput | null;
  ions?: IonCompositionInput | null;
} {
  if (!ui) return {};

  const chemistry: WaterChemistryInput = {
    alkalinity_mgL_as_CaCO3: ui.alkalinity_mgL_as_CaCO3 ?? null,
    calcium_hardness_mgL_as_CaCO3: ui.calcium_hardness_mgL_as_CaCO3 ?? null,
    sulfate_mgL: ui.sulfate_mgL ?? ui.so4_mgL ?? null,
    barium_mgL: ui.barium_mgL ?? ui.ba_mgL ?? null,
    strontium_mgL: ui.strontium_mgL ?? ui.sr_mgL ?? null,
    silica_mgL_SiO2: ui.silica_mgL_SiO2 ?? ui.sio2_mgL ?? null,
  };

  const ions: Record<string, number | null> = {
    NH4: ui.nh4_mgL ?? null,
    K: ui.k_mgL ?? null,
    Na: ui.na_mgL ?? null,
    Mg: ui.mg_mgL ?? null,
    Ca: ui.ca_mgL ?? null,
    Sr: ui.sr_mgL ?? null,
    Ba: ui.ba_mgL ?? null,
    HCO3: ui.hco3_mgL ?? null,
    NO3: ui.no3_mgL ?? null,
    Cl: ui.cl_mgL ?? null,
    F: ui.f_mgL ?? null,
    SO4: ui.so4_mgL ?? ui.sulfate_mgL ?? null,
    Br: ui.br_mgL ?? null,
    PO4: ui.po4_mgL ?? null,
    CO3: ui.co3_mgL ?? null,
    CO2: ui.co2_mgL ?? null,
    SiO2: ui.sio2_mgL ?? ui.silica_mgL_SiO2 ?? null,
    B: ui.b_mgL ?? null,
    Fe: ui.fe_mgL ?? null,
    Mn: ui.mn_mgL ?? null,
    Al: ui.al_mgL ?? null,
  };

  const validIons: any = {};
  let hasValidIon = false;
  for (const [key, value] of Object.entries(ions)) {
    if (typeof value === 'number' && Number.isFinite(value) && value > 0) {
      validIons[key] = value;
      hasValidIon = true;
    }
  }

  return {
    chemistry: hasAnyNumber(chemistry as any) ? chemistry : null,
    ions: hasValidIon ? validIons : null,
  };
}

export function isEditableTarget(t: EventTarget | null): boolean {
  const el = t as HTMLElement | null;
  if (!el) return false;
  const tag = el.tagName;
  if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return true;
  if ((el as any).isContentEditable) return true;
  return false;
}
