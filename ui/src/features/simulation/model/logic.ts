// ui\src\features\simulation\model\logic.ts
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
  NFConfig,
  ROConfig,
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
  convTemp,
} from './types';

// ==============================
// LocalStorage keys
// ==============================

export const LS_KEY = 'aquanova.flowbuilder.v1';
export const LS_SCNS = 'aquanova.scenario.library.v1';

// ==============================
// Small helpers
// ==============================

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

// ==============================
// Chain builder / validator
// ==============================

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

  // degree checks
  for (const n of nodes) {
    const outDeg = (outMap.get(n.id) || []).length;
    const inDeg = (inMap.get(n.id) || []).length;

    if (n.id === feed.id && inDeg > 0) {
      return { ok: false, message: 'Feed에는 들어오는 간선이 없어야 합니다.' };
    }
    if (n.id === product.id && outDeg > 0) {
      return { ok: false, message: 'Product에는 나가는 간선이 없어야 합니다.' };
    }

    if (n.id !== feed.id && n.id !== product.id) {
      if (outDeg > 1 || inDeg > 1) {
        return {
          ok: false,
          message: '분기/병렬은 미지원(MVP). 단일 체인으로 연결해 주세요.',
        };
      }
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

// ==============================
// Auto link (Feed → Units → Product)
// ==============================

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

// ==============================
// Node mutations
// ==============================

export function updateUnitCfg(
  id: string,
  cfg: any,
  setNodesFn: SetNodesFn,
): void {
  setNodesFn((arr) =>
    arr.map((n) =>
      n.id === id && (n.data as any)?.type === 'unit'
        ? ({
            ...n,
            data: { ...(n.data as UnitData), cfg },
          } as Node<FlowData>)
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

// ==============================
// Chips mapping (StageMetric aligned)
// ==============================

function metricFluxSI(m: StageMetric): number | null {
  const v = m.flux_lmh ?? m.jw_avg_lmh;
  return typeof v === 'number' ? v : null;
}

function metricSec(m: StageMetric): number | null {
  const v = m.sec_kwhm3 ?? m.sec_kwh_m3;
  return typeof v === 'number' ? v : null;
}

function metricPin(m: StageMetric): number | null {
  const v = m.p_in_bar ?? m.pin;
  return typeof v === 'number' ? v : null;
}

function metricPout(m: StageMetric): number | null {
  const v = m.p_out_bar ?? m.pout;
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

        if (sec_si != null) sec_disp = sec_si; // kWh/m3 is not unit-switched
      } else if (kpi) {
        jw_disp =
          unitMode === 'SI' ? kpi.flux_lmh : convFlux(kpi.flux_lmh, 'SI', 'US');
        sec_disp = kpi.sec_kwhm3;
      }

      const maxLMH = MAX_FLUX_BY_KIND[kind] ?? 0;
      const thresh = unitMode === 'SI' ? maxLMH : convFlux(maxLMH, 'SI', 'US');
      const warn = typeof jw_disp === 'number' && jw_disp > thresh + 1e-6;

      const chips: any[] = [];

      if (jw_disp != null) {
        chips.push({
          label: unitLabel('flux', unitMode),
          value: fmt(jw_disp),
          warn,
          tip: warn ? `권고 상한(${fmt(thresh)}) 초과` : undefined,
        });
      }
      if (dp_disp != null) {
        chips.push({
          label: 'ΔP ' + unitLabel('press', unitMode),
          value: fmt(dp_disp),
        });
      }
      if (sec_disp != null) {
        chips.push({
          label: 'SEC kWh/m³',
          value: fmt(sec_disp, 3),
        });
      }

      return { ...n, data: { ...d, chips } } as Node<FlowData>;
    }),
  );
}

// =========================================================================
// Stage payload builders (SI contract) + PUMP 제외는 useFlowLogic에서 처리
// =========================================================================

function getMemParams(c: any) {
  if (c?.membrane_mode === 'custom') {
    return {
      membrane_model: null,
      membrane_area_m2: num(c.custom_area_m2, 0) || null,
      membrane_A_lmh_bar: num(c.custom_A_lmh_bar, 0) || null,
      membrane_B_lmh: num(c.custom_B_lmh, 0) || null,
      membrane_salt_rejection_pct: num(c.custom_salt_rejection_pct, 0) || null,
    };
  }
  return {
    membrane_model: c?.membrane_model || null,
    membrane_area_m2: null,
    membrane_A_lmh_bar: null,
    membrane_B_lmh: null,
    membrane_salt_rejection_pct: null,
  };
}

/**
 * Convert a unit node -> backend StageConfig (always SI internally).
 * - pressure: bar
 * - flow: m3/h
 * - flux: LMH
 */
export function toStagePayload(
  n: UnitNode,
  currentUnitMode: UnitMode,
  globals?: { defaultMembraneModel?: string; pumpEff?: number },
): StageConfig {
  const d = n.data as UnitData;
  const kind = (d as any).kind as UnitKind;
  const c = (d as any).cfg as any;

  // global membrane fallback (catalog)
  const globalMem = globals?.defaultMembraneModel;
  if (c?.membrane_mode !== 'custom') {
    if (!c?.membrane_model && globalMem && globalMem !== 'AUTO') {
      c.membrane_model = globalMem;
    }
  }

  // 1) pressure SI (bar)
  let pressureVal = 15.0;
  if (kind === 'HRRO') pressureVal = num((c as HRROConfig).p_set_bar, 60);
  else if (c?.mode === 'pressure') pressureVal = num(c.pressure_bar, 15);

  if (currentUnitMode !== 'SI') {
    pressureVal = convPress(num(pressureVal, 15), 'US', 'SI');
  }

  // 2) HRRO
  if (kind === 'HRRO') {
    const cfg = c as HRROConfig;

    const stopRec =
      Number(cfg.stop_recovery_pct) ||
      Number((cfg as any).recovery_target_pct) ||
      90.0;

    return {
      stage_id: n.id,
      module_type: 'HRRO',
      elements: clampInt(cfg.elements, 1, 24),

      pressure_bar: Number(pressureVal),

      // closed-loop
      loop_volume_m3: num(cfg.loop_volume_m3, 2),
      recirc_flow_m3h: num(cfg.recirc_flow_m3h, 12),
      bleed_m3h: num(cfg.bleed_m3h, 0),
      timestep_s: clampInt(cfg.timestep_s, 1, 60),
      max_minutes: num(cfg.max_minutes, 60),
      stop_permeate_tds_mgL: cfg.stop_permeate_tds_mgL ?? null,

      // hard stop (critical)
      stop_recovery_pct: stopRec,
      recovery_target_pct: stopRec,

      // excel inputs
      hrro_engine: cfg.hrro_engine ?? 'excel_only',
      hrro_excel_only_cp_mode: cfg.hrro_excel_only_cp_mode ?? 'min_model',
      hrro_excel_only_fixed_rejection_pct:
        cfg.hrro_excel_only_fixed_rejection_pct ?? 99.5,
      hrro_excel_only_min_model_rejection_pct:
        cfg.hrro_excel_only_min_model_rejection_pct ?? null,

      element_inch: cfg.element_inch ?? 8,
      vessel_count: cfg.vessel_count ?? 1,
      elements_per_vessel: cfg.elements_per_vessel ?? cfg.elements ?? 6,

      feed_flow_m3h: cfg.feed_flow_m3h ?? null,
      ccro_recovery_pct: cfg.ccro_recovery_pct ?? null,
      pf_feed_ratio_pct: cfg.pf_feed_ratio_pct ?? 110.0,
      pf_recovery_pct: cfg.pf_recovery_pct ?? 10.0,
      cc_recycle_m3h_per_pv: cfg.cc_recycle_m3h_per_pv ?? null,
      membrane_area_m2_per_element: cfg.membrane_area_m2_per_element ?? null,

      pump_eff: cfg.pump_eff ?? globals?.pumpEff ?? 0.8,

      mass_transfer: cfg.mass_transfer ?? null,
      spacer: cfg.spacer ?? null,

      ...getMemParams(cfg),
    };
  }

  // 3) UF/MF (flux in SI LMH)
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

    // convert gfd -> LMH when in US mode
    const filtrateFluxSI =
      currentUnitMode === 'SI'
        ? filtrateFluxDisp
        : convFlux(filtrateFluxDisp, 'US', 'SI');
    const backwashFluxSI =
      currentUnitMode === 'SI'
        ? backwashFluxDisp
        : convFlux(backwashFluxDisp, 'US', 'SI');

    return {
      stage_id: n.id,
      module_type: kind,
      elements: clampInt(c.elements, 1, 24),

      // not pressure-controlled; keep >=0
      pressure_bar: 0.0,

      flux_lmh: filtrateFluxSI,
      backwash_flux_lmh: backwashFluxSI,

      filtration_cycle_min: isUF
        ? num(uf.filtration_duration_min, 30)
        : num(mf.mf_filtration_duration_min, 30),

      backwash_duration_sec: isUF
        ? num(uf.uf_backwash_duration_s, 60)
        : num(mf.mf_backwash_duration_s, 60),

      ...getMemParams(c),
    };
  }

  // 4) RO/NF standard
  return {
    stage_id: n.id,
    module_type: kind,
    elements: clampInt(c.elements, 1, 24),

    pressure_bar: Number(pressureVal),

    recovery_target_pct:
      c?.mode === 'recovery' ? num(c.recovery_target_pct, 50) : undefined,

    pump_eff: globals?.pumpEff ?? undefined,

    ...getMemParams(c),
  };
}

// ==============================
// API output normalization + display conversion
// ==============================

function normalizeTimeHistory(
  ts?: TimeSeriesPoint[] | null,
): TimeSeriesPoint[] | null {
  if (!ts || !Array.isArray(ts)) return ts ?? null;
  return ts.map((p) => ({
    ...p,
    // ensure optional fields exist as-is
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

  if (cp.stage_metrics) {
    cp.stage_metrics = (cp.stage_metrics as any[]).map(normalizeStageMetric);
  }

  if (cp.time_history) {
    cp.time_history = normalizeTimeHistory(cp.time_history);
  }

  return cp;
}

export function convertScenarioOutToDisplay(
  out: ScenarioOutput,
  mode: UnitMode,
): ScenarioOutput {
  const base = normalizeScenarioOutput(out);
  if (mode === 'SI') return base;

  const cp = clone(base);

  // KPI conversions
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

  // streams conversions
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

  // stage metrics conversions
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

  // scenario time_history conversions
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

// legacy exported name used by current screens
export const convertROutToDisplay = convertScenarioOutToDisplay;

// ==============================
// Library helpers
// ==============================

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
