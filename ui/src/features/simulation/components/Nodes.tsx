// ui/src/features/flow-builder/ui/components/Nodes.tsx

import React from 'react';
import type { NodeProps } from 'reactflow';
import { Handle, Position as RFPosition } from 'reactflow';
import { Waves, Zap } from 'lucide-react';

import IONode from '@/components/nodes/IONode';
import IconRO from '@/components/icons/IconRO';
import IconHRRO from '@/components/icons/IconHRRO';
import IconUF from '@/components/icons/IconUF';
import IconMF from '@/components/icons/IconMF';
import IconNF from '@/components/icons/IconNF';

// ==============================
// Node components
// ==============================

function iconFor(k: string | 'PUMP'): React.ReactElement {
  switch (k) {
    case 'RO':
      return <IconRO className="w-4 h-4" />;
    case 'HRRO':
      return <IconHRRO className="w-4 h-4" />;
    case 'NF':
      return <IconNF className="w-4 h-4" />;
    case 'UF':
      return <IconUF className="w-4 h-4" />;
    case 'MF':
      return <IconMF className="w-4 h-4" />;
    default:
      return <Waves className="w-4 h-4" />;
  }
}

export function UnitNode({ data, selected }: NodeProps<any>) {
  const cfg = data.cfg as any;
  const kind = data.kind;

  let modeText: string | null = null;
  let showPumpIcon = false;

  if (kind === 'PUMP') {
    modeText = `${cfg.pressure_bar ?? '-'} bar`;
  } else if (kind !== 'HRRO') {
    if (cfg.enable_pump && cfg.pump_pressure_bar > 0) {
      showPumpIcon = true;
    }

    if (showPumpIcon) {
      modeText = `${cfg.pump_pressure_bar} bar`;
    } else if ('mode' in cfg) {
      modeText =
        cfg.mode === 'pressure'
          ? `P=${cfg.pressure_bar ?? '-'}`
          : `R=${cfg.recovery_target_pct ?? '-'}%`;
    }
  }

  return (
    <div
      className={`
        relative flex items-center gap-2 rounded-full border px-3 py-1.5 backdrop-blur-sm transition-all duration-200
        ${
          selected
            ? 'bg-slate-900 border-sky-400 shadow-[0_0_12px_rgba(56,189,248,0.25)] ring-1 ring-sky-400 z-10'
            : 'bg-slate-900/90 border-slate-700 hover:border-slate-500 shadow-sm'
        }
      `}
    >
      {/* 1. 좌측 아이콘 (크기 최적화) */}
      <div className="flex items-center justify-center text-slate-300">
        {iconFor(kind)}
      </div>

      {/* 2. 공정 타이틀 & 펌프 상태 */}
      <div className="flex items-center gap-1">
        <span className="text-[13px] font-bold tracking-wide text-slate-100">
          {kind}
        </span>
        {showPumpIcon && (
          <Zap className="w-3.5 h-3.5 ml-0.5 text-emerald-400 fill-emerald-400/20 animate-pulse" />
        )}
      </div>

      {/* 3. 우측 파라미터 뱃지 (값이 있을 때만 표시, 공간 낭비 방지) */}
      {modeText && (
        <div
          className={`
            ml-1.5 px-1.5 py-0.5 rounded-full text-[10px] font-mono border
            ${
              showPumpIcon
                ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400'
                : 'bg-slate-800 border-slate-600 text-slate-300'
            }
          `}
        >
          {modeText}
        </div>
      )}

      {/* 4. 입력 포트 (Feed 노드 포트 크기와 비슷하게 매칭) */}
      <Handle
        type="target"
        position={RFPosition.Left}
        id="in"
        className={`
          !w-2.5 !h-2.5 !bg-slate-900 !border-2 !border-slate-500 hover:!border-sky-400 hover:!bg-sky-400 transition-colors
          ${selected ? '!border-sky-400' : ''}
        `}
        style={{ left: -5 }}
      />

      {/* 5. 출력 포트 */}
      <Handle
        type="source"
        position={RFPosition.Right}
        id="out"
        className={`
          !w-2.5 !h-2.5 !bg-slate-900 !border-2 !border-slate-500 hover:!border-sky-400 hover:!bg-sky-400 transition-colors
          ${selected ? '!border-sky-400' : ''}
        `}
        style={{ right: -5 }}
      />
    </div>
  );
}

export const nodeTypes: Record<string, any> = {
  endpoint: IONode,
  unit: UnitNode,
  io: IONode,
  feed: IONode,
  product: IONode,
};
