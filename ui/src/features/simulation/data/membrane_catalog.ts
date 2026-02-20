// ui/src/features/simulation/data/membrane_catalog.ts

// 1. 타입 정의 (백엔드 스키마와 동기화)
export interface MembraneSpec {
  id: string;
  name: string;
  vendor: string;
  type: 'RO' | 'NF' | 'HRRO' | 'UF' | 'MF';

  area_m2: number; // Active Area
  A_lmh_bar: number; // Water Permeability (A-value)

  // Salt Permeability: B_lmh를 우선 사용 (직관적)
  B_lmh?: number; // L/m²/h (e.g., 0.25)
  B_mps?: number; // m/s (Legacy support)

  salt_rejection_pct?: number;
}

// 2. 통합 데이터 리스트 (Validated Specs)
export const MEMBRANE_CATALOG: MembraneSpec[] = [
  // ==========================================================================
  // HRRO / CCRO Specialized Membranes (High Recovery)
  // ==========================================================================
  {
    id: 'filmtec-soar-6000i',
    name: '[DuPont] FilmTec™ SOAR 6000i',
    vendor: 'DuPont',
    type: 'HRRO',
    // [Engineering Note]
    // Standard Active Area for calculation alignment: 37.2 m² (400 ft²)
    // Matches 48.4 LMH flux at 90m³/h system capacity.
    area_m2: 40.9,
    A_lmh_bar: 3.8, // Tuned for brackish water high recovery
    B_lmh: 0.25, // Standard salt passage
    salt_rejection_pct: 99.5,
  },
  {
    id: 'filmtec-soar-7000i',
    name: '[DuPont] FilmTec™ SOAR 7000i',
    vendor: 'DuPont',
    type: 'HRRO',
    // High Active Area model (Low Energy)
    area_m2: 40.9, // 440 ft²
    A_lmh_bar: 3.8,
    B_lmh: 0.3,
    salt_rejection_pct: 99.5,
  },

  // ==========================================================================
  // Standard Brackish Water RO (BWRO)
  // ==========================================================================
  {
    id: 'bw30-400',
    name: 'FilmTec™ BW30-400',
    vendor: 'DuPont',
    type: 'RO',
    area_m2: 37.0, // Standard 400 ft²
    A_lmh_bar: 4.0, // Standard BWRO Permeability
    B_lmh: 0.5, // Typical B-value
    salt_rejection_pct: 99.5,
  },
  {
    id: 'tm820',
    name: 'Toray TM820-400',
    vendor: 'Toray',
    type: 'RO',
    area_m2: 37.0,
    A_lmh_bar: 3.9,
    B_lmh: 0.45,
    salt_rejection_pct: 99.75,
  },
  {
    id: 'lfc3-ld',
    name: 'LFC3-LD (Low Fouling)',
    vendor: 'Hydranautics',
    type: 'RO',
    area_m2: 37.0,
    A_lmh_bar: 3.2,
    B_lmh: 0.4,
    salt_rejection_pct: 99.7,
  },

  // ==========================================================================
  // Seawater RO (SWRO)
  // ==========================================================================
  {
    id: 'sw30hr',
    name: 'FilmTec™ SW30HR',
    vendor: 'DuPont',
    type: 'RO',
    area_m2: 37.0,
    A_lmh_bar: 1.0, // Low permeability, High rejection
    B_lmh: 0.05, // Very low salt passage
    salt_rejection_pct: 99.8,
  },

  // ==========================================================================
  // Nanofiltration (NF)
  // ==========================================================================
  {
    id: 'nf90',
    name: 'FilmTec™ NF90-400',
    vendor: 'DuPont',
    type: 'NF',
    area_m2: 37.0,
    A_lmh_bar: 9.0, // Tight NF
    B_lmh: 2.0, // Higher salt passage than RO
    salt_rejection_pct: 97.0, // MgSO4 rejection is higher, this is avg
  },
  {
    id: 'nf270',
    name: 'FilmTec™ NF270-400',
    vendor: 'DuPont',
    type: 'NF',
    area_m2: 37.0,
    A_lmh_bar: 12.5, // Loose NF (High Flux)
    B_lmh: 40.0, // Low monovalent rejection
    salt_rejection_pct: 50.0,
  },

  // ==========================================================================
  // Ultrafiltration / Microfiltration (UF/MF)
  // ==========================================================================
  {
    id: 'dultra',
    name: 'Suez dUltra UF',
    vendor: 'Suez',
    type: 'UF',
    area_m2: 50.0,
    A_lmh_bar: 150.0,
  },
  {
    id: 'integra',
    name: 'IntegraPac™ UF',
    vendor: 'DuPont',
    type: 'UF',
    area_m2: 55.0,
    A_lmh_bar: 140.0,
  },
  {
    id: 'memcor',
    name: 'Memcor® CP',
    vendor: 'Evoqua',
    type: 'MF',
    area_m2: 40.0,
    A_lmh_bar: 500.0,
  },
];

// Helper: Get Membrane Specs safely
export function getFallbackMembrane(
  id: string | undefined,
): MembraneSpec | undefined {
  if (!id) return undefined;
  return MEMBRANE_CATALOG.find((m) => m.id === id);
}
