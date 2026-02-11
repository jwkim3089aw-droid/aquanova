// ui/src/features/simulation/data/membrane_catalog.ts

// 1. 타입 정의
export interface MembraneSpec {
  id: string;
  name: string;
  vendor: string;
  type: 'RO' | 'NF' | 'HRRO' | 'UF' | 'MF';
  area_m2: number;
  A_lmh_bar: number; // Permeability
  B_mps?: number; // Salt permeability (m/s)
  salt_rejection_pct?: number;
}

// 2. 통합 데이터 리스트
export const MEMBRANE_CATALOG: MembraneSpec[] = [
  // ==========================================================================
  // [수정됨] WAVE Matching Tuned Data (FilmTec SOAR)
  // ==========================================================================
  {
    id: 'filmtec-soar-7000i',
    name: 'FilmTec™ SOAR 7000i',
    vendor: 'DuPont',
    type: 'HRRO',
    // [WAVE 역산 값 적용]
    area_m2: 40.9, // 기존 37.0 -> 40.9 (2044 m² / 50 elements)
    A_lmh_bar: 1.2, // 압력 보정 (조금 낮춰서 실제 고압 모사)
    B_mps: 1.0e-9, // 수질 보정 (매우 낮춰서 WAVE의 200ppm 수준 달성)
    salt_rejection_pct: 99.85,
  },
  {
    id: 'filmtec-soar-6000i',
    name: 'FilmTec™ SOAR 6000i',
    vendor: 'DuPont',
    type: 'HRRO',
    // [동일 플랫폼 적용]
    area_m2: 40.9,
    A_lmh_bar: 1.1,
    B_mps: 1.5e-9,
    salt_rejection_pct: 99.8,
  },

  // ==========================================================================
  // 기존 RO/NF/UF/MF 모델들은 그대로 유지
  // ==========================================================================
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
  // ... (나머지 기존 데이터들: sw30hr, tm820 등등 계속 이어짐) ...
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
  {
    id: 'memcor',
    name: 'Memcor CP',
    vendor: 'Evoqua',
    type: 'MF',
    area_m2: 40,
    A_lmh_bar: 500,
  },
];

// Helper: 호환성 유지용
export function getFallbackMembrane(
  id: string | undefined,
): MembraneSpec | undefined {
  if (!id) return undefined;
  return MEMBRANE_CATALOG.find((m) => m.id === id);
}
