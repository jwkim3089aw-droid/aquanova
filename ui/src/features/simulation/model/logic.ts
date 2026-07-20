// ui/src/features/simulation/model/logic.ts
import { MarkerType, type Edge, type Node } from 'reactflow';

import type {
  StageConfig,
  StageMetric,
  ScenarioOutput,
  TimeSeriesPoint,
} from '@/api/types';

import type {
  FlowData,
  EndpointData,
  UnitData,
  UnitKind,
  UnitNode,
  ChainOk,
  ChainErr,
  UnitMode,
  SetNodesFn,
  SetEdgesFn,
  HRROConfig,
  UFConfig,
  MFConfig,
  ROConfig,
  MembraneStageConfig,
} from './types';

import {
  convPress,
  convFlux,
  unitLabel,
  fmt,
  MAX_FLUX_BY_KIND,
  clampInt,
  num,
  convFlow,
} from './types';

// 추가: 프론트엔드 카탈로그 조회를 위한 임포트
import { getFallbackMembrane } from '../data/membrane_catalog';

export const LS_KEY = 'aquanova.flowbuilder.v1';
export const LS_SCNS = 'aquanova.scenario.library.v1';

export function isUnitNode(
  n: Node<FlowData> | null | undefined,
): n is UnitNode {
  return !!n && (n.data as any)?.type === 'unit';
}

export function cryptoRandomId(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return (crypto as any).randomUUID();
  }
  return 'id_' + Math.random().toString(36).slice(2);
}

export function clone<T>(x: T): T {
  if (typeof (globalThis as any).structuredClone === 'function') {
    return (structuredClone as any)(x);
  }
  return JSON.parse(JSON.stringify(x));
}

export function buildLinearChain(
  nodes: Node<FlowData>[],
  edges: Edge[],
): ChainOk | ChainErr {
  const byId = new Map<string, Node<FlowData>>(nodes.map((n) => [n.id, n]));
  const outMap = new Map<string, string[]>();
  const inMap = new Map<string, string[]>();

  for (const e of edges) {
    if (!e.source || !e.target) continue;
    if (!outMap.has(e.source)) outMap.set(e.source, []);
    if (!inMap.has(e.target)) inMap.set(e.target, []);
    outMap.get(e.source)!.push(e.target);
    inMap.get(e.target)!.push(e.source);
  }

  const feed = nodes.find(
    (n) =>
      (n.data as any)?.type === 'endpoint' &&
      (n.data as EndpointData).role === 'feed',
  );
  const product = nodes.find(
    (n) =>
      (n.data as any)?.type === 'endpoint' &&
      (n.data as EndpointData).role === 'product',
  );

  if (!feed || !product) {
    return { ok: false, message: 'Feed/Product 노드가 필요합니다.' };
  }

  for (const n of nodes) {
    const outDeg = (outMap.get(n.id) || []).length;
    const inDeg = (inMap.get(n.id) || []).length;

    if (n.id === feed.id && inDeg > 0)
      return { ok: false, message: 'Feed에는 들어오는 간선이 없어야 합니다.' };
    if (n.id === product.id && outDeg > 0)
      return { ok: false, message: 'Product에는 나가는 간선이 없어야 합니다.' };
    if (n.id !== feed.id && n.id !== product.id) {
      if (outDeg > 1 || inDeg > 1)
        return {
          ok: false,
          message: '분기/병렬은 미지원(MVP). 단일 체인으로 연결해 주세요.',
        };
    }
  }

  const chain: UnitNode[] = [];
  const visited = new Set<string>();
  let cur = feed.id;
  let guard = 0;

  while (cur && guard++ < 1000) {
    visited.add(cur);
    const nexts = outMap.get(cur) || [];
    if (nexts.length > 1)
      return { ok: false, message: '분기 발견: 단일 경로만 허용됩니다.' };
    if (nexts.length === 0) {
      if (cur !== product.id)
        return { ok: false, message: 'Feed→Product 연결이 끊어졌습니다.' };
      break;
    }
    const nx = nexts[0]!;
    if (visited.has(nx))
      return { ok: false, message: '사이클이 발견되었습니다.' };
    const nxNode = byId.get(nx);
    if (!nxNode)
      return { ok: false, message: '존재하지 않는 노드로 연결되었습니다.' };
    if ((nxNode.data as any)?.type === 'unit') chain.push(nxNode as UnitNode);
    cur = nx;
  }
  return { ok: true, chain };
}

