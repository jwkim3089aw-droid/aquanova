// ui/src/features/simulation/hooks/flow/useFlowState.ts
import { useState, useRef, useMemo, useCallback, useEffect } from 'react';
import {
  useNodesState,
  useEdgesState,
  ReactFlowInstance,
  Node,
  Edge,
} from 'reactflow';
import { loadLibrary, clone } from '../../model/logic';
import { ensureUnitCfg } from '../../FlowBuilder.utils';
import { SESSION_KEY, migrateFeedState } from './utils';
import {
  UnitMode,
  PersistModel,
  ChemistryInput,
  DEFAULT_CHEMISTRY,
  FlowData,
  UnitKind,
  UnitData,
  EndpointData,
  FeedState,
  OpexState,
  convFlow,
  convTemp,
  convPress,
  convFlux,
  HRROConfig,
  ROConfig,
  NFConfig,
  MFConfig,
  UFConfig,
} from '../../model/types';

export function useFlowState() {
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

  const [optPumpEff, setOptPumpEff] = useState(
    sessionData?.opt?.pump_eff ?? 0.8,
  );
  const [optErdEff, setOptErdEff] = useState(sessionData?.opt?.erd_eff ?? 0.0);
  const [optSegments, setOptSegments] = useState(
    sessionData?.opt?.segments ?? 10,
  );

  const [opexConfig, setOpexConfig] = useState<OpexState>(
    sessionData?.opex || {
      electricity_price_kwh: 0.12,
      antiscalant_price_kg: 5.5,
      acid_base_price_kg: 0.85,
    },
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

  const pushToast = useCallback((msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 1500);
  }, []);

  const sel = useMemo(
    () => nodes.find((n) => n.id === selectedNodeId) || null,
    [nodes, selectedNodeId],
  );
  const selEndpoint = useMemo(() => {
    if (!sel) return null;
    const d = sel.data as any;
    if (d?.type === 'endpoint')
      return sel as Node<FlowData> & { data: EndpointData };
    return null;
  }, [sel]);

  const stageTypeHint = useMemo(() => {
    if (sel && (sel.data as any).type === 'unit') {
      const k = (sel.data as UnitData).kind as UnitKind;
      if (k === 'PUMP') return undefined;
      return k;
    }
    return undefined;
  }, [sel]);

  // 💡 [패치 1] 함수형 업데이트 적용: `feed` 상태 의존성 제거로 리렌더링 방어
  const toggleUnits = useCallback(
    (next: UnitMode) => {
      if (next === unitMode) return;

      setFeed((prev) => ({
        ...prev,
        flow_m3h: convFlow(prev.flow_m3h, unitMode, next),
        temperature_C: convTemp(prev.temperature_C, unitMode, next),
        pressure_bar:
          typeof prev.pressure_bar === 'number'
            ? convPress(prev.pressure_bar, unitMode, next)
            : prev.pressure_bar,
      }));

      setNodes((arr) =>
        arr.map((n) => {
          const d = n.data as any;
          if (!d || d.type !== 'unit') return n;
          if (d.kind === 'HRRO') {
            const c = d.cfg as HRROConfig;
            return {
              ...n,
              data: {
                ...d,
                cfg: {
                  ...c,
                  p_set_bar: convPress(c.p_set_bar, unitMode, next),
                },
              },
            } as Node<FlowData>;
          }
          if (['RO', 'NF'].includes(d.kind)) {
            const c = clone(d.cfg) as ROConfig | NFConfig;
            if (c.mode === 'pressure' && typeof c.pressure_bar === 'number')
              c.pressure_bar = convPress(c.pressure_bar, unitMode, next);
            if (c.mode === 'flow' && typeof c.flow_target_m3h === 'number')
              c.flow_target_m3h = convFlow(c.flow_target_m3h, unitMode, next);
            if (typeof c.permeate_back_pressure_bar === 'number')
              c.permeate_back_pressure_bar = convPress(
                c.permeate_back_pressure_bar,
                unitMode,
                next,
              );
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
            } else if (typeof c.pre_stage_dp_bar === 'number') {
              c.pre_stage_dp_bar = convPress(
                c.pre_stage_dp_bar,
                unitMode,
                next,
              );
            }
            return { ...n, data: { ...d, cfg: c } } as Node<FlowData>;
          }
          if (d.kind === 'MF') {
            const c = d.cfg as MFConfig;
            return {
              ...n,
              data: {
                ...d,
                cfg: {
                  ...c,
                  pressure_bar:
                    c.mode === 'pressure' && typeof c.pressure_bar === 'number'
                      ? convPress(c.pressure_bar, unitMode, next)
                      : c.pressure_bar,
                  mf_filtrate_flux_lmh_25C:
                    typeof c.mf_filtrate_flux_lmh_25C === 'number'
                      ? convFlux(c.mf_filtrate_flux_lmh_25C, unitMode, next)
                      : c.mf_filtrate_flux_lmh_25C,
                  mf_backwash_flux_lmh:
                    typeof c.mf_backwash_flux_lmh === 'number'
                      ? convFlux(c.mf_backwash_flux_lmh, unitMode, next)
                      : c.mf_backwash_flux_lmh,
                },
              },
            } as Node<FlowData>;
          }
          if (d.kind === 'UF') {
            const c = d.cfg as UFConfig;
            return {
              ...n,
              data: {
                ...d,
                cfg: {
                  ...c,
                  filtrate_flux_lmh_25C:
                    typeof c.filtrate_flux_lmh_25C === 'number'
                      ? convFlux(c.filtrate_flux_lmh_25C, unitMode, next)
                      : c.filtrate_flux_lmh_25C,
                  backwash_flux_lmh:
                    typeof c.backwash_flux_lmh === 'number'
                      ? convFlux(c.backwash_flux_lmh, unitMode, next)
                      : c.backwash_flux_lmh,
                },
              },
            } as Node<FlowData>;
          }
          return n;
        }),
      );
      setUnitMode(next);
    },
    [setNodes, unitMode],
  );

  // 💡 [패치 2] 디바운싱(Debouncing) 적용: 노드 드래그 시 60fps 렌더링 지연 원천 차단
  useEffect(() => {
    const payload = {
      unitMode,
      scenarioName,
      feed,
      feedChemistry,
      nodes,
      edges,
      opt: {
        pump_eff: optPumpEff,
        erd_eff: optErdEff,
        segments: optSegments,
      },
      opex: opexConfig,
      data,
      chemSummary,
    };

    // 상태 변경 후 500ms 동안 추가 변경이 없을 때만 스토리지에 기록합니다.
    const timeoutId = setTimeout(() => {
      try {
        sessionStorage.setItem(SESSION_KEY, JSON.stringify(payload));
      } catch (e) {
        console.warn('Auto-save failed:', e);
      }
    }, 500);

    // 컴포넌트 언마운트 또는 다음 렌더링 시 이전 타이머 취소
    return () => clearTimeout(timeoutId);
  }, [
    unitMode,
    scenarioName,
    feed,
    feedChemistry,
    nodes,
    edges,
    optPumpEff,
    optErdEff,
    optSegments,
    opexConfig,
    data,
    chemSummary,
  ]);

  return {
    rfRef,
    INITIAL_NODES,
    unitMode,
    setUnitMode,
    scenarioName,
    setScenarioName,
    libraryOpen,
    setLibraryOpen,
    libraryItems,
    setLibraryItems,
    feed,
    setFeed,
    feedChemistry,
    setFeedChemistry,
    optPumpEff,
    setOptPumpEff,
    optErdEff,
    setOptErdEff,
    optSegments,
    setOptSegments,
    opexConfig,
    setOpexConfig,
    nodes,
    setNodes,
    onNodesChange,
    edges,
    setEdges,
    onEdgesChange,
    selectedNodeId,
    setSelectedNodeId,
    loading,
    setLoading,
    err,
    setErr,
    data,
    setData,
    chemSummary,
    setChemSummary,
    editorOpen,
    setEditorOpen,
    optionsOpen,
    setOptionsOpen,
    toast,
    setToast,
    pushToast,
    sel,
    selEndpoint,
    stageTypeHint,
    toggleUnits,
  };
}
