// ui/src/features/simulation/model/logic.ts
// ui/src/features/simulation/model/logic.ts

import { MarkerType, type Edge, type Node } from 'reactflow';

// ✅ [FIX] 백엔드 스키마와 일치하는 타입을 Import
import type {
  StageConfig,
  ROStageMetric,
  ROScenarioOutput,
  HRRORunOutput,
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

  // degree 체크
  for (const n of nodes) {
    const outDeg = (outMap.get(n.id) || []).length;
    const inDeg = (inMap.get(n.id) || []).length;
    if (n.id === feed.id && inDeg > 0) {
      return {
        ok: false,
        message: 'Feed에는 들어오는 간선이 없어야 합니다.',
      };
    }
    if (n.id === product.id && outDeg > 0) {
      return {
        ok: false,
        message: 'Product에는 나가는 간선이 없어야 합니다.',
      };
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
    if (nexts.length > 1) {
      return { ok: false, message: '분기 발견: 단일 경로만 허용됩니다.' };
    }
    if (nexts.length === 0) {
      if (cur !== product.id) {
        return { ok: false, message: 'Feed→Product 연결이 끊어졌습니다.' };
      }
      break;
    }
    const nx = nexts[0];
    if (visited.has(nx)) {
      return { ok: false, message: '사이클이 발견되었습니다.' };
    }
    const nxNode = byId.get(nx);
    if (!nxNode) {
      return { ok: false, message: '존재하지 않는 노드로 연결되었습니다.' };
    }
    if ((nxNode.data as any)?.type === 'unit') {
      chain.push(nxNode as UnitNode);
    }
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

    const a = units[idx];
    const b = units[swapIdx];
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
      if (d.kind === 'HRRO') return n;
      const c = d.cfg as any;
      if (mode === 'pressure') {
        return {
          ...n,
          data: {
            ...d,
            cfg: { ...c, mode: 'pressure', pressure_bar: value },
          },
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
// Chips mapping
// ==============================

export function applyStageChips(
  nodeIds: string[],
  metrics: ROStageMetric[] | undefined | null,
  kpi: any,
  unitMode: UnitMode,
  setNodesFn: SetNodesFn,
): void {
  setNodesFn((arr) =>
    arr.map((n) => {
      const d = n.data as any;
      if (!d || d.type !== 'unit') return n;
      if (d.kind === 'HRRO') return n;

      const kind = d.kind as UnitKind;
      const idx = nodeIds.indexOf(n.id);
      if (idx < 0) return n;

      let jw_disp: number | undefined;
      let dp_disp: number | undefined;

      if (metrics && metrics[idx]) {
        const m = metrics[idx] as ROStageMetric;

        const jw_si = m.jw_avg_lmh ?? 0;
        const pin_si = m.p_in_bar ?? 0;
        const pout_si = m.p_out_bar ?? 0;

        jw_disp = unitMode === 'SI' ? jw_si : convFlux(jw_si, 'SI', 'US');

        const dp_bar = pin_si - pout_si;
        dp_disp = unitMode === 'SI' ? dp_bar : convPress(dp_bar, 'SI', 'US');
      } else if (kpi) {
        jw_disp =
          unitMode === 'SI' ? kpi.flux_lmh : convFlux(kpi.flux_lmh, 'SI', 'US');
      }

      const maxLMH = MAX_FLUX_BY_KIND[kind];
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

      return {
        ...n,
        data: { ...d, chips },
      } as Node<FlowData>;
    }),
  );
}

export function applyHRROChips(
  id: string,
  out: HRRORunOutput,
  unitMode: UnitMode,
  setNodesFn: SetNodesFn,
): void {
  const k = out.kpi || ({} as any);

  const jw =
    unitMode === 'SI'
      ? (k.flux_lmh ?? 0)
      : convFlux(k.flux_lmh ?? 0, 'SI', 'US');

  const ndp =
    unitMode === 'SI'
      ? (k.ndp_bar ?? 0)
      : convPress(k.ndp_bar ?? 0, 'SI', 'US');

  const maxLMH = MAX_FLUX_BY_KIND['HRRO'];
  const thresh = unitMode === 'SI' ? maxLMH : convFlux(maxLMH, 'SI', 'US');
  const warn = jw > thresh + 1e-6;

  const chips: any[] = [
    {
      label: 'Avg ' + unitLabel('flux', unitMode),
      value: fmt(jw),
      warn,
      tip: warn ? `권고 상한(${fmt(thresh)}) 초과` : undefined,
    },
    {
      label: 'Avg NDP ' + unitLabel('press', unitMode),
      value: fmt(ndp),
    },
  ];

  setNodesFn((arr) =>
    arr.map((n) => {
      if (n.id !== id) return n;
      const d = n.data as any;
      if (!d || d.type !== 'unit') return n;
      return {
        ...n,
        data: { ...d, chips },
      } as Node<FlowData>;
    }),
  );
}

// =========================================================================
// ✅ Stage payload builders (THE CRITICAL FIX FOR 110% BUG)
// =========================================================================

// Helper to extract membrane params
function getMemParams(c: any) {
  if (c.membrane_mode === 'custom') {
    return {
      membrane_model: null,
      membrane_area_m2: num(c.custom_area_m2, 0) || null,
      membrane_A_lmh_bar: num(c.custom_A_lmh_bar, 0) || null,
      membrane_B_lmh: num(c.custom_B_lmh, 0) || null,
      membrane_salt_rejection_pct: num(c.custom_salt_rejection_pct, 0) || null,
    };
  }
  return {
    membrane_model: c.membrane_model || null,
    membrane_area_m2: null,
    membrane_A_lmh_bar: null,
    membrane_B_lmh: null,
    membrane_salt_rejection_pct: null,
  };
}

/**
 * ReactFlow 노드를 백엔드 API 스키마(StageConfig)로 완벽하게 변환하는 함수.
 * 110% 폭주 버그를 막기 위해 stop_recovery_pct 값을 강제로 주입합니다.
 */
export function toStagePayload(
  n: UnitNode,
  currentUnitMode: UnitMode,
): StageConfig {
  const d = n.data;
  const kind = d.kind;
  const c = d.cfg as any;

  // 1. 공통 압력 처리 (US -> SI 변환)
  let pressureVal = 15.0; // default
  if (kind === 'HRRO') pressureVal = c.p_set_bar;
  else if (c.mode === 'pressure') pressureVal = c.pressure_bar;

  if (currentUnitMode !== 'SI') {
    pressureVal = convPress(num(pressureVal, 15), 'US', 'SI');
  }

  // 2. HRRO Logic (✅ 110% Bug Fix Applied Here)
  if (kind === 'HRRO') {
    // UI에서 입력된 값을 확실하게 가져옴.
    // 사용자가 'Recovery Target'을 입력하면 그것을 'Stop Trigger'로 간주.
    const stopRecInput =
      Number(c.stop_recovery_pct) || Number(c.recovery_target_pct) || 90.0;

    return {
      stage_id: n.id,
      module_type: 'HRRO',
      elements: clampInt(c.elements, 1, 12),
      pressure_bar: Number(pressureVal),

      // HRRO Specific Parameters
      loop_volume_m3: num(c.loop_volume_m3, 2),
      recirc_flow_m3h: num(c.recirc_flow_m3h, 12),
      bleed_m3h: num(c.bleed_m3h, 0),
      timestep_s: clampInt(c.timestep_s, 1, 60),
      max_minutes: num(c.max_minutes, 60),
      stop_permeate_tds_mgL: c.stop_permeate_tds_mgL ?? null,

      // 🔥 [CRITICAL FIX] 백엔드 계약서(StageConfig)에 명시된 필드에 값 주입
      stop_recovery_pct: stopRecInput,
      recovery_target_pct: stopRecInput, // 호환성 유지용

      mass_transfer: c.mass_transfer ?? null,
      spacer: c.spacer ?? null,
      ...getMemParams(c),
    };
  }

  // 3. UF/MF Logic
  if (kind === 'UF' || kind === 'MF') {
    const isUF = kind === 'UF';
    return {
      stage_id: n.id,
      module_type: kind,
      elements: clampInt(c.elements, 1, 12),
      pressure_bar: 0.1, // UF/MF는 압력 제어 아님

      flux_lmh: num(
        isUF ? c.filtrate_flux_lmh_25C : c.mf_filtrate_flux_lmh_25C,
        60,
      ),
      backwash_flux_lmh: num(
        isUF ? c.backwash_flux_lmh : c.mf_backwash_flux_lmh,
        120,
      ),
      filtration_cycle_min: num(
        isUF ? c.filtration_duration_min : c.mf_filtration_duration_min,
        30,
      ),
      backwash_duration_sec: num(
        isUF ? c.uf_backwash_duration_s : c.mf_backwash_duration_s,
        60,
      ),

      ...getMemParams(c),
    };
  }

  // 4. RO/NF Logic (Standard)
  return {
    stage_id: n.id,
    module_type: kind as any,
    elements: clampInt(c.elements, 1, 12),
    pressure_bar: Number(pressureVal),
    recovery_target_pct:
      c.mode === 'recovery' ? num(c.recovery_target_pct, 50) : undefined,
    ...getMemParams(c),
  };
}

export function toHRROStage(n: UnitNode): any {
  return toStagePayload(n, 'SI');
}

export function chooseGlobalOptions(
  unitNodes: UnitNode[],
  feedTDS: number,
): { membrane: string; pump_eff: number; erd_eff: number } {
  const kinds = new Set(unitNodes.map((n) => n.data.kind as UnitKind));
  let membrane = 'BWRO-8040-generic';

  if (kinds.has('RO') || kinds.has('HRRO')) {
    membrane = feedTDS >= 10000 ? 'SWRO-8040-generic' : 'BWRO-8040-generic';
  } else if (kinds.has('NF')) {
    membrane = 'NF-8040-generic';
  } else if (kinds.has('UF')) {
    membrane = 'UF-8040-generic';
  } else if (kinds.has('MF')) {
    membrane = 'MF-8040-generic';
  }
  return { membrane, pump_eff: 0.8, erd_eff: 0.0 };
}

// ==============================
// API output 변환
// ==============================

export function convertROutToDisplay(
  out: ROScenarioOutput,
  mode: UnitMode,
): ROScenarioOutput {
  if (mode === 'SI') return out;
  const cp = clone(out);

  if (cp.kpi) {
    if (typeof cp.kpi.flux_lmh === 'number') {
      cp.kpi.flux_lmh = convFlux(cp.kpi.flux_lmh, 'SI', 'US');
    }
    if (typeof cp.kpi.ndp_bar === 'number') {
      cp.kpi.ndp_bar = convPress(cp.kpi.ndp_bar, 'SI', 'US');
    }
  }

  if (cp.stage_metrics) {
    cp.stage_metrics = cp.stage_metrics.map((m: ROStageMetric) => {
      return {
        ...m,
        p_in_bar:
          typeof m.p_in_bar === 'number'
            ? convPress(m.p_in_bar, 'SI', 'US')
            : m.p_in_bar,
        p_out_bar:
          typeof m.p_out_bar === 'number'
            ? convPress(m.p_out_bar, 'SI', 'US')
            : m.p_out_bar,
        jw_avg_lmh:
          typeof m.jw_avg_lmh === 'number'
            ? convFlux(m.jw_avg_lmh, 'SI', 'US')
            : m.jw_avg_lmh,
        ndp_bar:
          typeof m.ndp_bar === 'number'
            ? convPress(m.ndp_bar, 'SI', 'US')
            : m.ndp_bar,
        delta_pi_bar:
          typeof m.delta_pi_bar === 'number'
            ? convPress(m.delta_pi_bar, 'SI', 'US')
            : m.delta_pi_bar,
      };
    });
  }

  return cp;
}

export function convertHRROOutToDisplay(
  out: HRRORunOutput,
  mode: UnitMode,
): HRRORunOutput {
  if (mode === 'SI') return out;
  const cp = clone(out);

  if (cp.kpi) {
    if (typeof cp.kpi.flux_lmh === 'number') {
      cp.kpi.flux_lmh = convFlux(cp.kpi.flux_lmh, 'SI', 'US');
    }
    if (typeof cp.kpi.ndp_bar === 'number') {
      cp.kpi.ndp_bar = convPress(cp.kpi.ndp_bar, 'SI', 'US');
    }
  }
  return cp;
}

// ==============================
// Library / project helpers
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
  return (raw && raw.trim()) || '11111111-1111-1111-1111-111111111111';
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