export function makeLinearEdges(nodes: Node<FlowData>[]): Edge[] {
  const feed = nodes.find(
    (n) =>
      (n.data as any)?.type === 'endpoint' &&
      (n.data as EndpointData).role === 'feed',
  );
  const product = nodes.find(
    (n) =>
      (n.data as any)?.type === 'endpoint' &&
      (n.data as EndpointData).role === 'product',
  );
  if (!feed || !product) return [];

  const units = nodes
    .filter((n) => (n.data as any)?.type === 'unit')
    .sort((a, b) => a.position.x - b.position.x);
  const chain = [feed, ...units, product];

  return chain.slice(0, -1).map((cur, i) => {
    const nxt = chain[i + 1]!;
    return {
      id: `e-${cur.id}-${nxt.id}`,
      source: cur.id,
      target: nxt.id,
      type: 'smoothstep',
      animated: true,
      markerEnd: { type: MarkerType.ArrowClosed },
    } as Edge;
  });
}

export function autoLinkLinear(
  nodes: Node<FlowData>[],
  setEdges: SetEdgesFn,
): void {
  setEdges(() => makeLinearEdges(nodes));
}

export function updateUnitCfg(
  id: string,
  cfg: any,
  setNodesFn: SetNodesFn,
): void {
  setNodesFn((arr) =>
    arr.map((n) =>
      n.id === id && (n.data as any)?.type === 'unit'
        ? ({ ...n, data: { ...(n.data as UnitData), cfg } } as Node<FlowData>)
        : n,
    ),
  );
}

export function nudge(
  id: string,
  dx: number,
  dy: number,
  setNodesFn: SetNodesFn,
): void {
  const STEP = 24;
  setNodesFn((arr) =>
    arr.map((n) =>
      n.id === id
        ? {
            ...n,
            position: {
              x: n.position.x + dx * STEP,
              y: n.position.y + dy * STEP,
            },
          }
        : n,
    ),
  );
}

export function removeNode(
  id: string,
  setNodesFn: SetNodesFn,
  setEdgesFn: SetEdgesFn,
): void {
  if (id === 'feed' || id === 'product') return;
  setEdgesFn((eds) => eds.filter((e) => e.source !== id && e.target !== id));
  setNodesFn((nds) => nds.filter((n) => n.id !== id));
}

export function reorderNode(
  id: string,
  dir: -1 | 1,
  setNodesFn: SetNodesFn,
): void {
  setNodesFn((nds) => {
    const units = nds
      .filter((n) => (n.data as any)?.type === 'unit')
      .sort((a, b) => a.position.x - b.position.x);
    const idx = units.findIndex((n) => n.id === id);
    if (idx < 0) return nds;
    const swapIdx = idx + dir;
    if (swapIdx < 0 || swapIdx >= units.length) return nds;

    const a = units[idx]!;
    const b = units[swapIdx]!;
    const ax = a.position.x;
    const bx = b.position.x;

    return nds.map((n) => {
      if (n.id === a.id) return { ...n, position: { ...n.position, x: bx } };
      if (n.id === b.id) return { ...n, position: { ...n.position, x: ax } };
      return n;
    });
  });
}

export function bulkApply(
  mode: 'pressure' | 'recovery',
  value: number,
  setNodesFn: SetNodesFn,
): void {
  setNodesFn((arr) =>
    arr.map((n) => {
      const d = n.data as any;
      if (!d || d.type !== 'unit') return n;
      if (d.kind === 'HRRO' || d.kind === 'PUMP') return n;

      const c = d.cfg as any;
      if (mode === 'pressure') {
        return {
          ...n,
          data: { ...d, cfg: { ...c, mode: 'pressure', pressure_bar: value } },
        } as Node<FlowData>;
      }
      return {
        ...n,
        data: {
          ...d,
          cfg: { ...c, mode: 'recovery', recovery_target_pct: value },
        },
      } as Node<FlowData>;
    }),
  );
}

