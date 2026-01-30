// ui/src/components/nodes/ProcessNode.tsx
import { memo } from 'react';
import { Handle, Position, NodeProps } from 'reactflow';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import { HANDLE_STYLE } from '@/features/simulation/model/types';
import { StageMetric } from '@/api/types';

type ProcessData = {
  label: string;
  metrics?: StageMetric; // 백엔드에서 받은 결과가 여기로 들어옴
};

function ProcessNode({ data, selected }: NodeProps<ProcessData>) {
  const { label, metrics } = data;

  // 그래프 데이터가 있는지 확인
  const chartData = metrics?.time_history || [];
  const hasData = chartData.length > 0;

  // 노드 스타일 (선택되면 테두리 강조)
  const borderClass = selected
    ? 'border-blue-500 ring-2 ring-blue-500/50'
    : 'border-slate-600 hover:border-slate-500';

  return (
    <div
      className={`relative w-[280px] bg-slate-800 rounded-lg border ${borderClass} shadow-xl transition-all`}
    >
      {/* 1. 헤더 (라벨 & KPI) */}
      <div className="px-3 py-2 border-b border-slate-700 bg-slate-900/50 rounded-t-lg flex justify-between items-center">
        <span className="font-semibold text-slate-200 text-sm">{label}</span>
        {metrics && (
          <span className="text-[10px] text-emerald-400 font-mono bg-emerald-400/10 px-1.5 py-0.5 rounded">
            Rec: {metrics.recovery_pct?.toFixed(1)}%
          </span>
        )}
      </div>

      {/* 2. 그래프 영역 (데이터 있을 때만) */}
      <div className="h-[120px] w-full p-2 bg-slate-900/30 rounded-b-lg relative group">
        {hasData ? (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={chartData}>
              <defs>
                <linearGradient id="colorFlux" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#8884d8" stopOpacity={0.8} />
                  <stop offset="95%" stopColor="#8884d8" stopOpacity={0} />
                </linearGradient>
              </defs>
              {/* X축: 시간 */}
              <XAxis dataKey="time_min" hide />

              {/* Y축: Flux (범위 자동) */}
              <YAxis hide domain={['auto', 'auto']} />

              <Tooltip
                contentStyle={{
                  backgroundColor: '#1e293b',
                  borderColor: '#334155',
                  fontSize: '12px',
                }}
                itemStyle={{ color: '#e2e8f0' }}
                labelStyle={{ color: '#94a3b8' }}
                formatter={(value: number) => value.toFixed(2)}
                labelFormatter={(v) => `Time: ${v} min`}
              />

              {/* [핵심] 백엔드 키값(flux_lmh) 사용 */}
              <Area
                type="monotone"
                dataKey="flux_lmh"
                stroke="#8884d8"
                fillOpacity={1}
                fill="url(#colorFlux)"
                name="Flux (LMH)"
              />
              {/* 필요시 라인 추가 가능: pressure_bar, tds_mgL */}
            </AreaChart>
          </ResponsiveContainer>
        ) : (
          <div className="flex items-center justify-center h-full text-xs text-slate-500">
            No Simulation Data
          </div>
        )}
      </div>

      {/* 3. 연결 핸들 (좌:입력, 우:출력) */}
      <Handle
        type="target"
        position={Position.Left}
        id="in"
        style={{ ...HANDLE_STYLE, left: -6, background: '#94a3b8' }}
      />
      <Handle
        type="source"
        position={Position.Right}
        id="out"
        style={{ ...HANDLE_STYLE, right: -6, background: '#94a3b8' }}
      />
    </div>
  );
}

export default memo(ProcessNode);
