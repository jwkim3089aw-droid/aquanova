// ui/src/features/flow-builder/FlowBuilder.utils.ts
import { Node } from "reactflow";
import {
  UnitKind,
  OLConfig,
  HRROConfig,
  ROConfig,
  NFConfig,
  MFConfig,
  UFConfig,
  UnitData,
  FlowData,
} from "./model/types";

// ==============================
// defaultConfig (유닛 초기값)
// ==============================

export function defaultConfig(k: UnitKind): OLConfig | HRROConfig {
  if (k === "HRRO") {
    const cfg: HRROConfig = {
      elements: 6,
      p_set_bar: 28,
      recirc_flow_m3h: 12,
      bleed_m3h: 0,
      loop_volume_m3: 2,
      makeup_tds_mgL: 35000,
      timestep_s: 5,
      max_minutes: 30,
      stop_permeate_tds_mgL: null,
      stop_recovery_pct: 60,

      // ✅ [NEW] advanced defaults
      mass_transfer: {
        recirc_flow_m3h: 12.0,
        feed_channel_area_m2: 0.0012,
        rho_kg_m3: 998.0,
        mu_pa_s: 0.001,
        diffusivity_m2_s: 1.5e-9,
        cp_exp_max: 5.0,
        cp_rel_tol: 1e-4,
        cp_abs_tol_lmh: 0.001,
        cp_relax: 0.5,
        cp_max_iter: 30,
      },
      spacer: {
        thickness_mm: 0.76,
        filament_diameter_mm: 0.35,
        voidage: 0.87,
      },
    };
    return cfg;
  }
  if (k === "RO") {
    const cfg: ROConfig = {
      elements: 6,
      mode: "pressure",
      pressure_bar: 16,
      recovery_target_pct: 45,
    };
    return cfg;
  }
  if (k === "NF") {
    const cfg: NFConfig = {
      elements: 6,
      mode: "pressure",
      pressure_bar: 10,
      recovery_target_pct: 75,
    };
    return cfg;
  }
  if (k === "MF") {
    const cfg: MFConfig = {
      elements: 6,
      mode: "pressure",
      pressure_bar: 1.0,
      recovery_target_pct: 95,
    };
    return cfg;
  }
  // UF — pressure/recovery 없음
  const uf: UFConfig = {
    elements: 6,
  };
  return uf;
}

// cfg 없는 유닛 노드에 defaultConfig를 채워 넣는 헬퍼
export function ensureUnitCfg(nodes: Node<FlowData>[]): Node<FlowData>[] {
  return nodes.map((n) => {
    const d: any = n.data;
    if (d?.type === "unit" && !d.cfg) {
      const kind = d.kind as UnitKind;
      return {
        ...n,
        data: {
          ...d,
          cfg: defaultConfig(kind),
        } as UnitData,
      } as Node<FlowData>;
    }
    return n;
  });
}