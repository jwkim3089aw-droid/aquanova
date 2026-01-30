// ui/src/features/simulation/data/membrane_catalog.ts

// 1. 타입 정의 (이 파일에서 관리하거나 중앙 타입에서 가져옴)
export interface MembraneSpec {
  id: string;
  name: string;
  vendor: string;
  type: 'RO' | 'NF' | 'HRRO' | 'UF' | 'MF'; // ✅ 이 필드가 있어야 필터링이 됩니다!
  area_m2: number;
  A_lmh_bar: number; // Permeability
  B_mps?: number; // Salt permeability (Optional)
  salt_rejection_pct?: number;
}

// 2. 통합 데이터 리스트 (정석)
export const MEMBRANE_CATALOG: MembraneSpec[] = [
  // --- RO Membranes ---
  {
    id: 'bw30-400',
    name: 'BW30-400',
    vendor: 'DuPont',
    type: 'RO',
    area_m2: 37,
    A_lmh_bar: 3.5,
    B_mps: 1e-7,
    salt_rejection_pct: 99.5,
  },
  {
    id: 'sw30hr',
    name: 'SW30HR',
    vendor: 'DuPont',
    type: 'RO',
    area_m2: 35,
    A_lmh_bar: 1.2,
    B_mps: 5e-9,
    salt_rejection_pct: 99.8,
  },
  {
    id: 'tm820',
    name: 'TM820',
    vendor: 'Toray',
    type: 'RO',
    area_m2: 37,
    A_lmh_bar: 1.1,
    B_mps: 4e-9,
    salt_rejection_pct: 99.8,
  },
  {
    id: 'lfc3',
    name: 'LFC3-LD',
    vendor: 'Hydranautics',
    type: 'RO',
    area_m2: 37,
    A_lmh_bar: 2.8,
    B_mps: 2e-8,
    salt_rejection_pct: 99.7,
  },

  // --- NF Membranes ---
  {
    id: 'nf90',
    name: 'NF90-400',
    vendor: 'DuPont',
    type: 'NF',
    area_m2: 37,
    A_lmh_bar: 4.5,
    B_mps: 2e-6,
    salt_rejection_pct: 97.0,
  },
  {
    id: 'nf270',
    name: 'NF270-400',
    vendor: 'DuPont',
    type: 'NF',
    area_m2: 37,
    A_lmh_bar: 10.5,
    B_mps: 5e-6,
    salt_rejection_pct: 50.0,
  },

  // --- UF Membranes ---
  {
    id: 'dultra',
    name: 'dUltra UF',
    vendor: 'Suez',
    type: 'UF',
    area_m2: 50,
    A_lmh_bar: 150,
  },
  {
    id: 'integra',
    name: 'IntegraPac',
    vendor: 'DuPont',
    type: 'UF',
    area_m2: 55,
    A_lmh_bar: 140,
  },

  // --- MF Membranes ---
  {
    id: 'memcor',
    name: 'Memcor CP',
    vendor: 'Evoqua',
    type: 'MF',
    area_m2: 40,
    A_lmh_bar: 500,
  },
];

// Helper: 호환성 유지용 (필요하면 사용)
export function getFallbackMembrane(
  id: string | undefined,
): MembraneSpec | undefined {
  if (!id) return undefined;
  return MEMBRANE_CATALOG.find((m) => m.id === id);
}
