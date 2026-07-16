// ui/src/features/simulation/hooks/useFlowLogic.ts
import { useFlowState } from './flow/useFlowState';
import { useFlowHistory } from './flow/useFlowHistory';
import { useFlowTracer } from './flow/useFlowTracer';
import { useFlowRunner } from './flow/useFlowRunner';
import { useFlowStorage } from './flow/useFlowStorage';
import { useFlowEvents } from './flow/useFlowEvents';

export function useFlowLogic() {
  const state = useFlowState();

  const history = useFlowHistory({
    nodes: state.nodes,
    edges: state.edges,
    setNodes: state.setNodes,
    setEdges: state.setEdges,
  });

  const tracer = useFlowTracer({
    sel: state.sel,
    edges: state.edges,
    nodes: state.nodes,
    feedFlow: state.feed.flow_m3h,
  });

  const runner = useFlowRunner({ ...state });

  const storage = useFlowStorage({
    state,
    history,
    INITIAL_NODES: state.INITIAL_NODES,
  });

  const events = useFlowEvents({
    ...state,
    pushHistory: history.pushHistory,
    undo: history.undo,
    redo: history.redo,
    onRun: runner.onRun,
    selUnit: tracer.selUnit,
  });

  return {
    ...state, // 상태 및 기본 함수 (feed, nodes, edges, setFeed, toggleUnits 등)
    ...history, // undo, redo, canUndo 등
    ...tracer, // selUnit (실시간 유량 추적기가 부착된 선택 노드)
    ...runner, // onRun
    ...storage, // saveLocal, loadLocal, resetAll 등
    ...events, // onConnect, onDrop 등 이벤트 핸들러
  };
}
