// ui/src/features/simulation/results/pdf/panels/HRROHistoryChart.tsx
import React from 'react';
import {
  ComposedChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Area,
} from 'recharts';
import { AutoSizedChart } from '../components';
import { pickNumber, safeArr } from '../utils';
import { UnitLabels } from '../types';

export function HRROHistoryChart({
  history,
  unitLabels,
}: {
  history: any[];
  unitLabels: UnitLabels;
}) {
  const h = safeArr(history);
  if (h.length < 2) {
    return (
      <div className="text-[10px] text-slate-500">
        차트를 그리기엔 time history 포인트가 부족합니다 (n={h.length}).
      </div>
    );
  }

  const data = h.map((d) => ({
    time_min: pickNumber(d?.time_min) ?? 0,
    pressure_bar: pickNumber(d?.pressure_bar) ?? 0,
    tds_mgL: pickNumber(d?.tds_mgL) ?? 0,
    flux_lmh: pickNumber(d?.flux_lmh) ?? 0,
    recovery_pct: pickNumber(d?.recovery_pct) ?? 0,
  }));

  return (
    <AutoSizedChart className="h-56 rounded-xl border border-slate-200 bg-slate-50 p-3 min-w-0 min-h-0">
      {({ width, height }) => (
        <ComposedChart
          width={width}
          height={height}
          data={data}
          margin={{ top: 10, right: 12, bottom: 10, left: 10 }}
        >
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="time_min" tick={{ fontSize: 10 }} />
          <YAxis yAxisId="left" tick={{ fontSize: 10 }} width={34} />
          <YAxis
            yAxisId="right"
            orientation="right"
            domain={[0, 100]}
            tick={{ fontSize: 10 }}
            width={34}
          />
          <Tooltip />
          <Area
            yAxisId="left"
            type="monotone"
            dataKey="tds_mgL"
            fill="#10b981"
            stroke="#10b981"
            fillOpacity={0.14}
            name="TDS (mg/L)"
            isAnimationActive={false}
          />
          <Line
            yAxisId="left"
            type="monotone"
            dataKey="pressure_bar"
            stroke="#fb923c"
            strokeWidth={2}
            name={`압력 (${unitLabels.pressure ?? 'bar'})`}
            dot={false}
            isAnimationActive={false}
          />
          <Line
            yAxisId="left"
            type="monotone"
            dataKey="flux_lmh"
            stroke="#3b82f6"
            strokeWidth={2}
            name={`플럭스 (${unitLabels.flux ?? 'LMH'})`}
            dot={false}
            isAnimationActive={false}
          />
          <Line
            yAxisId="right"
            type="monotone"
            dataKey="recovery_pct"
            stroke="#7c3aed"
            strokeWidth={2}
            name="회수율 (%)"
            dot={false}
            strokeDasharray="4 3"
            isAnimationActive={false}
          />
        </ComposedChart>
      )}
    </AutoSizedChart>
  );
}
