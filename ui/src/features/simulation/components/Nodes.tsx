// ui/src/features/flow-builder/ui/components/Nodes.tsx

import React from 'react';
import type { NodeProps } from 'reactflow';
import { Handle, Position as RFPosition } from 'reactflow';
import { Waves, Zap } from 'lucide-react'; // Zap(번개) 아이콘 추가

import IONode from '@/components/nodes/IONode';
import IconRO from '@/components/icons/IconRO';
import IconHRRO from '@/components/icons/IconHRRO';
import IconUF from '@/components/icons/IconUF';
import IconMF from '@/components/icons/IconMF';
import IconNF from '@/components/icons/IconNF';
// 펌프 아이콘은 이제 선택사항이지만, 파일이 있다면 import 유지
import { HANDLE_STYLE } from '../model/types';

// ==============================
// Node components
// ==============================

function iconFor(k: UnitKind | 'PUMP'): React.ReactElement {
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

export function UnitNode({ data, selected }: NodeProps<UnitData>) {
  const cfg = data.cfg as any;
  const kind = data.kind;

  // [로직 수정] 노드 상태 텍스트 (펌프 포함)
  let modeText: string | null = null;
  let showPumpIcon = false;

  if (kind === 'PUMP') {
    // 1. 독립 펌프 노드인 경우
    modeText = `${cfg.pressure_bar ?? '-'} bar`;
  } else if (kind !== 'HRRO') {
    // 2. 일반 멤브레인 유닛 (RO, UF, NF, MF)

    // (A) 내장 펌프가 켜져 있는지 확인
    if (cfg.enable_pump && cfg.pump_pressure_bar > 0) {
      showPumpIcon = true; // 번개 아이콘 표시 플래그
    }

    // (B) 운전 모드 텍스트 (압력 vs 회수율)
    // 펌프가 켜져있으면 펌프 압력을 우선 보여줄지, 기존 모드를 보여줄지 결정
    if (showPumpIcon) {
      modeText = `${cfg.pump_pressure_bar} bar`; // 펌프 압력 표시
    } else if ('mode' in cfg) {
      modeText =
        cfg.mode === 'pressure'
          ? `P=${cfg.pressure_bar ?? '-'}`
          : `R=${cfg.recovery_target_pct ?? '-'}%`;
    }
  }

  return (
    <div
      className={`relative rounded-xl border px-2 py-1 shadow-sm bg-slate-900 text-slate-200 transition-all ${
        selected
          ? 'ring-2 ring-sky-500/70 border-sky-500/60'
          : 'border-slate-700 hover:border-slate-500'
      }`}
    >
      <div className="flex items-center gap-2">
        {/* 유닛 아이콘 */}
        <div className="flex items-center justify-center w-6 h-6 bg-slate-800 rounded-full border border-slate-700/50">
          {iconFor(kind)}
        </div>

        <div className="flex flex-col min-w-[40px]">
          <div className="flex items-center gap-1">
            <span className="text-[12px] font-bold text-slate-100">{kind}</span>
            {/* 내장 펌프 활성 시 번개 아이콘 표시 */}
            {showPumpIcon && (
              <Zap className="w-3 h-3 text-emerald-400 fill-emerald-400/20" />
            )}
          </div>

          {/* 하단 텍스트 (압력 or 회수율) */}
          {modeText && (
            <div
              className={`text-[9px] font-mono leading-none mt-0.5 ${showPumpIcon ? 'text-emerald-300' : 'text-slate-400'}`}
            >
              {modeText}
            </div>
          )}
        </div>
      </div>

      <Handle
        type="target"
        position={RFPosition.Left}
        id="in"
        className="!w-2.5 !h-2.5 !bg-slate-400 hover:!bg-blue-500 transition-colors"
        style={{ ...HANDLE_STYLE, left: -6 }}
      />

      <Handle
        type="source"
        position={RFPosition.Right}
        id="out"
        className="!w-2.5 !h-2.5 !bg-slate-400 hover:!bg-blue-500 transition-colors"
        style={{ ...HANDLE_STYLE, right: -6 }}
      />
    </div>
  );
}

export const nodeTypes: Record<string, any> = {
  endpoint: IONode,
  unit: UnitNode,
  // legacy alias
  io: IONode,
  feed: IONode,
  product: IONode,
};
