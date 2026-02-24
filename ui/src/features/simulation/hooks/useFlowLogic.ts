// ui/src/features/simulation/hooks/useFlowLogic.ts
import { useState, useRef, useMemo, useCallback, useEffect } from 'react';
import type { DragEvent } from 'react';
import {
  useNodesState,
  useEdgesState,
  addEdge,
  Connection,
  Edge,
  Node,
  ReactFlowInstance,
} from 'reactflow';

import { runSimulation } from '@/api/simulation';
import type {
  SimulationRequest,
  FeedInput as ApiFeedInput,
  WaterChemistryInput,
  IonCompositionInput,
} from '@/api/types';

import {
  UnitMode,
  PersistModel,
  ChemistryInput,
  DEFAULT_CHEMISTRY,
  FlowData,
  UnitKind,
  UnitData,
  EndpointData,
  Snapshot,
  SetNodesFn,
  SetEdgesFn,
  ChainOk,
  ChainErr,
  UnitNodeRF,
  FeedState,
  convFlow,
  convTemp,
  HRROConfig,
  ROConfig,
  NFConfig,
  MFConfig,
  UFConfig,
  convPress,
  convFlux,
} from '../model/types';

import {
  loadLibrary,
  cryptoRandomId,
  isUnitNode,
  clone,
  buildLinearChain,
  makeLinearEdges,
  convertROutToDisplay,
  applyStageChips,
  nudge,
  removeNode,
  LS_KEY,
  LS_SCNS,
  toStagePayload,
  resolveProjectId,
} from '../model/logic';

import { defaultConfig, ensureUnitCfg } from '../FlowBuilder.utils';
import { normalizeWaterType } from '../model/feedWater';

const SESSION_KEY = 'AQUANOVA_SESSION_V1';

const DEFAULT_FEED: FeedState = {
  flow_m3h: 20,
  tds_mgL: 2000,
  temperature_C: 25,
  ph: 7.0,
  pressure_bar: 0.0,

  water_type: 'RO/NF Well Water',
  water_subtype: null,

  fouling: {
    turbidity_ntu: null,
    tss_mgL: null,
    sdi15: null,
    toc_mgL: null,
    cod_mgL: null,
    bod_mgL: null,
  },

  temp_min_C: null,
  temp_max_C: null,
  feed_note: null,

  charge_balance_mode: null,
};

function migrateFeedState(raw: any): FeedState {
  if (!raw) return clone(DEFAULT_FEED);

  const safeWaterType =
    normalizeWaterType(raw.water_type) || 'RO/NF Well Water';

  return {
    ...raw,
    water_type: safeWaterType,
    fouling: {
      turbidity_ntu: raw.fouling?.turbidity_ntu ?? raw.turbidity_ntu ?? null,
      tss_mgL: raw.fouling?.tss_mgL ?? raw.tss_mgL ?? null,
      sdi15: raw.fouling?.sdi15 ?? raw.sdi15 ?? null,
      toc_mgL: raw.fouling?.toc_mgL ?? raw.toc_mgL ?? null,
      cod_mgL: raw.fouling?.cod_mgL ?? null,
      bod_mgL: raw.fouling?.bod_mgL ?? null,
    },
  };
}

function hasAnyNumber(obj: Record<string, any> | null | undefined): boolean {
  if (!obj) return false;
  return Object.values(obj).some(
    (v) => typeof v === 'number' && Number.isFinite(v),
  );
}

