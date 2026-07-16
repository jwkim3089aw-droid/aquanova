// ui/src/features/simulation/hooks/flow/useFlowTracer.ts
import { useMemo } from 'react';
import { Node, Edge } from 'reactflow';
import { isUnitNode } from '../../model/logic';
import { FlowData } from '../../model/types';

export function useFlowTracer(props: {
  sel: Node<FlowData> | null;
  edges: Edge[];
  nodes: Node<FlowData>[];
  feedFlow: number;
}) {
  const { sel, edges, nodes, feedFlow } = props;

  const selUnit = useMemo(() => {
    if (!isUnitNode(sel)) return null;

    let incoming = feedFlow;
    let currId = 'feed';
    let safeLoop = 0;
    let foundPath = false;

    while (currId !== sel.id && safeLoop < 100) {
      safeLoop++;
      const nextEdge = edges.find((e) => e.source === currId);
      if (!nextEdge) break;

      const prevNode = nodes.find((n) => n.id === currId);
      if (prevNode && prevNode.id !== 'feed') {
        const d = prevNode.data as any;
        if (d?.kind === 'UF' || d?.kind === 'MF') {
          const stRec = (d.cfg?.strainer_recovery_pct ?? 100) / 100;
          const targetRec = (d.cfg?.recovery_target_pct ?? 94.17) / 100;
          incoming = incoming * stRec * targetRec;
        } else if (['HRRO', 'RO', 'NF'].includes(d?.kind)) {
          const targetRec = (d.cfg?.recovery_target_pct ?? 90) / 100;
          incoming = incoming * targetRec;
        }
      }

      currId = nextEdge.target;
      if (currId === sel.id) {
        foundPath = true;
        break;
      }
    }

    return {
      ...sel,
      data: {
        ...sel.data,
        computed_feed_flow: foundPath ? incoming : 0,
      },
    };
  }, [sel, edges, nodes, feedFlow]);

  return { selUnit };
}
