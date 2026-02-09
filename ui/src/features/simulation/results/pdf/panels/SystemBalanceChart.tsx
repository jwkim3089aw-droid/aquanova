// ui/src/features/simulation/results/pdf/panels/SystemBalanceChart.tsx
import React from 'react';
import {
  ComposedChart,
  Line,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from 'recharts';
import { AutoSizedChart } from '../components';
import { hasAnyNumber } from '../utils';
import { UnitLabels } from '../types';

export function SystemBalanceChart({
  stageData,
  u,
}: {
  stageData: any[];
  u: UnitLabels;
}) {
  const hasFlux = hasAnyNumber(stageData, 'flux');
  const hasNdp = hasAnyNumber(stageData, 'ndp');

  if (!stageData.length || (!hasFlux && !hasNdp)) {
    return (
      <div className="text-[10px] text-slate-500">
        표시할 스테이지 차트 데이터가 없습니다.
      </div>
    );
  }

  return (
    <AutoSizedChart className="h-56 rounded-xl border border-slate-200 bg-slate-50 p-3 min-w-0 min-h-0">
      {({ width, height }) => (
        <ComposedChart
          width={width}
          height={height}
          data={stageData}
          margin={{ top: 10, right: 12, bottom: 10, left: 10 }}
        >
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="stage" tick={{ fontSize: 10 }} />
          <YAxis yAxisId="left" tick={{ fontSize: 10 }} width={34} />
          <YAxis
            yAxisId="right"
            orientation="right"
            tick={{ fontSize: 10 }}
            width={34}
          />
          <Tooltip />
          {hasFlux ? (
            <Bar
              yAxisId="left"
              dataKey="flux"
              fill="#3b82f6"
              name={`Flux (${u.flux})`}
              barSize={32}
            />
          ) : null}
          {hasNdp ? (
            <Line
              yAxisId="right"
              type="monotone"
              dataKey="ndp"
              stroke="#10b981"
              name={`NDP (${u.pressure})`}
              strokeWidth={2}
              dot={false}
              isAnimationActive={false}
            />
          ) : null}
        </ComposedChart>
      )}
    </AutoSizedChart>
  );
}
