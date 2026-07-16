// ui/src/features/simulation/hooks/flow/useFlowEvents.ts
import { useCallback, useEffect, useRef } from 'react';
import { addEdge, Connection, Edge, Node } from 'reactflow';
import type { DragEvent } from 'react';
import { UnitKind, UnitData, FlowData } from '../../model/types';
import { cryptoRandomId, removeNode, nudge } from '../../model/logic';
import { defaultConfig } from '../../FlowBuilder.utils';
import { isEditableTarget } from './utils';

export function useFlowEvents(props: {
  rfRef: any;
  pushHistory: Function;
  setNodes: Function;
  setEdges: Function;
  setSelectedNodeId: Function;
  setEditorOpen: Function;
  undo: Function;
  redo: Function;
  onRun: Function;
  selUnit: any;
}) {
  const {
    rfRef,
    pushHistory,
    setNodes,
    setEdges,
    setSelectedNodeId,
    setEditorOpen,
    undo,
    redo,
    onRun,
    selUnit,
  } = props;

  const onRunRef = useRef(onRun);
  useEffect(() => {
    onRunRef.current = onRun;
  }, [onRun]);
  const selUnitRef = useRef(selUnit);
  useEffect(() => {
    selUnitRef.current = selUnit;
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
      setNodes((prev: any) =>
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
    [pushHistory, setNodes, rfRef, setSelectedNodeId, setEditorOpen],
  );

  const onConnect = useCallback(
    (params: Edge | Connection) => {
      pushHistory();
      setEdges((eds: any) =>
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

  const onNodeClick = useCallback(
    (_e: any, n: Node<FlowData>) => {
      setSelectedNodeId(n.id);
      const d = n.data as any;
      if (d?.type === 'endpoint' || d?.type === 'unit') setEditorOpen(true);
    },
    [setSelectedNodeId, setEditorOpen],
  );

  const onNodeDragStop = useCallback(() => pushHistory(), [pushHistory]);
  const onEdgesDelete = useCallback(() => pushHistory(), [pushHistory]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.defaultPrevented || isEditableTarget(e.target)) return;
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
        removeNode(u.id, setNodes as any, setEdges as any);
        setSelectedNodeId(null);
        setEditorOpen(false);
        return;
      }
      if (
        u &&
        ['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].includes(e.key)
      ) {
        e.preventDefault();
        const step = e.shiftKey ? 6 : 1;
        const dx =
          e.key === 'ArrowLeft' ? -step : e.key === 'ArrowRight' ? step : 0;
        const dy =
          e.key === 'ArrowUp' ? -step : e.key === 'ArrowDown' ? step : 0;
        nudge(u.id, dx, dy, setNodes as any);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [
    undo,
    redo,
    pushHistory,
    setNodes,
    setEdges,
    setSelectedNodeId,
    setEditorOpen,
  ]);

  return {
    onDragStartPalette,
    onDragOver,
    onDrop,
    onConnect,
    onNodeClick,
    onNodeDragStop,
    onEdgesDelete,
  };
}
