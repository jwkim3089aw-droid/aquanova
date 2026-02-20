// ui/src/features/simulation/model/feedWater.ts
// Feed water type utilities (UI <-> backend enum alignment)

// 백엔드 FeedWaterType 호환성을 위해 키값 자체는 유지하되, 화면에 표시될 때(Label)는 WAVE 명칭을 따름
export type FeedWaterType =
  | 'Seawater'
  | 'Brackish'
  | 'Surface'
  | 'Groundwater'
  | 'Wastewater'
  | 'Other';

export type WaterTypeOption = { value: FeedWaterType; label: string };

// 🛑 WAVE UI의 Water Type 콤보박스와 100% 매칭
export const WATER_TYPE_OPTIONS: WaterTypeOption[] = [
  { value: 'Other', label: 'RO Permeate' },
  { value: 'Brackish', label: 'Municipal Water' },
  { value: 'Groundwater', label: 'Well Water' },
  { value: 'Surface', label: 'Surface Water' },
  { value: 'Seawater', label: 'Seawater' },
  { value: 'Wastewater', label: 'Wastewater' },
];

export const WATER_TYPE_LABEL: Record<FeedWaterType, string> = {
  Other: 'RO Permeate',
  Brackish: 'Municipal Water',
  Groundwater: 'Well Water',
  Surface: 'Surface Water',
  Seawater: 'Seawater',
  Wastewater: 'Wastewater',
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
 * - WAVE 카테고리에 맞게 똑똑하게 파싱
 */
export function normalizeWaterType(v: unknown): FeedWaterType | null {
  if (v == null) return null;

  const raw = String(v).trim();
  if (!raw) return null;

  if (isFeedWaterType(raw)) return raw;

  const s = raw.toLowerCase();

  // Seawater
  if (s === 'sea' || s === 'seawater' || s === 'ocean' || raw.includes('해수'))
    return 'Seawater';

  // Municipal (Brackish)
  if (
    s === 'municipal' ||
    s === 'municipal water' ||
    s === 'brackish' ||
    raw.includes('기수')
  )
    return 'Brackish';

  // Surface Water
  if (
    s === 'surface' ||
    s === 'surfacewater' ||
    s === 'river' ||
    raw.includes('지표수')
  )
    return 'Surface';

  // Well Water (Groundwater)
  if (
    s === 'well' ||
    s === 'well water' ||
    s === 'groundwater' ||
    raw.includes('지하수')
  )
    return 'Groundwater';

  // Wastewater
  if (
    s === 'waste' ||
    s === 'wastewater' ||
    s === 'industrial' ||
    raw.includes('폐수')
  )
    return 'Wastewater';

  // RO Permeate (Other)
  if (
    s === 'ro permeate' ||
    s === 'permeate' ||
    s === 'reuse' ||
    raw.includes('재이용')
  )
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
  if (cat.includes('municipal') || cat === 'brackish') return 'Brackish';
  if (cat === 'surface') return 'Surface';
  if (cat.includes('well') || cat === 'groundwater') return 'Groundwater';
  if (cat.includes('waste')) return 'Wastewater';

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
