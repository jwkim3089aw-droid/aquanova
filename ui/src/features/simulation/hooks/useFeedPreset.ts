// ui/src/features/simulation/hooks/useFeedPreset.ts
import {
  useCallback,
  useMemo,
  type Dispatch,
  type SetStateAction,
} from 'react';

import { WATER_CATALOG } from '../data/water_catalog';
import { n0, roundTo } from '../chemistry';
import type { ChemistryInput } from '../model/types';

import {
  WATER_TYPE_OPTIONS,
  buildSubtypeSuggestions,
  computeTdsMgL,
  resolveWaterSubtype,
  resolveWaterType,
  type IonMap,
  type WaterCatalogPreset,
} from '../model/feedWater';

export { WATER_TYPE_OPTIONS }; // 기존 import 호환용

export type FeedState = {
  temperature_C?: number;
  ph?: number;

  water_type?: string;
  water_subtype?: string;

  tds_mgL?: number;

  temp_min_C?: number | null;
  temp_max_C?: number | null;

  feed_note?: string | null;

  [key: string]: unknown;
};

function asText(v: unknown, fallback = ''): string {
  const s = String(v ?? '').trim();
  return s.length ? s : fallback;
}

function asNumberOr(v: unknown, fallback: number): number {
  const n = typeof v === 'number' ? v : Number(v);
  return Number.isFinite(n) ? n : fallback;
}

function r3num(x: unknown): number {
  return roundTo(n0(x), 3);
}

function chemPatchFromIons(ions: IonMap): Partial<ChemistryInput> {
  // dataset key sometimes "SiO2"
  const si = (ions as any).SiO2;

  // NOTE: ChemistryInput의 ion 키는 optional이므로,
  // 프리셋에서 숫자가 아니면 0으로 넣어도 되고, null로 넣어도 됨.
  // 여기서는 "프리셋은 값이 존재한다"는 가정으로 0 fallback을 씀.
  return {
    // cations
    nh4_mgL: r3num(ions.NH4),
    k_mgL: r3num(ions.K),
    na_mgL: r3num(ions.Na),
    mg_mgL: r3num(ions.Mg),
    ca_mgL: r3num(ions.Ca),
    sr_mgL: r3num(ions.Sr),
    ba_mgL: r3num(ions.Ba),

    // anions
    hco3_mgL: r3num(ions.HCO3),
    co3_mgL: r3num(ions.CO3),
    no3_mgL: r3num(ions.NO3),
    cl_mgL: r3num(ions.Cl),
    f_mgL: r3num(ions.F),
    so4_mgL: r3num(ions.SO4),
    br_mgL: r3num(ions.Br),
    po4_mgL: r3num(ions.PO4),

    // neutrals
    co2_mgL: r3num((ions as any).CO2),
    sio2_mgL: r3num(si),
    silica_mgL_SiO2: r3num(si),
    b_mgL: r3num((ions as any).B),

    // optional metals (프리셋에 있으면 반영)
    fe_mgL: r3num((ions as any).Fe),
    mn_mgL: r3num((ions as any).Mn),
  };
}

export function useFeedPreset(
  localFeed: FeedState,
  setLocalFeed: Dispatch<SetStateAction<FeedState>>,
  setLocalChem: Dispatch<SetStateAction<ChemistryInput>>,
) {
  const waterType = String(localFeed?.water_type ?? '');

  // ✅ FeedInspectorBody가 기대하는 {value,label} 형태 그대로 제공
  const waterTypeOptions = useMemo(() => WATER_TYPE_OPTIONS, []);

  const subtypeSuggestions = useMemo(() => {
    return buildSubtypeSuggestions(
      WATER_CATALOG as unknown as WaterCatalogPreset[],
      waterType,
    );
  }, [waterType]);

  const applyPreset = useCallback(
    (presetId: string) => {
      const preset = (WATER_CATALOG as unknown as WaterCatalogPreset[]).find(
        (p) => p.id === presetId,
      );
      if (!preset) return;

      const ions = (preset.ions ?? {}) as IonMap;
      const tds = computeTdsMgL(ions);

      const wt = resolveWaterType(preset); // FeedWaterType
      const ws = resolveWaterSubtype(preset); // string

      setLocalFeed((prev) => {
        const prevTemp = asNumberOr(prev.temperature_C, 25);
        const nextTemp = asNumberOr(preset.temp_C, prevTemp);

        // controlled-safe: 문자열은 ''로
        const nextSubtype = asText(ws, asText(prev.water_subtype, ''));
        const nextNote =
          asText(prev.feed_note, '').length > 0
            ? asText(prev.feed_note, '')
            : asText((preset as any).desc, '');

        return {
          ...prev,
          temperature_C: preset.temp_C ?? prev.temperature_C,
          ph: preset.ph ?? prev.ph,

          water_type: wt, // enum string
          water_subtype: nextSubtype,

          tds_mgL: tds,

          // 기존 값이 있으면 유지, 없으면 preset 온도로 채움
          temp_min_C: prev.temp_min_C ?? nextTemp,
          temp_max_C: prev.temp_max_C ?? nextTemp,

          feed_note: nextNote,
        };
      });

      setLocalChem((prev) => ({
        ...prev,
        ...chemPatchFromIons(ions),
      }));
    },
    [setLocalFeed, setLocalChem],
  );

  return {
    waterTypeOptions,
    subtypeSuggestions,
    applyPreset,
  };
}
