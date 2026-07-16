// ui/src/features/simulation/hooks/flow/useFlowHistory.ts
import { useState, useCallback } from 'react';
import { Node, Edge } from 'reactflow';
import { clone } from '../../model/logic';
import { FlowData, Snapshot } from '../../model/types';

export function useFlowHistory(props: {
  nodes: Node<FlowData>[];
  edges: Edge[];
  setNodes: Function;
  setEdges: Function;
}) {
  const { nodes, edges, setNodes, setEdges } = props;
  const [history, setHistory] = useState<{
    past: Snapshot[];
    future: Snapshot[];
  }>({ past: [], future: [] });

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

  return {
    history,
    setHistory,
    pushHistory,
    undo,
    redo,
    canUndo: history.past.length > 0,
    canRedo: history.future.length > 0,
  };
}
