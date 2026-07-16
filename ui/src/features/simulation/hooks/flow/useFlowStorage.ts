// ui/src/features/simulation/hooks/flow/useFlowStorage.ts
import { useCallback } from 'react';
import { PersistModel, DEFAULT_CHEMISTRY } from '../../model/types';
import { loadLibrary, LS_KEY, LS_SCNS } from '../../model/logic';
import { ensureUnitCfg } from '../../FlowBuilder.utils';
import { migrateFeedState, DEFAULT_FEED, SESSION_KEY } from './utils';

// 🚀 방금 만든 API 함수들 임포트!
import {
  saveScenarioToDB,
  getScenariosFromDB,
  getScenarioStateFromDB,
} from '../../../../api/simulation';

const CURRENT_DB_SCENARIO_ID_KEY = 'AQUANOVA_CURRENT_DB_SCENARIO_ID';

export function useFlowStorage(props: {
  state: any;
  history: any;
  INITIAL_NODES: any[];
}) {
  const { state, history, INITIAL_NODES } = props;
  const {
    nodes,
    edges,
    feed,
    optSegments,
    optPumpEff,
    optErdEff,
    scenarioName,
    feedChemistry,
    opexConfig,
    pushToast,
    setNodes,
    setEdges,
    setFeed,
    setOptSegments,
    setOptPumpEff,
    setOptErdEff,
    setScenarioName,
    setFeedChemistry,
    setOpexConfig,
    setLibraryOpen,
    libraryItems,
    setLibraryItems,
    setSelectedNodeId,
    setData,
    setErr,
    setChemSummary,
    setEditorOpen,
    rfRef,
  } = state;
  const { setHistory } = history;

  // ==========================================================================
  // 🌟 NEW: 백엔드 DB 연동(Cloud Sync) 로직
  // ==========================================================================

  /**
   * 캔버스를 DB에 영구 저장 (Upsert 지원)
   */
  const saveToDB = useCallback(async () => {
    pushToast('Saving to DB...', 'info');

    // 현재 캔버스의 모든 데이터를 영혼까지 끌어모음
    const payload: PersistModel = {
      nodes,
      edges,
      feed,
      name: scenarioName,
      chemistry: feedChemistry,
      opex: opexConfig,
      opt: { segments: optSegments, pump_eff: optPumpEff, erd_eff: optErdEff },
    };

    try {
      // 이전에 저장해서 발급받은 ID가 있다면 덮어쓰기(Update)를 위해 꺼냄
      const existingId = sessionStorage.getItem(CURRENT_DB_SCENARIO_ID_KEY);

      const res = await saveScenarioToDB({
        scenario_id: existingId || undefined, // ID가 있으면 Update, 없으면 Insert
        name: scenarioName || 'Untitled Scenario',
        canvas_state: payload,
      });

      // 덮어쓰기를 위해 방금 발급된 ID를 브라우저 세션에 임시 보관
      sessionStorage.setItem(CURRENT_DB_SCENARIO_ID_KEY, res.scenario_id);
      pushToast('✅ Saved to Database successfully!');
    } catch (error) {
      console.error('DB Save Error:', error);
      pushToast('❌ Failed to save to Database', 'error');
    }
  }, [
    nodes,
    edges,
    feed,
    optSegments,
    optPumpEff,
    optErdEff,
    scenarioName,
    feedChemistry,
    opexConfig,
    pushToast,
  ]);

  /**
   * DB에서 특정 시나리오를 캔버스로 완벽 복원
   */
  const loadFromDB = useCallback(
    async (scenarioId: string) => {
      pushToast('Loading from DB...', 'info');
      try {
        const dbData = await getScenarioStateFromDB(scenarioId);
        const p = dbData.canvas_state as PersistModel;

        // DB 상태를 현재 UI 상태로 덮어쓰기
        setNodes(ensureUnitCfg(p.nodes));
        setEdges(p.edges);
        setFeed(migrateFeedState(p.feed));
        setOptSegments(p.opt?.segments ?? 10);
        setOptPumpEff(p.opt?.pump_eff ?? 0.8);
        setOptErdEff(p.opt?.erd_eff ?? 0.0);
        setScenarioName(p.name || dbData.name);
        setFeedChemistry(p.chemistry ?? DEFAULT_CHEMISTRY);
        if (p.opex) setOpexConfig(p.opex);

        // 불러온 시나리오 ID를 세션에 저장 (이후 저장 버튼 누르면 덮어쓰기 됨)
        sessionStorage.setItem(CURRENT_DB_SCENARIO_ID_KEY, dbData.id);

        setLibraryOpen(false);
        pushToast('✅ Loaded from Database!');
        setTimeout(() => rfRef.current?.fitView?.({ padding: 0.2 }), 50);
      } catch (error) {
        console.error('DB Load Error:', error);
        pushToast('❌ Failed to load from Database', 'error');
      }
    },
    [
      setNodes,
      setEdges,
      setFeed,
      setOptSegments,
      setOptPumpEff,
      setOptErdEff,
      setScenarioName,
      setFeedChemistry,
      setOpexConfig,
      setLibraryOpen,
      pushToast,
      rfRef,
    ],
  );

  /**
   * DB에서 목록만 쫙 당겨오기 (모달창 리스트용)
   */
  const fetchDBLibraryItems = useCallback(async () => {
    try {
      const list = await getScenariosFromDB();
      return list; // [{id, name, created_at}, ...]
    } catch (error) {
      console.error('Fetch Library Error:', error);
      pushToast('Failed to fetch library list', 'error');
      return [];
    }
  }, [pushToast]);

  // ==========================================================================
  // 💾 기존 LocalStorage 로직 (오프라인/임시 백업용으로 유지)
  // ==========================================================================
  const saveLocal = useCallback(() => {
    /* 기존 코드 유지 */
    const payload: PersistModel = {
      nodes,
      edges,
      feed,
      name: scenarioName,
      chemistry: feedChemistry,
      opex: opexConfig,
      opt: { segments: optSegments, pump_eff: optPumpEff, erd_eff: optErdEff },
    };
    localStorage.setItem(LS_KEY, JSON.stringify(payload));
    pushToast('Saved to browser');
  }, [
    nodes,
    edges,
    feed,
    optSegments,
    optPumpEff,
    optErdEff,
    scenarioName,
    feedChemistry,
    opexConfig,
    pushToast,
  ]);

  const loadLocal = useCallback(() => {
    /* 기존 코드 유지 */
    const raw = localStorage.getItem(LS_KEY);
    if (!raw) return pushToast('Nothing saved');
    try {
      const p = JSON.parse(raw) as PersistModel;
      setNodes(ensureUnitCfg(p.nodes));
      setEdges(p.edges);
      setFeed(migrateFeedState(p.feed));
      setOptSegments(p.opt?.segments ?? 10);
      setOptPumpEff(p.opt?.pump_eff ?? 0.8);
      setOptErdEff(p.opt?.erd_eff ?? 0.0);
      if (p.name) setScenarioName(p.name);
      setFeedChemistry(p.chemistry ?? DEFAULT_CHEMISTRY);
      if (p.opex) setOpexConfig(p.opex);
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
    setOptSegments,
    setOptPumpEff,
    setOptErdEff,
    setScenarioName,
    setFeedChemistry,
    setOpexConfig,
    rfRef,
  ]);

  const saveToLibrary = useCallback(() => {
    /* 기존 코드 유지 */
    const entry: PersistModel = {
      nodes,
      edges,
      feed,
      name: scenarioName,
      chemistry: feedChemistry,
      opex: opexConfig,
      opt: { segments: optSegments, pump_eff: optPumpEff, erd_eff: optErdEff },
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
    optSegments,
    optPumpEff,
    optErdEff,
    scenarioName,
    feedChemistry,
    opexConfig,
    pushToast,
    setLibraryItems,
  ]);

  const loadFromLibrary = useCallback(
    (idx: number) => {
      /* 기존 코드 유지 */
      const e = libraryItems[idx];
      if (!e) return;
      setNodes(ensureUnitCfg(e.nodes));
      setEdges(e.edges);
      setFeed(migrateFeedState(e.feed));
      setOptSegments(e.opt?.segments ?? 10);
      setOptPumpEff(e.opt?.pump_eff ?? 0.8);
      setOptErdEff(e.opt?.erd_eff ?? 0.0);
      setScenarioName(e.name ?? 'Loaded Scenario');
      setFeedChemistry(e.chemistry ?? DEFAULT_CHEMISTRY);
      if (e.opex) setOpexConfig(e.opex);
      setLibraryOpen(false);
      pushToast('Loaded from Library');
      setTimeout(() => rfRef.current?.fitView?.({ padding: 0.2 }), 0);
    },
    [
      libraryItems,
      setNodes,
      setEdges,
      setFeed,
      setOptSegments,
      setOptPumpEff,
      setOptErdEff,
      setScenarioName,
      setFeedChemistry,
      setOpexConfig,
      setLibraryOpen,
      pushToast,
      rfRef,
    ],
  );

  const resetAll = useCallback(() => {
    /* 기존 코드 유지 */
    if (window.confirm('정말 모든 작업을 초기화하시겠습니까?')) {
      sessionStorage.removeItem(SESSION_KEY);
      sessionStorage.removeItem(CURRENT_DB_SCENARIO_ID_KEY); // 🧹 초기화 시 DB ID도 같이 날림!
      setNodes(INITIAL_NODES);
      setEdges([]);
      setSelectedNodeId(null);
      setData(null);
      setErr(null);
      setChemSummary(null);
      setHistory({ past: [], future: [] });
      setFeed(DEFAULT_FEED);
      setFeedChemistry(DEFAULT_CHEMISTRY);
      setOpexConfig({
        electricity_price_kwh: 0.12,
        antiscalant_price_kg: 5.5,
        acid_base_price_kg: 0.85,
      });
      setEditorOpen(false);
      setTimeout(() => rfRef.current?.fitView?.({ padding: 0.2 }), 0);
    }
  }, [
    INITIAL_NODES,
    setNodes,
    setEdges,
    setSelectedNodeId,
    setData,
    setErr,
    setChemSummary,
    setHistory,
    setFeed,
    setFeedChemistry,
    setOpexConfig,
    setEditorOpen,
    rfRef,
  ]);

  // 🚀 리턴값에 새로운 DB 연동 함수들 추가!
  return {
    saveLocal,
    loadLocal,
    saveToLibrary,
    loadFromLibrary,
    resetAll,
    saveToDB,
    loadFromDB,
    fetchDBLibraryItems, // <-- DB 삼총사 출격!
  };
}
