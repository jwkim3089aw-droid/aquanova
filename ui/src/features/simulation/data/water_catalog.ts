// ui/src/features/simulation/data/water_catalog.ts

import type { WAVEWaterType, FoulingIndicators } from '../../../api/types';

export type WaterPresetCategory =
  | 'Seawater'
  | 'Brackish'
  | 'Surface'
  | 'Waste'
  | 'Reuse';

export type WaterPresetIons = {
  // Cations (+)
  NH4: number;
  K: number;
  Na: number;
  Mg: number;
  Ca: number;
  Sr: number;
  Ba: number;
  Fe: number;
  Mn: number;
  // Anions (-)
  HCO3: number;
  NO3: number;
  Cl: number;
  F: number;
  SO4: number;
  Br: number;
  PO4: number;
  CO3: number;
  // Neutrals
  SiO2: number;
  B: number;
  CO2: number;
};

export type WaterPreset = {
  id: string;
  name: string; // ✅ 한국어 표시명
  category: WaterPresetCategory;
  desc: string; // ✅ 간단 설명(한국어)
  temp_C: number;
  ph: number;

  // ✅ 백엔드 WAVE 스키마와 완벽 일치
  water_type?: WAVEWaterType;
  water_subtype?: string;
  fouling?: FoulingIndicators; // 🛑 [WAVE PATCH] 수질별 파울링 지표 추가

  ions: WaterPresetIons;
};

