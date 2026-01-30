// ui\src\features\flow-builder\hooks\useFlowLogic.ts
// ui/src/features/simulation/hooks/useFlowLogic.ts

import { useState, useRef, useMemo, useCallback, useEffect } from 'react';
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
import { SimulationRequest, FeedInput } from '@/api/types';

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
  convFlow,
  convTemp,
  HRROConfig,
  ROConfig,
  NFConfig,
  MFConfig,
  convPress,
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
  toStagePayload, // ✅ 새로 만든 강력한 매핑 함수 사용
} from '../model/logic';
import { defaultConfig, ensureUnitCfg } from '../FlowBuilder.utils';

const SESSION_KEY = 'AQUANOVA_SESSION_V1';

export function useFlowLogic() {
  const rfRef = useRef<ReactFlowInstance | null>(null);

  // [Session Load]
  const sessionData = useMemo(() => {
    try {
      const saved = sessionStorage.getItem(SESSION_KEY);
      if (saved) {
        return JSON.parse(saved);
      }
    } catch (e) {
      console.error('Failed to load session', e);
    }
    return null;
  }, []);

  // --- States ---
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

  const [feed, setFeed] = useState(
    sessionData?.feed || {
      flow_m3h: 20,
      tds_mgL: 2000,
      temperature_C: 25,
      ph: 7.0,
    },
  );

  const [feedChemistry, setFeedChemistry] = useState<ChemistryInput>(
    sessionData?.feedChemistry || DEFAULT_CHEMISTRY,
  );

  // Global Options
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

  // Nodes & Edges
  const INITIAL_NODES: Node<FlowData>[] = [
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
  ];

  const [nodes, setNodes, onNodesChange] = useNodesState<FlowData>(
    sessionData?.nodes ? ensureUnitCfg(sessionData.nodes) : INITIAL_NODES,
  );
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge[]>(
    sessionData?.edges || [],
  );

  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  // Results
  const [data, setData] = useState<any | null>(sessionData?.data || null);
  const [chemSummary, setChemSummary] = useState<any | null>(
    sessionData?.chemSummary || null,
  );

  // UI States
  const [editorOpen, setEditorOpen] = useState(false);
  const [optionsOpen, setOptionsOpen] = useState(false);
  const [toast, setToast] = useState<string | null>(null);

  // History (Undo/Redo)
  const [history, setHistory] = useState<{
    past: Snapshot[];
    future: Snapshot[];
  }>({ past: [], future: [] });

  // [Auto-Save]
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

  // --- Helpers ---
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

  // --- Actions ---
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
    if (d?.type === 'endpoint') {
      return sel as Node<FlowData> & { data: EndpointData };
    }
    return null;
  }, [sel]);

  const onDragStartPalette = (k: UnitKind, ev: React.DragEvent) => {
    ev.dataTransfer.setData('application/x-unitkind', k);
    ev.dataTransfer.effectAllowed = 'move';
  };

  const onDragOver = useCallback((ev: React.DragEvent) => {
    ev.preventDefault();
    ev.dataTransfer.dropEffect = 'move';
  }, []);

  const onDrop = useCallback(
    (ev: React.DragEvent) => {
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
    [setNodes, pushHistory],
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
    if (d?.type === 'endpoint' || d?.type === 'unit') {
      setEditorOpen(true);
    }
  }, []);

  const onNodeDragStop = useCallback(() => pushHistory(), [pushHistory]);
  const onEdgesDelete = useCallback(() => pushHistory(), [pushHistory]);

  // Keyboard Shortcuts
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const mod = e.ctrlKey || e.metaKey;
      if (mod && e.key.toLowerCase() === 'z') {
        e.preventDefault();
        e.shiftKey ? redo() : undo();
        return;
      }
      if (mod && e.key === 'Enter') {
        e.preventDefault();
        onRun();
        return;
      }
      if (
        (e.key === 'Delete' || e.key === 'Backspace') &&
        selUnit &&
        selUnit.id !== 'feed' &&
        selUnit.id !== 'product'
      ) {
        e.preventDefault();
        removeNode(selUnit.id, setNodes as SetNodesFn, setEdges as SetEdgesFn);
        setSelectedNodeId(null);
        setEditorOpen(false);
        pushHistory();
        return;
      }
      if (selUnit) {
        const step = e.shiftKey ? 6 : 1;
        if (
          ['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].includes(e.key)
        ) {
          e.preventDefault();
          const dx =
            e.key === 'ArrowLeft' ? -step : e.key === 'ArrowRight' ? step : 0;
          const dy =
            e.key === 'ArrowUp' ? -step : e.key === 'ArrowDown' ? step : 0;
          nudge(selUnit.id, dx, dy, setNodes as SetNodesFn);
          return;
        }
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [undo, redo, selUnit, setNodes, setEdges]);

  // Derived
  const chainCheck = useMemo<ChainOk | ChainErr>(
    () => buildLinearChain(nodes, edges),
    [nodes, edges],
  );
  const unitChain: UnitNodeRF[] = chainCheck.ok
    ? (chainCheck.chain as UnitNodeRF[])
    : [];

  const stageTypeHint = useMemo(() => {
    if (selUnit) {
      const k = (selUnit.data as UnitData).kind as UnitKind;
      if (k === 'PUMP') return undefined;
      return k === 'HRRO' ? 'RO' : k;
    }
    return undefined;
  }, [selUnit]);

  // Toggle Units
  const toggleUnits = (next: UnitMode) => {
    if (next === unitMode) return;

    // Feed 변환
    const feed2 = { ...feed };
    feed2.flow_m3h =
      unitMode === 'SI'
        ? convFlow(feed2.flow_m3h, 'SI', next)
        : convFlow(feed2.flow_m3h, 'US', next);
    feed2.temperature_C =
      unitMode === 'SI'
        ? convTemp(feed2.temperature_C, 'SI', next)
        : convTemp(feed2.temperature_C, 'US', next);
    setFeed(feed2);

    // 노드 설정값 변환
    setNodes((arr) =>
      arr.map((n) => {
        const d = n.data as any;
        if (!d || d.type !== 'unit') return n;

        // HRRO
        if (d.kind === 'HRRO') {
          const c = d.cfg as HRROConfig;
          const p = convPress(c.p_set_bar, unitMode, next);
          return {
            ...n,
            data: { ...d, cfg: { ...c, p_set_bar: p } },
          } as Node<FlowData>;
        }

        // RO/NF/MF/UF
        if (['RO', 'NF', 'MF', 'UF'].includes(d.kind)) {
          const c = d.cfg as ROConfig | NFConfig | MFConfig;
          if (c.mode === 'pressure' && typeof c.pressure_bar === 'number') {
            const p = convPress(c.pressure_bar, unitMode, next);
            return {
              ...n,
              data: { ...d, cfg: { ...c, pressure_bar: p } },
            } as Node<FlowData>;
          }
        }
        return n;
      }),
    );
    setUnitMode(next);
  };

  /**
   * ✅ [REFACTORED & FIXED] Simulation RUN
   * 이제 데이터를 수동으로 조립하지 않고, logic.ts의 toStagePayload를 호출하여
   * 107% 방지 패치가 적용된 데이터를 안전하게 보냅니다.
   */
  const onRun = useCallback(async () => {
    console.log('🚀 [UI DEBUG] Simulation RUN Triggered');
    setLoading(true);
    setErr(null);
    setData(null);
    setChemSummary(null);

    try {
      // 1. 유효성 검사 (체인 확인)
      let check = buildLinearChain(nodes, edges) as ChainOk | ChainErr;
      if (!check.ok) {
        // 끊어진 부분이 있다면 자동으로 연결 시도 (UX 편의)
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

      const unitNodes: UnitNodeRF[] = (check as ChainOk).chain as UnitNodeRF[];
      if (unitNodes.length === 0) {
        throw new Error('시뮬레이션할 스테이지가 없습니다.');
      }

      // 2. Feed 데이터 준비 (SI 단위로 변환)
      const feedSI: FeedInput = {
        flow_m3h:
          unitMode === 'SI'
            ? feed.flow_m3h
            : convFlow(feed.flow_m3h, 'US', 'SI'),
        tds_mgL: feed.tds_mgL,
        temperature_C:
          unitMode === 'SI'
            ? feed.temperature_C
            : convTemp(feed.temperature_C, 'US', 'SI'),
        ph: feed.ph,
      };

      // 3. Stages 데이터 준비 (logic.ts에 위임)
      // ✅ 여기서 toStagePayload를 사용하므로 stop_recovery_pct가 확실히 포함됨
      const stagesPayload = unitNodes.map((n) => toStagePayload(n, unitMode));

      // 4. 통합 Payload 생성
      const payload: SimulationRequest = {
        simulation_id: cryptoRandomId(),
        project_id: 'default-project',
        scenario_name: scenarioName,
        feed: feedSI,
        stages: stagesPayload,
      };

      // 5. API 호출 (단일 엔드포인트)
      const output = await runSimulation(payload);

      // 6. 결과 처리
      // 백엔드 결과를 UI 포맷에 맞게 변환 (Unit Mode 적용)
      const outDisp = convertROutToDisplay(output, unitMode);
      setData(outDisp);
      setChemSummary(output.chemistry ?? null);

      // 스테이지 노드에 결과 칩(Chips) 업데이트
      applyStageChips(
        unitNodes.map((n) => n.id),
        outDisp?.stage_metrics ?? null,
        outDisp?.kpi,
        outDisp?.unitMode ?? unitMode,
        setNodes as SetNodesFn,
      );

      pushToast('시뮬레이션 완료');
    } catch (e: any) {
      console.error('❌ Simulation Error:', e);
      const msg =
        e?.response?.data?.detail ?? e?.message ?? '알 수 없는 오류 발생';
      setErr(typeof msg === 'object' ? JSON.stringify(msg, null, 2) : msg);
    } finally {
      setLoading(false);
    }
  }, [
    nodes,
    edges,
    feed,
    unitMode,
    scenarioName,
    pushToast,
    setNodes,
    setEdges,
  ]);

  // Save / Load (LocalStorage)
  const saveLocal = () => {
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
  };

  const loadLocal = () => {
    const raw = localStorage.getItem(LS_KEY);
    if (!raw) return pushToast('Nothing saved');
    try {
      const p = JSON.parse(raw) as PersistModel;
      setNodes(ensureUnitCfg(p.nodes));
      setEdges(p.edges);
      setFeed(p.feed);
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
  };

  const saveToLibrary = () => {
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
  };

  const loadFromLibrary = (idx: number) => {
    const e = libraryItems[idx];
    if (!e) return;
    setNodes(ensureUnitCfg(e.nodes));
    setEdges(e.edges);
    setFeed(e.feed);
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
  };

  const resetAll = useCallback(() => {
    if (window.confirm('정말 모든 작업을 초기화하시겠습니까?')) {
      sessionStorage.removeItem(SESSION_KEY);
      setNodes(INITIAL_NODES);
      setEdges([]);
      setSelectedNodeId(null);
      setData(null);
      setErr(null);
      setHistory({ past: [], future: [] });
      setFeedChemistry(DEFAULT_CHEMISTRY);
      setChemSummary(null);
      setEditorOpen(false);
      setTimeout(() => rfRef.current?.fitView?.({ padding: 0.2 }), 0);
    }
  }, [setNodes, setEdges, INITIAL_NODES]);

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