function metricFluxSI(m: StageMetric): number | null {
  const v = m.flux_lmh ?? (m as any).jw_avg_lmh;
  return typeof v === 'number' ? v : null;
}

function metricSec(m: StageMetric): number | null {
  const v = m.sec_kwhm3 ?? (m as any).sec_kwh_m3;
  return typeof v === 'number' ? v : null;
}

function metricPin(m: StageMetric): number | null {
  const v = m.p_in_bar ?? (m as any).pin;
  return typeof v === 'number' ? v : null;
}

function metricPout(m: StageMetric): number | null {
  const v = m.p_out_bar ?? (m as any).pout;
  return typeof v === 'number' ? v : null;
}

export function applyStageChips(
  nodeIdsInStageOrder: string[],
  metrics: StageMetric[] | undefined | null,
  kpi: any,
  unitMode: UnitMode,
  setNodesFn: SetNodesFn,
): void {
  const stageMap = new Map<number, StageMetric>();
  if (metrics) {
    for (const m of metrics) stageMap.set(m.stage, m);
  }

  setNodesFn((arr) =>
    arr.map((n) => {
      const d = n.data as any;
      if (!d || d.type !== 'unit') return n;

      const kind = d.kind as UnitKind;
      if (kind === 'PUMP') return n;

      const idx = nodeIdsInStageOrder.indexOf(n.id);
      if (idx < 0) return n;

      const m = stageMap.get(idx + 1) ?? (metrics ? metrics[idx] : undefined);
      let jw_disp: number | undefined;
      let dp_disp: number | undefined;
      let sec_disp: number | undefined;

      if (m) {
        const jw_si = metricFluxSI(m);
        const pin_si = metricPin(m);
        const pout_si = metricPout(m);
        const sec_si = metricSec(m);

        if (jw_si != null)
          jw_disp = unitMode === 'SI' ? jw_si : convFlux(jw_si, 'SI', 'US');
        if (pin_si != null && pout_si != null) {
          const dp_bar = pin_si - pout_si;
          dp_disp = unitMode === 'SI' ? dp_bar : convPress(dp_bar, 'SI', 'US');
        }
        if (sec_si != null) sec_disp = sec_si;
      } else if (kpi) {
        jw_disp =
          unitMode === 'SI' ? kpi.flux_lmh : convFlux(kpi.flux_lmh, 'SI', 'US');
        sec_disp = kpi.sec_kwhm3;
      }

      const maxLMH = MAX_FLUX_BY_KIND[kind] ?? 0;
      const thresh = unitMode === 'SI' ? maxLMH : convFlux(maxLMH, 'SI', 'US');
      const warn = typeof jw_disp === 'number' && jw_disp > thresh + 1e-6;
      const chips: any[] = [];

      if (jw_disp != null)
        chips.push({
          label: unitLabel('flux', unitMode),
          value: fmt(jw_disp),
          warn,
          tip: warn ? `권고 상한(${fmt(thresh)}) 초과` : undefined,
        });
      if (dp_disp != null)
        chips.push({
          label: 'ΔP ' + unitLabel('press', unitMode),
          value: fmt(dp_disp),
        });
      if (sec_disp != null)
        chips.push({ label: 'SEC kWh/m³', value: fmt(sec_disp, 3) });

      return { ...n, data: { ...d, chips } } as Node<FlowData>;
    }),
  );
}

