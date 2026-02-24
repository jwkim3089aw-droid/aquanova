// ui/src/features/simulation/model/feedWater.ts
// Feed water type utilities (UI <-> backend enum alignment)
import { WAVEWaterType } from '../../../api/types';

export type WaterTypeOption = { value: WAVEWaterType; label: string };

// 🛑 WAVE UI의 Water Type 콤보박스와 100% 매칭
export const WATER_TYPE_OPTIONS: WaterTypeOption[] = [
  { value: 'RO/NF Well Water', label: 'Well Water (RO/NF)' },
  { value: 'RO/NF Surface Water', label: 'Surface Water (RO/NF)' },
  { value: 'SD Seawater (Open Intake)', label: 'Seawater (Open Intake)' },
  { value: 'SD Seawater (Well)', label: 'Seawater (Well)' },
  { value: 'WW Wastewater', label: 'Wastewater' },
  { value: 'City Water', label: 'City Water' },
];

export const WATER_TYPE_LABEL: Record<WAVEWaterType, string> = {
  'RO/NF Well Water': 'Well Water (RO/NF)',
  'RO/NF Surface Water': 'Surface Water (RO/NF)',
  'SD Seawater (Open Intake)': 'Seawater (Open Intake)',
  'SD Seawater (Well)': 'Seawater (Well)',
  'WW Wastewater': 'Wastewater',
  'City Water': 'City Water',
};

export function isFeedWaterType(v: unknown): v is WAVEWaterType {
  return (
    v === 'RO/NF Well Water' ||
    v === 'RO/NF Surface Water' ||
    v === 'SD Seawater (Open Intake)' ||
    v === 'SD Seawater (Well)' ||
    v === 'WW Wastewater' ||
    v === 'City Water'
  );
}

/**
 * ✅ 백엔드 enum 정석화
 * - 과거 데이터(한글/별칭/대소문자/카테고리 문자열)를 WAVEWaterType으로 정규화
 * - WAVE 카테고리에 맞게 똑똑하게 파싱
 */
export function normalizeWaterType(v: unknown): WAVEWaterType | null {
  if (v == null) return null;

  const raw = String(v).trim();
  if (!raw) return null;

  if (isFeedWaterType(raw)) return raw as WAVEWaterType;

  const s = raw.toLowerCase();

  // Seawater
  if (s.includes('sea') || s.includes('ocean') || raw.includes('해수')) {
    return s.includes('well')
      ? 'SD Seawater (Well)'
      : 'SD Seawater (Open Intake)';
  }

  // City / Municipal
  if (
    s.includes('city') ||
    s.includes('municipal') ||
    raw.includes('수돗물') ||
    raw.includes('상수도')
  ) {
    return 'City Water';
  }

  // Surface Water
  if (s.includes('surface') || s.includes('river') || raw.includes('지표수')) {
    return 'RO/NF Surface Water';
  }

  // Well Water (Groundwater)
  if (s.includes('well') || s.includes('ground') || raw.includes('지하수')) {
    return 'RO/NF Well Water';
  }

  // Wastewater
  if (s.includes('waste') || s.includes('industrial') || raw.includes('폐수')) {
    return 'WW Wastewater';
  }

  // Default Fallback
  return 'RO/NF Well Water';
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
  water_type?: WAVEWaterType | string | null;
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

export function resolveWaterType(preset: WaterCatalogPreset): WAVEWaterType {
  const normalized = normalizeWaterType(preset.water_type);
  if (normalized) return normalized;

  const cat = String(preset.category ?? '')
    .trim()
    .toLowerCase();

  if (cat.includes('sea')) return 'SD Seawater (Open Intake)';
  if (cat.includes('municipal') || cat.includes('city')) return 'City Water';
  if (cat.includes('surface')) return 'RO/NF Surface Water';
  if (cat.includes('well') || cat.includes('ground')) return 'RO/NF Well Water';
  if (cat.includes('waste')) return 'WW Wastewater';

  return 'RO/NF Well Water';
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
