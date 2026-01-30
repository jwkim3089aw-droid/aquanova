// ui/src/features/flow-builder/data/water_catalog.ts

export type WaterPreset = {
  id: string;
  name: string;
  // [수정] WAVE처럼 Waste와 Reuse를 모두 포함
  category: "Seawater" | "Brackish" | "Surface" | "Waste" | "Reuse";
  desc: string;
  temp_C: number;
  ph: number;
  ions: {
    // Cations (+)
    NH4: number; K: number; Na: number; Mg: number; Ca: number;
    Sr: number; Ba: number; Fe: number; Mn: number;
    // Anions (-)
    HCO3: number; NO3: number; Cl: number; F: number; SO4: number;
    Br: number; PO4: number; CO3: number;
    // Neutrals
    SiO2: number; B: number; CO2: number;
  };
};

export const WATER_CATALOG: WaterPreset[] = [
  // ==================================================
  // 1. Seawater (해수)
  // ==================================================
  {
    id: "std_seawater_pacific",
    name: "Standard Seawater (Pacific)",
    category: "Seawater",
    desc: "ASTM Standard Seawater (TDS ~35,000)",
    temp_C: 25, ph: 8.1,
    ions: {
      NH4: 0, K: 399, Na: 10781, Mg: 1284, Ca: 412, Sr: 7.9, Ba: 0, Fe: 0.002, Mn: 0,
      HCO3: 142, NO3: 0, Cl: 19353, F: 1.3, SO4: 2712, Br: 67, PO4: 0, CO3: 0,
      SiO2: 6.0, B: 4.5, CO2: 0.5
    }
  },
  {
    id: "high_salinity_me",
    name: "High Salinity (Middle East)",
    category: "Seawater",
    desc: "Red Sea / Arabian Gulf (TDS ~45,000)",
    temp_C: 32, ph: 8.3,
    ions: {
      NH4: 0, K: 480, Na: 14500, Mg: 1800, Ca: 550, Sr: 12, Ba: 0, Fe: 0.01, Mn: 0,
      HCO3: 160, NO3: 0, Cl: 25000, F: 1.5, SO4: 3500, Br: 90, PO4: 0, CO3: 5,
      SiO2: 3.0, B: 6.0, CO2: 0
    }
  },

  // ==================================================
  // 2. Brackish Water (기수/지하수)
  // ==================================================
  {
    id: "brackish_well_std",
    name: "Brackish Well Water",
    category: "Brackish",
    desc: "Standard Groundwater (TDS ~1,500)",
    temp_C: 20, ph: 7.6,
    ions: {
      NH4: 0.5, K: 15, Na: 450, Mg: 80, Ca: 150, Sr: 2, Ba: 0.1, Fe: 0.5, Mn: 0.1,
      HCO3: 350, NO3: 10, Cl: 600, F: 0.8, SO4: 400, Br: 1, PO4: 0, CO3: 0,
      SiO2: 25, B: 0.5, CO2: 15
    }
  },

  // ==================================================
  // 3. Surface Water (강물/호수)
  // ==================================================
  {
    id: "river_water",
    name: "River Water (Surface)",
    category: "Surface",
    desc: "Low TDS, High Organics Potential",
    temp_C: 15, ph: 7.2,
    ions: {
      NH4: 0.2, K: 4, Na: 30, Mg: 10, Ca: 40, Sr: 0.1, Ba: 0, Fe: 0.3, Mn: 0.05,
      HCO3: 120, NO3: 3, Cl: 40, F: 0.2, SO4: 50, Br: 0, PO4: 0.1, CO3: 0,
      SiO2: 12, B: 0.1, CO2: 5
    }
  },

  // ==================================================
  // 4. Wastewater (산업폐수) - Scaling 주의
  // ==================================================
  {
    id: "cooling_tower_blowdown",
    name: "Cooling Tower Blowdown",
    category: "Waste",
    desc: "High Silica & Hardness (Scaling Risk)",
    temp_C: 30, ph: 8.0,
    ions: {
      // 증발 농축으로 인해 경도(Ca, Mg)와 실리카(SiO2), 황산염(SO4)이 매우 높음
      NH4: 1, K: 50, Na: 600, Mg: 180, Ca: 400, Sr: 3, Ba: 0.2, Fe: 1.0, Mn: 0.2,
      HCO3: 400, NO3: 20, Cl: 800, F: 1.0, SO4: 1200, Br: 2, PO4: 5, CO3: 10,
      SiO2: 80, B: 1.0, CO2: 5
    }
  },
  {
    id: "industrial_effluent_textile",
    name: "Industrial Effluent (Textile/Dyeing)",
    category: "Waste",
    desc: "High TDS & Conductivity",
    temp_C: 35, ph: 9.0,
    ions: {
      // 염색 폐수는 Na, Cl, SO4가 높고 pH가 높은 경향
      NH4: 5, K: 30, Na: 2500, Mg: 50, Ca: 80, Sr: 0.5, Ba: 0, Fe: 0.5, Mn: 0,
      HCO3: 500, NO3: 10, Cl: 3500, F: 0.5, SO4: 1500, Br: 10, PO4: 2, CO3: 50,
      SiO2: 15, B: 2.0, CO2: 0
    }
  },

  // ==================================================
  // 5. Reuse (재이용수) - Fouling 주의
  // ==================================================
  {
    id: "municipal_secondary",
    name: "Municipal Secondary Effluent",
    category: "Reuse",
    desc: "High Ammonia & Phosphate (Bio-fouling Risk)",
    temp_C: 25, ph: 7.1,
    ions: {
      // 하수 처리수는 암모니아, 인산염 등 영양염류가 높음
      NH4: 25, K: 20, Na: 150, Mg: 30, Ca: 60, Sr: 0.5, Ba: 0, Fe: 0.5, Mn: 0.1,
      HCO3: 250, NO3: 35, Cl: 180, F: 0.5, SO4: 120, Br: 0, PO4: 12, CO3: 0,
      SiO2: 20, B: 0.5, CO2: 20
    }
  },
  {
    id: "tertiary_ro_feed",
    name: "Tertiary Treated Reuse",
    category: "Reuse",
    desc: "Filtered Reuse Water (UF Permeate)",
    temp_C: 25, ph: 7.0,
    ions: {
      // 3차 처리(UF 등)를 거쳐 탁도는 낮으나 이온은 남아있음
      NH4: 5, K: 18, Na: 140, Mg: 28, Ca: 55, Sr: 0.4, Ba: 0, Fe: 0.1, Mn: 0.05,
      HCO3: 200, NO3: 20, Cl: 170, F: 0.5, SO4: 110, Br: 0, PO4: 2, CO3: 0,
      SiO2: 18, B: 0.4, CO2: 10
    }
  }
];