function mapChemistryToBackend(ui: ChemistryInput | null | undefined): {
  chemistry?: WaterChemistryInput | null;
  ions?: IonCompositionInput | null;
} {
  if (!ui) return {};

  const chemistry: WaterChemistryInput = {
    alkalinity_mgL_as_CaCO3: ui.alkalinity_mgL_as_CaCO3 ?? null,
    calcium_hardness_mgL_as_CaCO3: ui.calcium_hardness_mgL_as_CaCO3 ?? null,
    sulfate_mgL: ui.sulfate_mgL ?? ui.so4_mgL ?? null,
    barium_mgL: ui.barium_mgL ?? ui.ba_mgL ?? null,
    strontium_mgL: ui.strontium_mgL ?? ui.sr_mgL ?? null,
    silica_mgL_SiO2: ui.silica_mgL_SiO2 ?? ui.sio2_mgL ?? null,
  };

  const ions: IonCompositionInput = {
    NH4: ui.nh4_mgL ?? null,
    K: ui.k_mgL ?? null,
    Na: ui.na_mgL ?? null,
    Mg: ui.mg_mgL ?? null,
    Ca: ui.ca_mgL ?? null,
    Sr: ui.sr_mgL ?? null,
    Ba: ui.ba_mgL ?? null,
    HCO3: ui.hco3_mgL ?? null,
    NO3: ui.no3_mgL ?? null,
    Cl: ui.cl_mgL ?? null,
    F: ui.f_mgL ?? null,
    SO4: ui.so4_mgL ?? ui.sulfate_mgL ?? null,
    Br: ui.br_mgL ?? null,
    PO4: ui.po4_mgL ?? null,
    CO3: ui.co3_mgL ?? null,
    CO2: ui.co2_mgL ?? null,
    SiO2: ui.sio2_mgL ?? ui.silica_mgL_SiO2 ?? null,
    B: ui.b_mgL ?? null,
    Fe: ui.fe_mgL ?? null,
    Mn: ui.mn_mgL ?? null,
    Al: ui.al_mgL ?? null,
  };

  const chemistryOut = hasAnyNumber(chemistry as any) ? chemistry : null;
  const ionsOut = hasAnyNumber(ions as any) ? ions : null;

  return { chemistry: chemistryOut, ions: ionsOut };
}

function isEditableTarget(t: EventTarget | null): boolean {
  const el = t as HTMLElement | null;
  if (!el) return false;
  const tag = el.tagName;
  if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return true;
  if ((el as any).isContentEditable) return true;
  return false;
}