function getMemParams(c: any) {
  if (c?.membrane_mode === 'custom') {
    return {
      membrane_model: null,
      membrane_area_m2: num(c.custom_area_m2, 0) || null,
      membrane_A_lmh_bar: num(c.custom_A_lmh_bar, 0) || null,
      membrane_B_lmh: num(c.custom_B_lmh, 0) || null,
      membrane_salt_rejection_pct: num(c.custom_salt_rejection_pct, 0) || null,
      temp_corr_factor_A: null,
      temp_corr_factor_B: null,
      cp_adjustment_factor: null,
      fouling_factor: null,
      dp_per_elem_bar: null,
      A_correction_factor: null,
      B_correction_factor: null,
    };
  }

  // 기본 카탈로그 선택 시, 저장된 모델명을 기반으로 물리 계수 매핑
  const targetModel = c?.membrane_model || null;
  const spec = getFallbackMembrane(targetModel);

  return {
    membrane_model: targetModel,
    membrane_area_m2: spec?.area_m2 || null,
    membrane_A_lmh_bar: spec?.A_lmh_bar || null,
    membrane_B_lmh: spec?.B_lmh || null,
    membrane_salt_rejection_pct: spec?.salt_rejection_pct || null,

    A_correction_factor: spec?.A_correction_factor || null,
    B_correction_factor: spec?.B_correction_factor || null,
    // --- [WAVE 물리 보정 계수 데이터 주입] ---
    temp_corr_factor_A: spec?.temp_corr_factor_A || null,
    temp_corr_factor_B: spec?.temp_corr_factor_B || null,
    cp_adjustment_factor: spec?.cp_adjustment_factor || null,
    fouling_factor: spec?.fouling_factor || null,
    dp_per_elem_bar: spec?.dp_per_elem_bar || null,
  };
}

export function defaultConfig(k: UnitKind): StageConfig {
  const baseConfig: Partial<StageConfig> = {
    module_type: k as any,
    element_inch: 8,
    vessel_count: 10,
    elements_per_vessel: 5,
    elements: 50,
    membrane_area_m2: 40.9,
    flow_factor: 0.85,
    permeate_back_pressure_bar: 0.0,
    burst_pressure_limit_bar: 83.0,
  };

  if (k === 'HRRO') {
    return {
      ...baseConfig,
      module_type: 'HRRO',
      membrane_model: 'filmtec-soar-5000i',
      membrane_area_m2: 37.16,
      flow_factor: 1.0,
      membrane_A_lmh_bar: 5.5,
      membrane_B_lmh: 0.06,
      membrane_salt_rejection_pct: 99.5,
      pressure_bar: 50.0,
      recovery_target_pct: 90.0,
      stop_recovery_pct: 90.0,
      loop_volume_m3: 1.36,
      recirc_flow_m3h: 120.0,
      max_minutes: 60.0,
      timestep_s: 5,
      hrro_engine: 'physics',
      cc_recycle_m3h_per_pv: 4.33,
      pf_feed_ratio_pct: 150.0,
      pf_recovery_pct: 10.0,
      pf_mode: 'smart_partial_drain',
      brine_valve_mode: 'full_open',
      p3_recycle_capacity_m3h_per_pv: 4.54,
      pf_cp_assist_enabled: false,
      pf_cp_assist_flow_m3h_per_pv: 0.0,
      adaptive_recovery_enabled: false,
      brine_conductivity_limit_mgL: null,
      brine_tds_limit_mgL: null,
      hpp_safe_pressure_limit_bar: null,
      hpp_sizing_mode: 'base',
      hpp_count: 1,
      p3_generated_head_bar: 0.6,
      p3_casing_pressure_rating_bar: 12.0,
      mass_transfer: {
        feed_channel_area_m2: 0.015,
        rho_kg_m3: 998.0,
        mu_pa_s: 0.001,
        diffusivity_m2_s: 1.5e-9,
      },
      spacer: {
        thickness_mm: 0.864,
        filament_diameter_mm: 0.35,
        voidage: 0.88,
      },
    } as StageConfig;
  }

  if (k === 'RO') {
    return {
      ...baseConfig,
      module_type: 'RO',
      membrane_model: 'filmtec-bw30-400',
      membrane_A_lmh_bar: 4.0,
      membrane_B_lmh: 0.5,
      pressure_bar: 15.0,
      recovery_target_pct: 50.0,
    } as StageConfig;
  }

  if (k === 'NF') {
    return {
      ...baseConfig,
      module_type: 'NF',
      pressure_bar: 10.0,
      recovery_target_pct: 75.0,
    } as StageConfig;
  }

  if (k === 'MF') {
    return {
      ...baseConfig,
      module_type: 'MF',
      pressure_bar: 1.0,
      recovery_target_pct: 95.0,
      filtration_cycle_min: 30,
      backwash_duration_sec: 60,
    } as StageConfig;
  }

  return {
    ...baseConfig,
    module_type: 'UF',
    pressure_bar: 2.0,
    flow_factor: 1.3,
    filtration_cycle_min: 30,
    backwash_duration_sec: 60,
  } as StageConfig;
}

