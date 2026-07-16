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

  fouling?: any; // ✅ 파울링 상태 타입 추가

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
  const si = (ions as any).SiO2;

  return {
    nh4_mgL: r3num(ions.NH4),
    k_mgL: r3num(ions.K),
    na_mgL: r3num(ions.Na),
    mg_mgL: r3num(ions.Mg),
    ca_mgL: r3num(ions.Ca),
    sr_mgL: r3num(ions.Sr),
    ba_mgL: r3num(ions.Ba),

    hco3_mgL: r3num(ions.HCO3),
    co3_mgL: r3num(ions.CO3),
    no3_mgL: r3num(ions.NO3),
    cl_mgL: r3num(ions.Cl),
    f_mgL: r3num(ions.F),
    so4_mgL: r3num(ions.SO4),
    br_mgL: r3num(ions.Br),
    po4_mgL: r3num(ions.PO4),

    co2_mgL: r3num((ions as any).CO2),
    sio2_mgL: r3num(si),
    silica_mgL_SiO2: r3num(si),
    b_mgL: r3num((ions as any).B),

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

  const waterTypeOptions = useMemo(() => WATER_TYPE_OPTIONS, []);

  const subtypeSuggestions = useMemo(() => {
    return buildSubtypeSuggestions(
      WATER_CATALOG as unknown as WaterCatalogPreset[],
      waterType,
    );
  }, [waterType]);

  const applyPreset = useCallback(
    (presetId: string) => {
      const preset = (WATER_CATALOG as any[]).find((p) => p.id === presetId);
      if (!preset) return;

      const ions = (preset.ions ?? {}) as IonMap;
      const tds = computeTdsMgL(ions);

      const wt = resolveWaterType(preset);
      const ws = resolveWaterSubtype(preset);

      setLocalFeed((prev) => {
        const prevTemp = asNumberOr(prev.temperature_C, 25);
        const nextTemp = asNumberOr(preset.temp_C, prevTemp);

        const nextSubtype = asText(ws, asText(prev.water_subtype, ''));
        const nextNote =
          asText(prev.feed_note, '').length > 0
            ? asText(prev.feed_note, '')
            : asText((preset as any).desc, '');

        return {
          ...prev,
          temperature_C:
            prev.temperature_C !== 25
              ? prev.temperature_C
              : (preset.temp_C ?? prev.temperature_C),
          ph: preset.ph ?? prev.ph,

          water_type: wt,
          water_subtype: nextSubtype,

          tds_mgL: tds,

          temp_min_C: prev.temp_min_C !== null ? prev.temp_min_C : nextTemp,
          temp_max_C: prev.temp_max_C !== null ? prev.temp_max_C : nextTemp,

          feed_note: nextNote,

          // 🚀 [PATCH] 카탈로그의 파울링 지표(SDI, 탁도 등)를 불러와서 덮어씌움!
          fouling: {
            ...(prev.fouling || {}),
            ...(preset.fouling || {}),
          },
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