export function useFlowLogic() {
  const rfRef = useRef<ReactFlowInstance | null>(null);

  const INITIAL_NODES: Node<FlowData>[] = useMemo(
    () => [
      {
        id: 'feed',
        type: 'endpoint',
        position: { x: 40, y: 160 },
        data: { type: 'endpoint', role: 'feed', label: 'Feed' },
      },
      {
        id: 'product',
        type: 'endpoint',
        position: { x: 900, y: 160 },
        data: { type: 'endpoint', role: 'product', label: 'Product' },
      },
    ],
    [],
  );

  const sessionData = useMemo(() => {
    try {
      const saved = sessionStorage.getItem(SESSION_KEY);
      if (saved) return JSON.parse(saved);
    } catch (e) {
      console.error('Failed to load session', e);
    }
    return null;
  }, []);

  const [unitMode, setUnitMode] = useState<UnitMode>(
    sessionData?.unitMode || 'SI',
  );
  const [scenarioName, setScenarioName] = useState<string>(
    sessionData?.scenarioName || 'My Scenario',
  );

  const [libraryOpen, setLibraryOpen] = useState<boolean>(false);
  const [libraryItems, setLibraryItems] = useState<PersistModel[]>(() =>
    loadLibrary(),
  );

  const [feed, setFeed] = useState<FeedState>(() =>
    migrateFeedState(sessionData?.feed),
  );
  const [feedChemistry, setFeedChemistry] = useState<ChemistryInput>(
    sessionData?.feedChemistry || DEFAULT_CHEMISTRY,
  );

  const [optAuto, setOptAuto] = useState(sessionData?.opt?.auto ?? true);
  const [optMembrane, setOptMembrane] = useState<string>(
    sessionData?.opt?.membrane || 'AUTO',
  );
  const [optPumpEff, setOptPumpEff] = useState(
    sessionData?.opt?.pump_eff ?? 0.8,
  );
  const [optErdEff, setOptErdEff] = useState(sessionData?.opt?.erd_eff ?? 0.0);
  const [optSegments, setOptSegments] = useState(
    sessionData?.opt?.segments ?? 10,
  );

  const [nodes, setNodes, onNodesChange] = useNodesState<FlowData>(
    sessionData?.nodes ? ensureUnitCfg(sessionData.nodes) : INITIAL_NODES,
  );
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge[]>(
    sessionData?.edges || [],
  );

  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const [data, setData] = useState<any | null>(sessionData?.data || null);
  const [chemSummary, setChemSummary] = useState<any | null>(
    sessionData?.chemSummary || null,
  );

  const [editorOpen, setEditorOpen] = useState(false);
  const [optionsOpen, setOptionsOpen] = useState(false);
  const [toast, setToast] = useState<string | null>(null);

  const [history, setHistory] = useState<{
    past: Snapshot[];
    future: Snapshot[];
  }>({
    past: [],
    future: [],
  });

  useEffect(() => {
    const timeoutId = setTimeout(() => {
      const payload = {
        unitMode,
        scenarioName,
        feed,
        feedChemistry,
        nodes,
        edges,
        data,
        chemSummary,
        opt: {
          auto: optAuto,
          membrane: optMembrane,
          segments: optSegments,
          pump_eff: optPumpEff,
          erd_eff: optErdEff,
        },
        timestamp: Date.now(),
      };
      sessionStorage.setItem(SESSION_KEY, JSON.stringify(payload));
    }, 500);
    return () => clearTimeout(timeoutId);
  }, [
    unitMode,
    scenarioName,
    feed,
    feedChemistry,
    nodes,
    edges,
    data,
    chemSummary,
    optAuto,
    optMembrane,
    optSegments,
    optPumpEff,
    optErdEff,
  ]);

  const pushToast = useCallback((msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 1500);
  }, []);

  const pushHistory = useCallback(() => {
    setHistory((h) => ({
      past: [...h.past, { nodes: clone(nodes), edges: clone(edges) }],
      future: [],
    }));
  }, [nodes, edges]);

  const undo = useCallback(() => {
    setHistory((h) => {
      if (!h.past.length) return h;
      const past = [...h.past];
      const prev = past[past.length - 1];
      setNodes(prev.nodes);
      setEdges(prev.edges);
      return {
        past: past.slice(0, -1),
        future: [{ nodes: clone(nodes), edges: clone(edges) }, ...h.future],
      };
    });
  }, [nodes, edges, setNodes, setEdges]);

  const redo = useCallback(() => {
    setHistory((h) => {
      if (!h.future.length) return h;
      const [next, ...rest] = h.future;
      setNodes(next.nodes);
      setEdges(next.edges);
      return {
        past: [...h.past, { nodes: clone(nodes), edges: clone(edges) }],
        future: rest,
      };
    });
  }, [nodes, edges, setNodes, setEdges]);

  const sel = useMemo(
    () => nodes.find((n) => n.id === selectedNodeId) || null,
    [nodes, selectedNodeId],
  );
  const selUnit = useMemo(() => (isUnitNode(sel) ? sel : null), [sel]);

  const selEndpoint = useMemo(() => {
    if (!sel) return null;
    const d = sel.data as any;
    if (d?.type === 'endpoint')
      return sel as Node<FlowData> & { data: EndpointData };
    return null;
  }, [sel]);

  const stageTypeHint = useMemo(() => {
    if (selUnit) {
      const k = (selUnit.data as UnitData).kind as UnitKind;
      if (k === 'PUMP') return undefined;
      return k;
    }
    return undefined;
  }, [selUnit]);

  const onDragStartPalette = useCallback((k: UnitKind, ev: DragEvent) => {
    ev.dataTransfer.setData('application/x-unitkind', k);
    ev.dataTransfer.effectAllowed = 'move';
  }, []);

  const onDragOver = useCallback((ev: DragEvent) => {
    ev.preventDefault();
    ev.dataTransfer.dropEffect = 'move';
  }, []);

  const onDrop = useCallback(
    (ev: DragEvent) => {
      ev.preventDefault();
      const kind = ev.dataTransfer.getData(
        'application/x-unitkind',
      ) as UnitKind;
      if (!kind) return;

      const flowPos = rfRef.current?.screenToFlowPosition?.({
        x: ev.clientX,
        y: ev.clientY,
      }) ?? { x: 200, y: 120 };
      const id = cryptoRandomId();
      pushHistory();

      setNodes((prev) =>
        prev.concat({
          id,
          type: 'unit',
          position: flowPos,
          data: {
            type: 'unit',
            kind,
            cfg: defaultConfig(kind),
            label: `${kind} Stage`,
          } as UnitData,
        } as Node<FlowData>),
      );

      setSelectedNodeId(id);
      setEditorOpen(true);
    },
    [pushHistory, setNodes],
  );

  const onConnect = useCallback(
    (params: Edge | Connection) => {
      pushHistory();
      setEdges((eds) =>
        addEdge(
          {
            ...params,
            markerEnd: { type: 'arrowclosed' },
            type: 'smoothstep',
            animated: true,
          } as any,
          eds,
        ),
      );
    },
    [setEdges, pushHistory],
  );

  const onNodeClick = useCallback((_e: any, n: Node<FlowData>) => {
    setSelectedNodeId(n.id);
    const d = n.data as any;
    if (d?.type === 'endpoint' || d?.type === 'unit') setEditorOpen(true);
  }, []);

  const onNodeDragStop = useCallback(() => pushHistory(), [pushHistory]);
  const onEdgesDelete = useCallback(() => pushHistory(), [pushHistory]);

  const toggleUnits = useCallback(
    (next: UnitMode) => {
      if (next === unitMode) return;

      const feed2: FeedState = { ...feed };
      feed2.flow_m3h = convFlow(feed2.flow_m3h, unitMode, next);
      feed2.temperature_C = convTemp(feed2.temperature_C, unitMode, next);

      if (typeof feed2.pressure_bar === 'number') {
        feed2.pressure_bar = convPress(feed2.pressure_bar, unitMode, next);
      }
      setFeed(feed2);

      setNodes((arr) =>
        arr.map((n) => {
          const d = n.data as any;
          if (!d || d.type !== 'unit') return n;

          if (d.kind === 'HRRO') {
            const c = d.cfg as HRROConfig;
            const p = convPress(c.p_set_bar, unitMode, next);
            return {
              ...n,
              data: { ...d, cfg: { ...c, p_set_bar: p } },
            } as Node<FlowData>;
          }

          // 🛑 [MULTI-STAGE PATCH] 다단 배열 내의 압력과 시스템 유량 설정까지 단위 변환 적용
          if (['RO', 'NF'].includes(d.kind)) {
            const c = clone(d.cfg) as ROConfig | NFConfig;

            if (c.mode === 'pressure' && typeof c.pressure_bar === 'number') {
              c.pressure_bar = convPress(c.pressure_bar, unitMode, next);
            }
            if (c.mode === 'flow' && typeof c.flow_target_m3h === 'number') {
              c.flow_target_m3h = convFlow(c.flow_target_m3h, unitMode, next);
            }
            if (typeof c.permeate_back_pressure_bar === 'number') {
              c.permeate_back_pressure_bar = convPress(
                c.permeate_back_pressure_bar,
                unitMode,
                next,
              );
            }

            if (c.stages && c.stages.length > 0) {
              c.stages = c.stages.map((stg: any) => ({
                ...stg,
                pre_stage_dp_bar:
                  typeof stg.pre_stage_dp_bar === 'number'
                    ? convPress(stg.pre_stage_dp_bar, unitMode, next)
                    : stg.pre_stage_dp_bar,
                isbp_pressure_bar:
                  typeof stg.isbp_pressure_bar === 'number'
                    ? convPress(stg.isbp_pressure_bar, unitMode, next)
                    : stg.isbp_pressure_bar,
              }));
            } else {
              if (typeof c.pre_stage_dp_bar === 'number') {
                c.pre_stage_dp_bar = convPress(
                  c.pre_stage_dp_bar,
                  unitMode,
                  next,
                );
              }
            }

            return { ...n, data: { ...d, cfg: c } } as Node<FlowData>;
          }

          if (d.kind === 'MF') {
            const c = d.cfg as MFConfig;
            const p =
              c.mode === 'pressure' && typeof c.pressure_bar === 'number'
                ? convPress(c.pressure_bar, unitMode, next)
                : c.pressure_bar;
            const filtrate =
              typeof c.mf_filtrate_flux_lmh_25C === 'number'
                ? convFlux(c.mf_filtrate_flux_lmh_25C, unitMode, next)
                : c.mf_filtrate_flux_lmh_25C;
            const backwash =
              typeof c.mf_backwash_flux_lmh === 'number'
                ? convFlux(c.mf_backwash_flux_lmh, unitMode, next)
                : c.mf_backwash_flux_lmh;
            return {
              ...n,
              data: {
                ...d,
                cfg: {
                  ...c,
                  pressure_bar: p,
                  mf_filtrate_flux_lmh_25C: filtrate,
                  mf_backwash_flux_lmh: backwash,
                },
              },
            } as Node<FlowData>;
          }

          if (d.kind === 'UF') {
            const c = d.cfg as UFConfig;
            const filtrate =
              typeof c.filtrate_flux_lmh_25C === 'number'
                ? convFlux(c.filtrate_flux_lmh_25C, unitMode, next)
                : c.filtrate_flux_lmh_25C;
            const backwash =
              typeof c.backwash_flux_lmh === 'number'
                ? convFlux(c.backwash_flux_lmh, unitMode, next)
                : c.backwash_flux_lmh;
            return {
              ...n,
              data: {
                ...d,
                cfg: {
                  ...c,
                  filtrate_flux_lmh_25C: filtrate,
                  backwash_flux_lmh: backwash,
                },
              },
            } as Node<FlowData>;
          }

          return n;
        }),
      );

      setUnitMode(next);
    },
    [feed, setFeed, setNodes, unitMode],
  );

  const onRun = useCallback(async () => {
    setLoading(true);
    setErr(null);
    setData(null);
    setChemSummary(null);

    try {
      let check = buildLinearChain(nodes, edges) as ChainOk | ChainErr;
      if (!check.ok) {
        const hypot = makeLinearEdges(nodes);
        const check2 = buildLinearChain(nodes, hypot);
        if (check2.ok) {
          setEdges(() => hypot);
          check = check2 as ChainOk;
        } else {
          throw new Error(
            (check2 as ChainErr).message ?? '유효한 공정 순서를 구성해주세요.',
          );
        }
      }

      const unitNodes = (check as ChainOk).chain as UnitNodeRF[];
      const stageChain = unitNodes.filter(
        (n) => ((n.data as any).kind as UnitKind) !== 'PUMP',
      );

      if (stageChain.length === 0) {
        throw new Error(
          '시뮬레이션할 스테이지가 없습니다. (PUMP만 있거나 비어있음)',
        );
      }

      const { chemistry, ions } = mapChemistryToBackend(feedChemistry);

      const feedSI: ApiFeedInput = {
        flow_m3h: convFlow(feed.flow_m3h, unitMode, 'SI'),
        tds_mgL: feed.tds_mgL,
        temperature_C: convTemp(feed.temperature_C, unitMode, 'SI'),
        ph: feed.ph,
        pressure_bar:
          typeof feed.pressure_bar === 'number'
            ? convPress(feed.pressure_bar, unitMode, 'SI')
            : 0.0,
        water_type: feed.water_type ?? null,
        temp_min_C: feed.temp_min_C ?? null,
        temp_max_C: feed.temp_max_C ?? null,
        fouling: feed.fouling,
        ions: ions ?? undefined,
      };

      const globals = {
        defaultMembraneModel: optMembrane,
        pumpEff: optPumpEff,
      };

      // 🛑 [MULTI-STAGE PATCH] 배열 평탄화(flatMap)를 통해 다단 배열 구조를 백엔드가 처리할 수 있도록 1차원 리스트로 풀어서 전송
      const stagesPayload = stageChain.flatMap((n) =>
        toStagePayload(n, unitMode, globals),
      );

      const payload: SimulationRequest = {
        simulation_id: cryptoRandomId(),
        project_id: resolveProjectId(),
        scenario_name: scenarioName,
        feed: feedSI,
        stages: stagesPayload,
        options: {
          auto: optAuto,
          membrane: optMembrane,
          segments: optSegments,
          pump_eff: optPumpEff,
          erd_eff: optErdEff,
        },
        chemistry: chemistry ?? null,
      };

      const output = await runSimulation(payload);
      const outDisp = convertROutToDisplay(output as any, unitMode);

      setData(outDisp);
      setChemSummary((output as any).chemistry ?? null);

      applyStageChips(
        stageChain.map((n) => n.id),
        (outDisp as any)?.stage_metrics ?? null,
        (outDisp as any)?.kpi ?? null,
        unitMode,
        setNodes as SetNodesFn,
      );

      pushToast('시뮬레이션 완료');
    } catch (e: any) {
      console.error('❌ Simulation Error:', e);
      const msg =
        e?.response?.data?.detail ?? e?.message ?? '알 수 없는 오류 발생';
      setErr(
        typeof msg === 'object' ? JSON.stringify(msg, null, 2) : String(msg),
      );
    } finally {
      setLoading(false);
    }
  }, [
    nodes,
    edges,
    feed,
    feedChemistry,
    unitMode,
    scenarioName,
    optAuto,
    optMembrane,
    optSegments,
    optPumpEff,
    optErdEff,
    pushToast,
    setNodes,
    setEdges,
  ]);

  const onRunRef = useRef<() => void>(() => {});
  useEffect(() => {
    onRunRef.current = onRun;
  }, [onRun]);

  const selUnitRef = useRef<typeof selUnit>(null);
  useEffect(() => {
    selUnitRef.current = selUnit;
  }, [selUnit]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.defaultPrevented) return;
      if (isEditableTarget(e.target)) return;

      const mod = e.ctrlKey || e.metaKey;

      if (mod && e.key.toLowerCase() === 'z') {
        e.preventDefault();
        e.shiftKey ? redo() : undo();
        return;
      }

      if (mod && e.key === 'Enter') {
        e.preventDefault();
        onRunRef.current?.();
        return;
      }

      const u = selUnitRef.current;

      if (
        (e.key === 'Delete' || e.key === 'Backspace') &&
        u &&
        u.id !== 'feed' &&
        u.id !== 'product'
      ) {
        e.preventDefault();
        pushHistory();
        removeNode(u.id, setNodes as SetNodesFn, setEdges as SetEdgesFn);
        setSelectedNodeId(null);
        setEditorOpen(false);
        return;
      }

      if (u) {
        const step = e.shiftKey ? 6 : 1;
        if (
          ['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].includes(e.key)
        ) {
          e.preventDefault();
          const dx =
            e.key === 'ArrowLeft' ? -step : e.key === 'ArrowRight' ? step : 0;
          const dy =
            e.key === 'ArrowUp' ? -step : e.key === 'ArrowDown' ? step : 0;
          nudge(u.id, dx, dy, setNodes as SetNodesFn);
        }
      }
    };

    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [undo, redo, pushHistory, setNodes, setEdges]);

  const saveLocal = useCallback(() => {
    const payload: PersistModel = {
      nodes,
      edges,
      feed,
      opt: {
        auto: optAuto,
        membrane: optMembrane,
        segments: optSegments,
        pump_eff: optPumpEff,
        erd_eff: optErdEff,
      },
      name: scenarioName,
      chemistry: feedChemistry,
    };
    localStorage.setItem(LS_KEY, JSON.stringify(payload));
    pushToast('Saved to browser');
  }, [
    nodes,
    edges,
    feed,
    optAuto,
    optMembrane,
    optSegments,
    optPumpEff,
    optErdEff,
    scenarioName,
    feedChemistry,
    pushToast,
  ]);

  const loadLocal = useCallback(() => {
    const raw = localStorage.getItem(LS_KEY);
    if (!raw) return pushToast('Nothing saved');
    try {
      const p = JSON.parse(raw) as PersistModel;
      setNodes(ensureUnitCfg(p.nodes));
      setEdges(p.edges);
      setFeed(migrateFeedState(p.feed));
      setOptAuto(p.opt.auto);
      setOptMembrane(p.opt.membrane as any);
      setOptSegments(p.opt.segments);
      setOptPumpEff(p.opt.pump_eff);
      setOptErdEff(p.opt.erd_eff);
      if (p.name) setScenarioName(p.name);
      setFeedChemistry(p.chemistry ?? DEFAULT_CHEMISTRY);
      pushToast('Loaded');
      setTimeout(() => rfRef.current?.fitView?.({ padding: 0.2 }), 0);
    } catch {
      pushToast('Load failed');
    }
  }, [
    pushToast,
    setNodes,
    setEdges,
    setFeed,
    setOptAuto,
    setOptMembrane,
    setOptSegments,
    setOptPumpEff,
    setOptErdEff,
    setScenarioName,
    setFeedChemistry,
  ]);

  const saveToLibrary = useCallback(() => {
    const entry: PersistModel = {
      nodes,
      edges,
      feed,
      opt: {
        auto: optAuto,
        membrane: optMembrane,
        segments: optSegments,
        pump_eff: optPumpEff,
        erd_eff: optErdEff,
      },
      name: scenarioName,
      chemistry: feedChemistry,
    };
    const lib = loadLibrary();
    const withNew = [
      entry,
      ...lib.filter((i) => i.name !== scenarioName),
    ].slice(0, 10);
    localStorage.setItem(LS_SCNS, JSON.stringify(withNew));
    setLibraryItems(withNew);
    pushToast('Saved to Library');
  }, [
    nodes,
    edges,
    feed,
    optAuto,
    optMembrane,
    optSegments,
    optPumpEff,
    optErdEff,
    scenarioName,
    feedChemistry,
    pushToast,
  ]);

  const loadFromLibrary = useCallback(
    (idx: number) => {
      const e = libraryItems[idx];
      if (!e) return;

      setNodes(ensureUnitCfg(e.nodes));
      setEdges(e.edges);
      setFeed(migrateFeedState(e.feed));
      setOptAuto(e.opt.auto);
      setOptMembrane(e.opt.membrane as any);
      setOptSegments(e.opt.segments);
      setOptPumpEff(e.opt.pump_eff);
      setOptErdEff(e.opt.erd_eff);
      setScenarioName(e.name ?? 'Loaded Scenario');
      setFeedChemistry(e.chemistry ?? DEFAULT_CHEMISTRY);
      setLibraryOpen(false);
      pushToast('Loaded from Library');
      setTimeout(() => rfRef.current?.fitView?.({ padding: 0.2 }), 0);
    },
    [
      libraryItems,
      setNodes,
      setEdges,
      setFeed,
      setOptAuto,
      setOptMembrane,
      setOptSegments,
      setOptPumpEff,
      setOptErdEff,
      setScenarioName,
      setFeedChemistry,
      setLibraryOpen,
      pushToast,
    ],
  );

  const resetAll = useCallback(() => {
    if (window.confirm('정말 모든 작업을 초기화하시겠습니까?')) {
      sessionStorage.removeItem(SESSION_KEY);
      setNodes(INITIAL_NODES);
      setEdges([]);
      setSelectedNodeId(null);
      setData(null);
      setErr(null);
      setHistory({ past: [], future: [] });
      setFeed(DEFAULT_FEED);
      setFeedChemistry(DEFAULT_CHEMISTRY);
      setChemSummary(null);
      setEditorOpen(false);
      setTimeout(() => rfRef.current?.fitView?.({ padding: 0.2 }), 0);
    }
  }, [INITIAL_NODES, setNodes, setEdges]);

  return {
    rfRef,
    unitMode,
    setUnitMode,
    scenarioName,
    setScenarioName,
    libraryOpen,
    setLibraryOpen,
    libraryItems,
    feed,
    setFeed,
    feedChemistry,
    setFeedChemistry,
    optAuto,
    setOptAuto,
    optMembrane,
    setOptMembrane,
    optSegments,
    setOptSegments,
    optPumpEff,
    setOptPumpEff,
    optErdEff,
    setOptErdEff,
    nodes,
    setNodes,
    onNodesChange,
    edges,
    setEdges,
    onEdgesChange,
    selectedNodeId,
    setSelectedNodeId,
    loading,
    err,
    data,
    chemSummary,
    editorOpen,
    setEditorOpen,
    optionsOpen,
    setOptionsOpen,
    toast,
    canUndo: history.past.length > 0,
    canRedo: history.future.length > 0,
    selEndpoint,
    selUnit,
    stageTypeHint,
    pushToast,
    undo,
    redo,
    onDragStartPalette,
    onDragOver,
    onDrop,
    onConnect,
    onNodeClick,
    onNodeDragStop,
    onEdgesDelete,
    toggleUnits,
    onRun,
    saveLocal,
    loadLocal,
    saveToLibrary,
    loadFromLibrary,
    resetAll,
  };
}
