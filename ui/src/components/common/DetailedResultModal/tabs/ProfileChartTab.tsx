// ui/src/components/common/DetailedResultModal/tabs/ProfileChartTab.tsx
import React, { useEffect, useRef, useState, memo } from 'react';
import { Clock, Waves, Loader2, AlertCircle } from 'lucide-react';
import {
  ComposedChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Area,
  ReferenceLine,
} from 'recharts';

// 💡 [최적화] React.memo 적용: 차트 데이터가 변경되지 않으면 리렌더링 차단
export const ProfileChartTab = memo(function ProfileChartTab({
  isHRRO,
  chartData,
}: {
  isHRRO: boolean;
  chartData: any[];
}) {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const [chartSize, setChartSize] = useState({ width: 0, height: 0 });

  useEffect(() => {
    if (!chartContainerRef.current) return;
    const observer = new ResizeObserver((entries) => {
      const { width, height } = entries[0].contentRect;
      requestAnimationFrame(() => setChartSize({ width, height }));
    });
    observer.observe(chartContainerRef.current);
    return () => observer.disconnect();
  }, []);

  return (
    <div className="h-full flex flex-col p-6 animate-in fade-in duration-500 max-w-[1400px] mx-auto w-full">
      <div className="flex-none mb-6 flex justify-between items-end px-2 border-b border-slate-800 pb-4">
        <div>
          <h3 className="text-xl font-bold text-slate-100 flex items-center gap-2">
            {isHRRO ? (
              <Clock className="w-6 h-6 text-blue-400" />
            ) : (
              <Waves className="w-6 h-6 text-blue-400" />
            )}
            {isHRRO
              ? 'HRRO 동적 사이클 분석 (Dynamic Cycle Profile)'
              : '압력 및 플럭스 프로파일 (Pressure & Flux Profile)'}
          </h3>
          <p className="text-xs text-slate-400 mt-2 tracking-wide">
            {isHRRO
              ? '배치(Batch) 운전 시간에 따른 플럭스, 압력, 회수율의 변화 궤적을 시각화합니다.'
              : '압력 베셀(Pressure Vessel) 내 엘리먼트 축 방향 위치에 따른 수력학적 변화량입니다.'}
          </p>
        </div>
      </div>

      <div
        ref={chartContainerRef}
        className="flex-1 bg-slate-900/40 border border-slate-700/50 rounded-2xl p-6 min-h-[450px] relative w-full overflow-hidden shadow-xl"
      >
        {chartData.length > 0 && chartSize.width > 0 ? (
          <ComposedChart
            width={Math.max(10, chartSize.width - 48)}
            height={Math.max(10, chartSize.height - 48)}
            data={chartData}
            margin={{ top: 20, right: 30, bottom: 20, left: 10 }}
          >
            <defs>
              <linearGradient id="colorFlux" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.4} />
                <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
              </linearGradient>
              <linearGradient id="colorPress" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#fb923c" stopOpacity={0.2} />
                <stop offset="95%" stopColor="#fb923c" stopOpacity={0} />
              </linearGradient>
            </defs>

            <CartesianGrid
              strokeDasharray="3 3"
              stroke="#1e293b"
              vertical={false}
            />

            <XAxis
              dataKey={isHRRO ? 'time_min' : 'el'}
              stroke="#64748b"
              tick={{ fontSize: 11, fill: '#94a3b8' }}
              tickLine={false}
              axisLine={{ stroke: '#334155' }}
              tickMargin={10}
            />

            <YAxis
              yAxisId="left"
              stroke="#3b82f6"
              tick={{ fontSize: 11, fill: '#93c5fd' }}
              tickLine={false}
              axisLine={false}
              tickFormatter={(val) => val.toFixed(1)}
            />
            <YAxis
              yAxisId="right"
              orientation="right"
              stroke="#fb923c"
              tick={{ fontSize: 11, fill: '#fdba74' }}
              tickLine={false}
              axisLine={false}
              tickFormatter={(val) => val.toFixed(1)}
            />

            <Tooltip
              contentStyle={{
                backgroundColor: 'rgba(15, 23, 42, 0.95)',
                borderColor: '#334155',
                borderRadius: '12px',
                fontSize: '12px',
                boxShadow: '0 10px 15px -3px rgba(0, 0, 0, 0.5)',
                backdropFilter: 'blur(8px)',
                padding: '12px 16px',
              }}
              itemStyle={{ padding: '4px 0', fontWeight: 'bold' }}
              labelStyle={{
                color: '#94a3b8',
                marginBottom: '8px',
                borderBottom: '1px solid #334155',
                paddingBottom: '8px',
              }}
              formatter={(val: number) => Number(val).toFixed(2)}
              labelFormatter={(label) =>
                isHRRO
                  ? `진행 시간: ${label} min`
                  : `막 번호 (Element): #${label}`
              }
            />

            {isHRRO && (
              <ReferenceLine
                y={60}
                yAxisId="right"
                stroke="#10b981"
                strokeDasharray="3 3"
                label={{
                  position: 'right',
                  value: '목표 (Target)',
                  fill: '#10b981',
                  fontSize: 10,
                }}
              />
            )}

            <Area
              yAxisId="left"
              type="monotone"
              dataKey="flux_lmh"
              fill="url(#colorFlux)"
              stroke="#3b82f6"
              strokeWidth={3}
              name="플럭스 (Flux, LMH)"
              activeDot={{
                r: 6,
                fill: '#3b82f6',
                stroke: '#fff',
                strokeWidth: 2,
              }}
            />
            <Area
              yAxisId="right"
              type="monotone"
              dataKey="pressure_bar"
              fill="url(#colorPress)"
              stroke="#fb923c"
              strokeWidth={3}
              name="압력 (Pressure, bar)"
              activeDot={{
                r: 6,
                fill: '#fb923c',
                stroke: '#fff',
                strokeWidth: 2,
              }}
            />

            {isHRRO && (
              <Line
                yAxisId="right"
                type="monotone"
                dataKey="recovery_pct"
                stroke="#10b981"
                strokeWidth={2}
                strokeDasharray="5 5"
                dot={false}
                name="회수율 (Recovery, %)"
              />
            )}
          </ComposedChart>
        ) : (
          <div className="absolute inset-0 flex flex-col items-center justify-center text-slate-500">
            {chartSize.width === 0 ? (
              <div className="flex flex-col items-center">
                <Loader2 className="w-10 h-10 animate-spin text-blue-500/50 mb-3" />
                <span className="text-xs font-bold tracking-widest">
                  차트 렌더링 중...
                </span>
              </div>
            ) : (
              <div className="flex flex-col items-center p-8 bg-slate-900/50 rounded-full">
                <AlertCircle className="w-12 h-12 mb-3 text-slate-600" />
                <p className="text-sm font-bold text-slate-400">
                  시각화할 프로파일 데이터가 없습니다.
                </p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
});