// WAVE에서 흔히 쓰는 “대표 조성” 위주로 정리 (파울링 지표 빅데이터 기반 추가)
export const WATER_CATALOG: WaterPreset[] = [
  // ==================================================
  // 해수 (Seawater)
  // ==================================================
  {
    id: 'sw_std_pacific',
    name: '표준 해수(태평양 평균)',
    category: 'Seawater',
    desc: '대표 해수 조성 (TDS≈35,000 mg/L)',
    temp_C: 25,
    ph: 8.1,
    water_type: 'SD Seawater (Open Intake)',
    water_subtype: '태평양 평균',
    fouling: {
      sdi15: 4.0,
      turbidity_ntu: 1.0,
      tss_mgL: 2.0,
      toc_mgL: 1.0,
    },
    ions: {
      NH4: 0,
      K: 399,
      Na: 10781,
      Mg: 1284,
      Ca: 412,
      Sr: 7.9,
      Ba: 0,
      Fe: 0.002,
      Mn: 0,
      HCO3: 142,
      NO3: 0,
      Cl: 19353,
      F: 1.3,
      SO4: 2712,
      Br: 67,
      PO4: 0,
      CO3: 0,
      SiO2: 6.0,
      B: 4.5,
      CO2: 0.5,
    },
  },
  {
    id: 'sw_std_atlantic',
    name: '표준 해수(대서양 평균)',
    category: 'Seawater',
    desc: '대표 해수 조성 (TDS≈36,000 mg/L)',
    temp_C: 25,
    ph: 8.1,
    water_type: 'SD Seawater (Open Intake)',
    water_subtype: '대서양 평균',
    fouling: {
      sdi15: 4.2,
      turbidity_ntu: 1.5,
      tss_mgL: 2.5,
      toc_mgL: 1.2,
    },
    ions: {
      NH4: 0,
      K: 410,
      Na: 11100,
      Mg: 1290,
      Ca: 420,
      Sr: 8.2,
      Ba: 0,
      Fe: 0.003,
      Mn: 0,
      HCO3: 145,
      NO3: 0,
      Cl: 19900,
      F: 1.4,
      SO4: 2750,
      Br: 68,
      PO4: 0,
      CO3: 0,
      SiO2: 4.5,
      B: 4.8,
      CO2: 0.5,
    },
  },
  {
    id: 'sw_high_salinity_me',
    name: '고염도 해수(홍해/아라비아만)',
    category: 'Seawater',
    desc: '고염도 해수 (TDS≈45,000 mg/L)',
    temp_C: 32,
    ph: 8.3,
    water_type: 'SD Seawater (Open Intake)',
    water_subtype: '홍해/아라비아만',
    fouling: {
      sdi15: 4.5,
      turbidity_ntu: 2.0,
      tss_mgL: 3.0,
      toc_mgL: 1.5,
    },
    ions: {
      NH4: 0,
      K: 480,
      Na: 14500,
      Mg: 1800,
      Ca: 550,
      Sr: 12,
      Ba: 0,
      Fe: 0.01,
      Mn: 0,
      HCO3: 160,
      NO3: 0,
      Cl: 25000,
      F: 1.5,
      SO4: 3500,
      Br: 90,
      PO4: 0,
      CO3: 5,
      SiO2: 3.0,
      B: 6.0,
      CO2: 0,
    },
  },
  {
    id: 'sw_mediterranean',
    name: '해수(지중해)',
    category: 'Seawater',
    desc: '상대적 고염도 (TDS≈38,000 mg/L)',
    temp_C: 25,
    ph: 8.1,
    water_type: 'SD Seawater (Open Intake)',
    water_subtype: '지중해',
    fouling: {
      sdi15: 3.5,
      turbidity_ntu: 0.8,
      tss_mgL: 1.5,
      toc_mgL: 1.0,
    },
    ions: {
      NH4: 0,
      K: 420,
      Na: 12000,
      Mg: 1400,
      Ca: 450,
      Sr: 9.0,
      Ba: 0,
      Fe: 0.005,
      Mn: 0,
      HCO3: 150,
      NO3: 0,
      Cl: 21500,
      F: 1.4,
      SO4: 3050,
      Br: 75,
      PO4: 0,
      CO3: 2,
      SiO2: 3.0,
      B: 5.0,
      CO2: 0.5,
    },
  },

  // ==================================================
  // 기수/지하수 (Brackish / Well Water)
  // ==================================================
  {
    id: 'bw_std_groundwater',
    name: '기수 지하수(표준)',
    category: 'Brackish',
    desc: '대표 기수 조성 (TDS≈1,500 mg/L)',
    temp_C: 20,
    ph: 7.6,
    water_type: 'RO/NF Well Water',
    water_subtype: '지하수 표준',
    fouling: {
      sdi15: 1.5, // 지하수는 모래 여과 효과로 기본 탁도/SDI가 매우 낮음
      turbidity_ntu: 0.2,
      tss_mgL: 0.5,
      toc_mgL: 0.5,
    },
    ions: {
      NH4: 0.5,
      K: 15,
      Na: 450,
      Mg: 80,
      Ca: 150,
      Sr: 2,
      Ba: 0.1,
      Fe: 0.5,
      Mn: 0.1,
      HCO3: 350,
      NO3: 10,
      Cl: 600,
      F: 0.8,
      SO4: 400,
      Br: 1,
      PO4: 0,
      CO3: 0,
      SiO2: 25,
      B: 0.5,
      CO2: 15,
    },
  },
  {
    id: 'bw_high_hardness',
    name: '기수 지하수(고경도)',
    category: 'Brackish',
    desc: '경도/스케일링 주의 (TDS≈3,000 mg/L)',
    temp_C: 20,
    ph: 7.5,
    water_type: 'RO/NF Well Water',
    water_subtype: '고경도 지하수',
    fouling: {
      sdi15: 2.0,
      turbidity_ntu: 0.5,
      tss_mgL: 1.0,
      toc_mgL: 1.0,
    },
    ions: {
      NH4: 0.5,
      K: 20,
      Na: 650,
      Mg: 180,
      Ca: 450,
      Sr: 3,
      Ba: 0.2,
      Fe: 0.3,
      Mn: 0.1,
      HCO3: 520,
      NO3: 5,
      Cl: 900,
      F: 0.8,
      SO4: 650,
      Br: 1,
      PO4: 0,
      CO3: 5,
      SiO2: 35,
      B: 0.7,
      CO2: 10,
    },
  },
  {
    id: 'bw_saline_groundwater',
    name: '염지하수(고TDS)',
    category: 'Brackish',
    desc: '염지하수 (TDS≈10,000 mg/L)',
    temp_C: 25,
    ph: 7.8,
    water_type: 'RO/NF Well Water',
    water_subtype: '염지하수',
    fouling: {
      sdi15: 2.5,
      turbidity_ntu: 0.8,
      tss_mgL: 2.0,
      toc_mgL: 1.5,
    },
    ions: {
      NH4: 1,
      K: 60,
      Na: 3200,
      Mg: 220,
      Ca: 300,
      Sr: 5,
      Ba: 0.3,
      Fe: 0.2,
      Mn: 0.05,
      HCO3: 300,
      NO3: 5,
      Cl: 5200,
      F: 1.0,
      SO4: 1400,
      Br: 8,
      PO4: 0,
      CO3: 10,
      SiO2: 20,
      B: 1.0,
      CO2: 10,
    },
  },

  // ==================================================
  // 지표수 (Surface Water)
  // ==================================================
  {
    id: 'sf_river_std',
    name: '강물(표준)',
    category: 'Surface',
    desc: '저TDS 지표수 (TDS≈200~400 mg/L)',
    temp_C: 15,
    ph: 7.2,
    water_type: 'RO/NF Surface Water',
    water_subtype: '강물',
    fouling: {
      sdi15: 6.0, // 지표수는 부유물/미생물이 많아 SDI가 높음
      turbidity_ntu: 15.0,
      tss_mgL: 20.0,
      toc_mgL: 5.0,
      cod_mgL: 8.0,
    },
    ions: {
      NH4: 0.2,
      K: 4,
      Na: 25,
      Mg: 8,
      Ca: 35,
      Sr: 0.1,
      Ba: 0,
      Fe: 0.2,
      Mn: 0.03,
      HCO3: 110,
      NO3: 3,
      Cl: 25,
      F: 0.2,
      SO4: 35,
      Br: 0,
      PO4: 0.1,
      CO3: 0,
      SiO2: 10,
      B: 0.05,
      CO2: 5,
    },
  },
  {
    id: 'sf_reservoir',
    name: '저수지/호수(표준)',
    category: 'Surface',
    desc: '계절 변동 가능 (TDS≈250~500 mg/L)',
    temp_C: 15,
    ph: 7.4,
    water_type: 'RO/NF Surface Water',
    water_subtype: '호수/저수지',
    fouling: {
      sdi15: 5.0,
      turbidity_ntu: 8.0,
      tss_mgL: 10.0,
      toc_mgL: 4.0,
    },
    ions: {
      NH4: 0.2,
      K: 3,
      Na: 30,
      Mg: 10,
      Ca: 40,
      Sr: 0.1,
      Ba: 0,
      Fe: 0.15,
      Mn: 0.03,
      HCO3: 130,
      NO3: 2,
      Cl: 30,
      F: 0.2,
      SO4: 40,
      Br: 0,
      PO4: 0.1,
      CO3: 0,
      SiO2: 12,
      B: 0.05,
      CO2: 5,
    },
  },

  // ==================================================
  // 폐수 (Waste) -> 서버 enum: WW Wastewater
  // ==================================================
  {
    id: 'ww_cooling_tower_blowdown',
    name: '냉각탑 블로다운',
    category: 'Waste',
    desc: '실리카/경도 높음(스케일링 주의)',
    temp_C: 30,
    ph: 8.0,
    water_type: 'WW Wastewater',
    water_subtype: '냉각탑 블로다운',
    fouling: {
      sdi15: 5.5,
      turbidity_ntu: 10.0,
      tss_mgL: 15.0,
      toc_mgL: 8.0,
      cod_mgL: 20.0,
    },
    ions: {
      NH4: 1,
      K: 50,
      Na: 600,
      Mg: 180,
      Ca: 400,
      Sr: 3,
      Ba: 0.2,
      Fe: 1.0,
      Mn: 0.2,
      HCO3: 400,
      NO3: 20,
      Cl: 800,
      F: 1.0,
      SO4: 1200,
      Br: 2,
      PO4: 5,
      CO3: 10,
      SiO2: 80,
      B: 1.0,
      CO2: 5,
    },
  },
  {
    id: 'ww_textile_dyeing',
    name: '산업폐수(섬유/염색)',
    category: 'Waste',
    desc: 'Na/Cl/SO4 높음, pH 높을 수 있음',
    temp_C: 35,
    ph: 9.0,
    water_type: 'WW Wastewater',
    water_subtype: '섬유/염색',
    fouling: {
      sdi15: 6.5,
      turbidity_ntu: 30.0,
      tss_mgL: 50.0,
      toc_mgL: 40.0,
      cod_mgL: 120.0,
      bod_mgL: 40.0,
    },
    ions: {
      NH4: 5,
      K: 30,
      Na: 2500,
      Mg: 50,
      Ca: 80,
      Sr: 0.5,
      Ba: 0,
      Fe: 0.5,
      Mn: 0,
      HCO3: 500,
      NO3: 10,
      Cl: 3500,
      F: 0.5,
      SO4: 1500,
      Br: 10,
      PO4: 2,
      CO3: 50,
      SiO2: 15,
      B: 2.0,
      CO2: 0,
    },
  },

  // ==================================================
  // 재이용수 (Reuse) -> 서버 enum: WW Wastewater
  // ==================================================
  {
    id: 'ru_municipal_secondary',
    name: '하수 2차 처리수(방류수)',
    category: 'Reuse',
    desc: '암모니아/인 성분(바이오 파울링 주의)',
    temp_C: 25,
    ph: 7.1,
    water_type: 'WW Wastewater',
    water_subtype: '재이용수 - 2차 처리수',
    fouling: {
      sdi15: 4.5,
      turbidity_ntu: 3.0,
      tss_mgL: 8.0,
      toc_mgL: 12.0,
      cod_mgL: 35.0,
      bod_mgL: 10.0,
    },
    ions: {
      NH4: 25,
      K: 20,
      Na: 150,
      Mg: 30,
      Ca: 60,
      Sr: 0.5,
      Ba: 0,
      Fe: 0.5,
      Mn: 0.1,
      HCO3: 250,
      NO3: 35,
      Cl: 180,
      F: 0.5,
      SO4: 120,
      Br: 0,
      PO4: 12,
      CO3: 0,
      SiO2: 20,
      B: 0.5,
      CO2: 20,
    },
  },
  {
    id: 'ru_tertiary_filtered',
    name: '하수 3차 처리수(UF 여과수)',
    category: 'Reuse',
    desc: '탁도 낮음(RO/NF 전처리 후단 가정)',
    temp_C: 25,
    ph: 7.0,
    water_type: 'WW Wastewater', // 재이용수는 WW 계열로 취급하여 보수적 한계치 적용
    water_subtype: '재이용수 - 3차 처리수(UF)',
    fouling: {
      sdi15: 2.0, // UF를 거쳤으므로 입자성 오염물질은 거의 없음
      turbidity_ntu: 0.1,
      tss_mgL: 0.5,
      toc_mgL: 5.0,
      cod_mgL: 15.0,
      bod_mgL: 2.0,
    },
    ions: {
      NH4: 5,
      K: 18,
      Na: 140,
      Mg: 28,
      Ca: 55,
      Sr: 0.4,
      Ba: 0,
      Fe: 0.1,
      Mn: 0.05,
      HCO3: 200,
      NO3: 20,
      Cl: 170,
      F: 0.5,
      SO4: 110,
      Br: 0,
      PO4: 2,
      CO3: 0,
      SiO2: 18,
      B: 0.4,
      CO2: 10,
    },
  },
];
