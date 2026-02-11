// ui/src/features/simulation/hooks/useFeedPreset.ts
import { useCallback, useMemo } from 'react';
import { WATER_CATALOG } from '../data/water_catalog';
import { n0, roundTo } from '../chemistry';

export const WATER_TYPE_OPTIONS = [
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

export function useFeedPreset(
  localFeed: any,
  setLocalFeed: React.Dispatch<React.SetStateAction<any>>,
  setLocalChem: React.Dispatch<React.SetStateAction<any>>,
) {
  const subtypeSuggestions = useMemo(() => {
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
  }, [localFeed?.water_type]);

  const applyPreset = useCallback(
    (presetId: string) => {
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
    },
    [setLocalFeed, setLocalChem],
  );

  return {
    waterTypeOptions: WATER_TYPE_OPTIONS,
    subtypeSuggestions,
    applyPreset,
  };
}