export function ensureUnitCfg(nodes: Node<FlowData>[]): Node<FlowData>[] {
  return nodes.map((n) => {
    const d: any = n.data;
    if (d?.type === 'unit' && !d.cfg) {
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

export function toStagePayload(
  n: UnitNode,
  currentUnitMode: UnitMode,
  globals?: { defaultMembraneModel?: string; pumpEff?: number },
): StageConfig[] {
  const d = n.data as UnitData;
  const kind = (d as any).kind as UnitKind;
  const c = (d as any).cfg as any;
  const globalMem = globals?.defaultMembraneModel;

  if (c?.membrane_mode !== 'custom') {
    if (!c?.membrane_model && globalMem && globalMem !== 'AUTO') {
      c.membrane_model = globalMem;
    }
  }

  if (kind === 'HRRO') {
    const cfg = c as HRROConfig;
    let pressureVal = num(cfg.p_set_bar, 60);
    if (currentUnitMode !== 'SI')
      pressureVal = convPress(pressureVal, 'US', 'SI');
    const stopRec =
      Number(cfg.stop_recovery_pct) ||
      Number((cfg as any).recovery_target_pct) ||
      90.0;

    return [
      {
        stage_id: n.id,
        module_type: 'HRRO',
        elements: clampInt(cfg.elements, 1, 10000),
        pressure_bar: Number(pressureVal),
        loop_volume_m3: num(cfg.loop_volume_m3, 2.0),
        recirc_flow_m3h: num(cfg.recirc_flow_m3h, 120),
        bleed_m3h: num(cfg.bleed_m3h, 0),
        timestep_s: clampInt(cfg.timestep_s, 1, 60),
        max_minutes: num(cfg.max_minutes, 60),
        stop_permeate_tds_mgL: cfg.stop_permeate_tds_mgL ?? null,
        stop_recovery_pct: stopRec,
        recovery_target_pct: stopRec,
        hrro_engine: 'physics',
        hrro_excel_only_cp_mode: 'min_model',
        hrro_excel_only_fixed_rejection_pct: 99.5,
        hrro_excel_only_min_model_rejection_pct: null,
        element_inch: cfg.element_inch ?? 8,
        vessel_count: cfg.vessel_count ?? 10,
        elements_per_vessel: cfg.elements_per_vessel ?? 5,
        feed_flow_m3h: cfg.feed_flow_m3h ?? null,
        ccro_recovery_pct: cfg.ccro_recovery_pct ?? null,
        pf_feed_ratio_pct: cfg.pf_feed_ratio_pct ?? 150.0,
        pf_recovery_pct: cfg.pf_recovery_pct ?? 10.0,
        cc_recycle_m3h_per_pv: cfg.cc_recycle_m3h_per_pv ?? null,

        // V83: pass V82 HRRO smart-PF/adaptive-control fields through to API
        pf_mode: cfg.pf_mode ?? 'smart_partial_drain',
        brine_valve_mode:
          cfg.brine_valve_mode ??
          ((cfg.pf_mode ?? 'smart_partial_drain') === 'wave_true_plug_flow'
            ? 'full_open'
            : 'partial_pid'),
        p3_recycle_capacity_m3h_per_pv:
          cfg.p3_recycle_capacity_m3h_per_pv ?? null,
        pf_cp_assist_enabled: cfg.pf_cp_assist_enabled ?? null,
        pf_cp_assist_flow_m3h_per_pv:
          cfg.pf_cp_assist_flow_m3h_per_pv ?? null,
        adaptive_recovery_enabled: cfg.adaptive_recovery_enabled ?? false,
        brine_conductivity_limit_mgL:
          cfg.brine_conductivity_limit_mgL ?? null,
        brine_tds_limit_mgL: cfg.brine_tds_limit_mgL ?? null,
        hpp_safe_pressure_limit_bar: cfg.hpp_safe_pressure_limit_bar ?? null,
        hpp_sizing_mode: cfg.hpp_sizing_mode ?? 'base',
        hpp_count: cfg.hpp_count ?? 1,
        p3_generated_head_bar: cfg.p3_generated_head_bar ?? 0.6,
        p3_casing_pressure_rating_bar:
          cfg.p3_casing_pressure_rating_bar ?? 12.0,

        membrane_area_m2_per_element: undefined,
        pump_eff: cfg.pump_eff ?? globals?.pumpEff ?? 0.8,
        mass_transfer: cfg.mass_transfer ?? null,
        spacer: cfg.spacer ?? null,
        flow_factor: num(cfg.flow_factor, 0.85),
        ...getMemParams(cfg),
      },
    ];
  }

  if (kind === 'UF' || kind === 'MF') {
    const isUF = kind === 'UF';
    const uf = c as UFConfig;
    const mf = c as MFConfig;
    const filtrateFluxDisp = isUF
      ? num(uf.filtrate_flux_lmh_25C, 60)
      : num(mf.mf_filtrate_flux_lmh_25C, 60);
    const backwashFluxDisp = isUF
      ? num(uf.backwash_flux_lmh, 120)
      : num(mf.mf_backwash_flux_lmh, 120);
    const filtrateFluxSI =
      currentUnitMode === 'SI'
        ? filtrateFluxDisp
        : convFlux(filtrateFluxDisp, 'US', 'SI');
    const backwashFluxSI =
      currentUnitMode === 'SI'
        ? backwashFluxDisp
        : convFlux(backwashFluxDisp, 'US', 'SI');

    return [
      {
        stage_id: n.id,
        module_type: kind,
        elements: clampInt(c.elements, 1, 24),
        pressure_bar: 0.0,
        flux_lmh: filtrateFluxSI,
        backwash_flux_lmh: backwashFluxSI,
        filtration_cycle_min: isUF
          ? num(uf.filtration_duration_min, 30)
          : num(mf.mf_filtration_duration_min, 30),
        backwash_duration_sec: isUF
          ? num(uf.uf_backwash_duration_s, 60)
          : num(mf.mf_backwash_duration_s, 60),
        recovery_target_pct: num(c.recovery_target_pct, 90.0),
        strainer_recovery_pct: num(c.strainer_recovery_pct, 99.5),
        strainer_size_micron: num(c.strainer_size_micron, 150.0),
        ...getMemParams(c),
      },
    ];
  }

  const rnf = c as ROConfig;
  const opMode = rnf.mode || 'recovery';
  let sysPressureVal = num(rnf.pressure_bar, 15);
  if (currentUnitMode !== 'SI')
    sysPressureVal = convPress(sysPressureVal, 'US', 'SI');
  let backPressSI = num(rnf.permeate_back_pressure_bar, 0);
  let flowTargetSI = num(rnf.flow_target_m3h, 50);
  if (currentUnitMode !== 'SI') {
    backPressSI = convPress(backPressSI, 'US', 'SI');
    flowTargetSI = convFlow(flowTargetSI, 'US', 'SI');
  }

  const results: StageConfig[] = [];
  if (rnf.stages && rnf.stages.length > 0) {
    rnf.stages.forEach((stg: MembraneStageConfig, idx: number) => {
      let stageDpSI = num(stg.pre_stage_dp_bar, 0);
      let stageIsbpSI = num(stg.isbp_pressure_bar, 0);
      if (currentUnitMode !== 'SI') {
        stageDpSI = convPress(stageDpSI, 'US', 'SI');
        stageIsbpSI = convPress(stageIsbpSI, 'US', 'SI');
      }
      results.push({
        stage_id: n.id,
        stage_idx: stg.stage_idx || idx + 1,
        module_type: kind,
        elements: clampInt(
          (stg.vessel_count || 1) * (stg.elements_per_vessel || 6),
          1,
          10000,
        ),
        vessel_count: stg.vessel_count ?? 1,
        elements_per_vessel: stg.elements_per_vessel ?? 6,
        flow_factor: stg.flow_factor ?? 0.85,
        spi: stg.spi ?? 1.1,
        pre_stage_dp_bar: stageDpSI,
        isbp_pressure_bar: stageIsbpSI,
        isbp_eff_pct: stg.isbp_eff_pct ?? 80.0,
        permeate_back_pressure_bar: backPressSI,
        mode: opMode,
        pressure_bar:
          idx === 0 && opMode === 'pressure'
            ? Number(sysPressureVal)
            : undefined,
        recovery_target_pct:
          idx === 0 && opMode === 'recovery'
            ? num(rnf.recovery_target_pct, 50)
            : undefined,
        flow_target_m3h:
          idx === 0 && opMode === 'flow' ? flowTargetSI : undefined,
        pump_eff: globals?.pumpEff ?? undefined,
        ...getMemParams(c),
      });
    });
  } else {
    let dpSI = num(rnf.pre_stage_dp_bar, 0.3);
    if (currentUnitMode !== 'SI') dpSI = convPress(dpSI, 'US', 'SI');
    results.push({
      stage_id: n.id,
      stage_idx: 1,
      module_type: kind,
      elements: clampInt(rnf.elements, 1, 10000),
      vessel_count: rnf.vessel_count ?? 1,
      elements_per_vessel: rnf.elements_per_vessel ?? rnf.elements ?? 6,
      flow_factor: rnf.flow_factor ?? 0.85,
      spi: rnf.spi ?? 1.1,
      pre_stage_dp_bar: dpSI,
      isbp_pressure_bar: 0.0,
      isbp_eff_pct: 80.0,
      permeate_back_pressure_bar: backPressSI,
      mode: opMode,
      pressure_bar: opMode === 'pressure' ? Number(sysPressureVal) : undefined,
      recovery_target_pct:
        opMode === 'recovery' ? num(rnf.recovery_target_pct, 50) : undefined,
      flow_target_m3h: opMode === 'flow' ? flowTargetSI : undefined,
      pump_eff: globals?.pumpEff ?? undefined,
      ...getMemParams(c),
    });
  }
  return results;
}

function normalizeTimeHistory(
  ts?: TimeSeriesPoint[] | null,
): TimeSeriesPoint[] | null {
  if (!ts || !Array.isArray(ts)) return ts ?? null;
  return ts.map((p) => ({
    ...p,
    flux_lmh: p.flux_lmh ?? null,
    ndp_bar: p.ndp_bar ?? null,
    permeate_flow_m3h: p.permeate_flow_m3h ?? null,
    permeate_tds_mgL: p.permeate_tds_mgL ?? null,
  }));
}

function normalizeStageMetric(m: any): StageMetric {
  if (!m || typeof m !== 'object') return m as StageMetric;
  const flux = m.flux_lmh ?? m.jw_avg_lmh ?? null;
  const sec = m.sec_kwhm3 ?? m.sec_kwh_m3 ?? null;
  const pin = m.p_in_bar ?? m.pin ?? null;
  const pout = m.p_out_bar ?? m.pout ?? null;
  return {
    ...m,
    flux_lmh: typeof flux === 'number' ? flux : m.flux_lmh,
    sec_kwhm3: typeof sec === 'number' ? sec : m.sec_kwhm3,
    p_in_bar: typeof pin === 'number' ? pin : m.p_in_bar,
    p_out_bar: typeof pout === 'number' ? pout : m.p_out_bar,
    time_history: normalizeTimeHistory(m.time_history),
  } as StageMetric;
}

export function normalizeScenarioOutput(out: ScenarioOutput): ScenarioOutput {
  const cp = clone(out);
  if (cp.stage_metrics)
    cp.stage_metrics = (cp.stage_metrics as any[]).map(normalizeStageMetric);
  if (cp.time_history) cp.time_history = normalizeTimeHistory(cp.time_history);
  return cp;
}

export function convertScenarioOutToDisplay(
  out: ScenarioOutput,
  mode: UnitMode,
): ScenarioOutput {
  const base = normalizeScenarioOutput(out);
  if (mode === 'SI') return base;
  const cp = clone(base);
  if (cp.kpi) {
    if (typeof cp.kpi.flux_lmh === 'number')
      cp.kpi.flux_lmh = convFlux(cp.kpi.flux_lmh, 'SI', 'US');
    if (typeof cp.kpi.ndp_bar === 'number')
      cp.kpi.ndp_bar = convPress(cp.kpi.ndp_bar, 'SI', 'US');
    if (typeof cp.kpi.feed_m3h === 'number')
      cp.kpi.feed_m3h = convFlow(cp.kpi.feed_m3h, 'SI', 'US');
    if (typeof cp.kpi.permeate_m3h === 'number')
      cp.kpi.permeate_m3h = convFlow(cp.kpi.permeate_m3h, 'SI', 'US');
  }
  if (cp.streams) {
    cp.streams = cp.streams.map((s: any) => ({
      ...s,
      flow_m3h:
        typeof s.flow_m3h === 'number'
          ? convFlow(s.flow_m3h, 'SI', 'US')
          : s.flow_m3h,
      pressure_bar:
        typeof s.pressure_bar === 'number'
          ? convPress(s.pressure_bar, 'SI', 'US')
          : s.pressure_bar,
    }));
  }
  if (cp.stage_metrics) {
    cp.stage_metrics = cp.stage_metrics.map((m: StageMetric) => ({
      ...m,
      p_in_bar:
        typeof m.p_in_bar === 'number'
          ? convPress(m.p_in_bar, 'SI', 'US')
          : m.p_in_bar,
      p_out_bar:
        typeof m.p_out_bar === 'number'
          ? convPress(m.p_out_bar, 'SI', 'US')
          : m.p_out_bar,
      flux_lmh:
        typeof m.flux_lmh === 'number'
          ? convFlux(m.flux_lmh, 'SI', 'US')
          : m.flux_lmh,
      ndp_bar:
        typeof m.ndp_bar === 'number'
          ? convPress(m.ndp_bar, 'SI', 'US')
          : m.ndp_bar,
      delta_pi_bar:
        typeof m.delta_pi_bar === 'number'
          ? convPress(m.delta_pi_bar, 'SI', 'US')
          : m.delta_pi_bar,
      time_history: m.time_history
        ? m.time_history.map((p) => ({
            ...p,
            pressure_bar:
              typeof p.pressure_bar === 'number'
                ? convPress(p.pressure_bar, 'SI', 'US')
                : p.pressure_bar,
            flux_lmh:
              typeof p.flux_lmh === 'number'
                ? convFlux(p.flux_lmh, 'SI', 'US')
                : p.flux_lmh,
            ndp_bar:
              typeof p.ndp_bar === 'number'
                ? convPress(p.ndp_bar, 'SI', 'US')
                : p.ndp_bar,
            permeate_flow_m3h:
              typeof p.permeate_flow_m3h === 'number'
                ? convFlow(p.permeate_flow_m3h, 'SI', 'US')
                : p.permeate_flow_m3h,
          }))
        : m.time_history,
    }));
  }
  if (cp.time_history) {
    cp.time_history = cp.time_history.map((p) => ({
      ...p,
      pressure_bar:
        typeof p.pressure_bar === 'number'
          ? convPress(p.pressure_bar, 'SI', 'US')
          : p.pressure_bar,
      flux_lmh:
        typeof p.flux_lmh === 'number'
          ? convFlux(p.flux_lmh, 'SI', 'US')
          : p.flux_lmh,
      ndp_bar:
        typeof p.ndp_bar === 'number'
          ? convPress(p.ndp_bar, 'SI', 'US')
          : p.ndp_bar,
      permeate_flow_m3h:
        typeof p.permeate_flow_m3h === 'number'
          ? convFlow(p.permeate_flow_m3h, 'SI', 'US')
          : p.permeate_flow_m3h,
    }));
  }
  return cp;
}

export const convertROutToDisplay = convertScenarioOutToDisplay;

export function loadLibrary(): any[] {
  try {
    const raw = localStorage.getItem(LS_SCNS);
    if (!raw) return [];
    return JSON.parse(raw);
  } catch {
    return [];
  }
}

export function resolveProjectId(): string {
  const raw = (import.meta as any)?.env?.VITE_PROJECT_ID as string | undefined;
  return (raw && raw.trim()) || 'default';
}

export function pickStageTypeForMem(
  unitKinds: UnitKind[],
): UnitKind | undefined {
  if (unitKinds.includes('RO')) return 'RO';
  if (unitKinds.includes('HRRO')) return 'HRRO';
  if (unitKinds.includes('NF')) return 'NF';
  if (unitKinds.includes('UF')) return 'UF';
  if (unitKinds.includes('MF')) return 'MF';
  return undefined;
}
