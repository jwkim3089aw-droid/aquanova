// ui/src/features/simulation/model/feedWater.ts
// Feed water type utilities (UI <-> backend enum alignment)

export type FeedWaterType =
  | 'Seawater'
  | 'Brackish'
  | 'Surface'
  | 'Groundwater'
  | 'Wastewater'
  | 'Other';

export type WaterTypeOption = { value: FeedWaterType; label: string };

export const WATER_TYPE_OPTIONS: WaterTypeOption[] = [
  { value: 'Seawater', label: '해수' },
  { value: 'Brackish', label: '기수' },
  { value: 'Surface', label: '지표수(강/호수)' },
  { value: 'Groundwater', label: '지하수' },
  { value: 'Wastewater', label: '폐수(산업/공정)' },
  { value: 'Other', label: '기타' },
];

export const WATER_TYPE_LABEL: Record<FeedWaterType, string> = {
  Seawater: '해수',
  Brackish: '기수',
  Surface: '지표수(강/호수)',
  Groundwater: '지하수',
  Wastewater: '폐수(산업/공정)',
  Other: '기타',
};

export function isFeedWaterType(v: unknown): v is FeedWaterType {
  return (
    v === 'Seawater' ||
    v === 'Brackish' ||
    v === 'Surface' ||
    v === 'Groundwater' ||
    v === 'Wastewater' ||
    v === 'Other'
  );
}

/**
 * ✅ 백엔드 enum 정석화
 * - 과거 데이터(한글/별칭/대소문자/카테고리 문자열)를 FeedWaterType으로 정규화
 * - 못 맞추면 null
 */
export function normalizeWaterType(v: unknown): FeedWaterType | null {
  if (v == null) return null;

  const raw = String(v).trim();
  if (!raw) return null;

  // already valid
  if (isFeedWaterType(raw)) return raw;

  const s = raw.toLowerCase();

  // English-ish aliases
  if (s === 'sea' || s === 'seawater' || s === 'ocean') return 'Seawater';
  if (s === 'brackish' || s === 'brackishwater') return 'Brackish';
  if (
    s === 'surface' ||
    s === 'surfacewater' ||
    s === 'river' ||
    s === 'lake' ||
    s === 'reservoir'
  )
    return 'Surface';
  if (s === 'groundwater' || s === 'ground' || s === 'well')
    return 'Groundwater';
  if (s === 'waste' || s === 'wastewater' || s === 'industrial')
    return 'Wastewater';
  if (s === 'reuse' || s === 'reclaimed') return 'Other';

  // Dataset category strings sometimes stored
  if (raw === 'Waste') return 'Wastewater';
  if (raw === 'Reuse') return 'Other';

  // Korean legacy / fuzzy
  if (raw.includes('해수')) return 'Seawater';
  if (raw.includes('기수')) return 'Brackish';
  if (
    raw.includes('지표수') ||
    raw.includes('강') ||
    raw.includes('호수') ||
    raw.includes('저수지')
  )
    return 'Surface';
  if (raw.includes('지하수') || raw.includes('관정') || raw.includes('우물'))
    return 'Groundwater';
  if (raw.includes('폐수') || raw.includes('공정수') || raw.includes('산업'))
    return 'Wastewater';
  if (raw.includes('재이용') || raw.includes('하수') || raw.includes('방류수'))
    return 'Other';

  return null;
}

// ----------------------
// Preset helpers
// ----------------------

export type IonMap = Record<string, number | null | undefined>;

export type WaterCatalogPreset = {
  id: string;
  name?: string;
  category?: string;
  desc?: string;
  temp_C?: number;
  ph?: number;
  water_type?: FeedWaterType | string | null;
  water_subtype?: string | null;
  ions?: IonMap | null;
  [k: string]: unknown;
};

export function computeTdsMgL(ions: IonMap): number {
  let sum = 0;
  for (const v of Object.values(ions || {})) {
    if (v == null) continue;
    const n = typeof v === 'number' ? v : Number(v);
    if (Number.isFinite(n)) sum += n;
  }
  return sum;
}

export function resolveWaterType(preset: WaterCatalogPreset): FeedWaterType {
  const normalized = normalizeWaterType(preset.water_type);
  if (normalized) return normalized;

  const cat = String(preset.category ?? '')
    .trim()
    .toLowerCase();
  if (cat === 'seawater') return 'Seawater';
  if (cat === 'brackish') return 'Brackish';
  if (cat === 'surface') return 'Surface';
  if (cat === 'groundwater') return 'Groundwater';
  if (cat === 'waste') return 'Wastewater';
  if (cat === 'wastewater') return 'Wastewater';
  if (cat === 'reuse') return 'Other';

  return 'Other';
}

export function resolveWaterSubtype(preset: WaterCatalogPreset): string {
  const ws = String(preset.water_subtype ?? '').trim();
  if (ws) return ws;

  const name = String(preset.name ?? '').trim();
  if (name) return name;

  return '';
}

export function buildSubtypeSuggestions(
  catalog: WaterCatalogPreset[],
  waterType: string,
): string[] {
  const wt = normalizeWaterType(waterType);

  const set = new Set<string>();
  for (const p of catalog || []) {
    const pwt = normalizeWaterType(p.water_type) ?? resolveWaterType(p);
    if (wt && pwt !== wt) continue;

    const ws = String(p.water_subtype ?? '').trim();
    if (ws) set.add(ws);
  }

  return Array.from(set)
    .sort((a, b) => a.localeCompare(b))
    .slice(0, 50);
}
