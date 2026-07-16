// ui/src/components/common/DetailedResultModal/tabs/ChemistryTab.tsx
import React, { memo, useMemo, useState, useEffect, useRef } from 'react';
import {
  FlaskConical,
  Info,
  ShieldAlert,
  CheckCircle2,
  AlertTriangle,
  Beaker,
} from 'lucide-react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceDot,
  ReferenceLine,
} from 'recharts';
import { ChemCard } from '../SharedComponents';
import { fmt } from '../../../../features/simulation/model/types';

function ScalingBadge({
  label,
  value,
  limit,
  isPercentage = false,
}: {
  label: string;
  value: number;
  limit: number;
  isPercentage?: boolean;
}) {
  const isDanger = value > limit;
  const isWarning = value > limit * 0.8 && !isDanger;

  let statusClass = 'bg-emerald-950/30 border-emerald-500/30 text-emerald-400';
  let icon = <CheckCircle2 className="w-3.5 h-3.5" />;

  if (isDanger) {
    statusClass =
      'bg-rose-950/50 border-rose-500/50 text-rose-400 shadow-[0_0_15px_rgba(244,63,94,0.2)] animate-pulse';
    icon = <ShieldAlert className="w-3.5 h-3.5" />;
  } else if (isWarning) {
    statusClass = 'bg-amber-950/40 border-amber-500/40 text-amber-400';
    icon = <AlertTriangle className="w-3.5 h-3.5" />;
  }

  return (
    <div
      className={`flex flex-col p-3 rounded-lg border gap-1.5 ${statusClass}`}
    >
      <div className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wide opacity-90">
        {icon} {label}
      </div>
      <div className="text-xl font-mono font-bold tracking-tight">
        {fmt(value, 2)}
        <span className="text-xs ml-0.5 font-sans font-normal opacity-70">
          {isPercentage ? '%' : ''}
        </span>
      </div>
    </div>
  );
}

function getBoricAcidPKa(tempC: number) {
  const tk = tempC + 273.15;
  return 2273.4 / tk + 0.01756 * tk - 3.385;
}

function BoronIonizationChart({
  currentPh,
  tempC = 25,
}: {
  currentPh: number;
  tempC?: number;
}) {
  const pKa = getBoricAcidPKa(tempC);

  // 🚀 [궁극의 패치] ResizeObserver를 통해 컨테이너의 실제 Pixel 너비를 실시간으로 가져옵니다.
  const containerRef = useRef<HTMLDivElement>(null);
  const [chartWidth, setChartWidth] = useState<number>(0);

  useEffect(() => {
    if (!containerRef.current) return;
    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const width = entry.contentRect.width;
        if (width > 0) {
          setChartWidth(width);
        }
      }
    });
    observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, []);

  const chartData = useMemo(() => {
    const data = [];
    for (let i = 60; i <= 110; i += 1) {
      const ph = i / 10;
      const borateFraction = 1 / (1 + Math.pow(10, pKa - ph));
      const rejection = borateFraction * 99.5 + (1 - borateFraction) * 40;
      data.push({
        ph: Number(ph.toFixed(1)),
        borate: Number((borateFraction * 100).toFixed(1)),
        rejection: Number(rejection.toFixed(1)),
      });
    }
    return data;
  }, [pKa]);

  const safePKa = Number(
    Math.max(6.0, Math.min(11.0, Math.round(pKa * 10) / 10)).toFixed(1),
  );
  const safePh = Number(
    Math.max(6.0, Math.min(11.0, Math.round(currentPh * 10) / 10)).toFixed(1),
  );

  const currentBorateFraction = 1 / (1 + Math.pow(10, pKa - currentPh));
  const currentRejection =
    currentBorateFraction * 99.5 + (1 - currentBorateFraction) * 40;

  return (
    <div className="bg-slate-900/40 border border-slate-700/50 rounded-xl p-5 shadow-lg col-span-1 md:col-span-2 mt-6">
      <div className="flex items-center justify-between mb-4">
        <div className="text-[11px] font-bold text-blue-400 uppercase tracking-wide flex items-center gap-1.5">
          <Beaker className="w-4 h-4" /> 붕소(Boron) 이온화율 및 추정 배제율
          (pKa: {pKa.toFixed(2)})
        </div>
        <div className="text-xs text-slate-300 font-mono bg-slate-950 px-2 py-1 rounded border border-slate-800">
          Target pH:{' '}
          <span className="text-emerald-400 font-bold">
            {currentPh.toFixed(1)}
          </span>{' '}
          → Rejection:{' '}
          <span className="text-emerald-400 font-bold">
            {currentRejection.toFixed(1)}%
          </span>
        </div>
      </div>

      {/* 🚀 측정용 컨테이너 (스크롤 없음) */}
      <div ref={containerRef} className="w-full h-[280px]">
        {chartWidth > 0 ? (
          <LineChart
            width={chartWidth}
            height={280}
            data={chartData}
            margin={{ top: 20, right: 30, bottom: 5, left: -20 }}
          >
            <CartesianGrid
              strokeDasharray="3 3"
              stroke="#334155"
              vertical={false}
            />
            <XAxis
              dataKey="ph"
              stroke="#94a3b8"
              tick={{ fontSize: 11 }}
              tickFormatter={(val) => `pH ${val}`}
              minTickGap={20}
            />
            <YAxis
              stroke="#94a3b8"
              tick={{ fontSize: 11 }}
              domain={[0, 100]}
              tickFormatter={(val) => `${val}%`}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: '#0f172a',
                borderColor: '#334155',
                fontSize: '12px',
                color: '#f8fafc',
                borderRadius: '8px',
              }}
              itemStyle={{ color: '#38bdf8' }}
              labelFormatter={(val) => `Target pH: ${val}`}
            />

            <Line
              isAnimationActive={false}
              type="monotone"
              dataKey="borate"
              name="붕산염 이온(Borate) 비율"
              stroke="#6366f1"
              strokeWidth={3}
              dot={false}
              activeDot={{ r: 6, fill: '#6366f1', stroke: '#1e1b4b' }}
            />
            <Line
              isAnimationActive={false}
              type="monotone"
              dataKey="rejection"
              name="붕소 제거율(Rejection)"
              stroke="#10b981"
              strokeWidth={3}
              strokeDasharray="5 5"
              dot={false}
              activeDot={{ r: 6, fill: '#10b981', stroke: '#022c22' }}
            />

            <ReferenceLine
              x={safePKa}
              stroke="#fbbf24"
              strokeDasharray="3 3"
              label={{
                position: 'insideTopLeft',
                value: `pKa (${pKa.toFixed(2)})`,
                fill: '#fbbf24',
                fontSize: 11,
                fontWeight: 'bold',
              }}
            />

            <ReferenceDot
              x={safePh}
              y={Number((currentBorateFraction * 100).toFixed(1))}
              r={6}
              fill="#6366f1"
              stroke="#1e1b4b"
              strokeWidth={2}
            />
            <ReferenceDot
              x={safePh}
              y={Number(currentRejection.toFixed(1))}
              r={6}
              fill="#10b981"
              stroke="#022c22"
              strokeWidth={2}
            />
          </LineChart>
        ) : (
          <div className="w-full h-full flex items-center justify-center text-slate-500 text-xs">
            그래프 로딩 중...
          </div>
        )}
      </div>
      <div className="mt-4 text-[10px] text-slate-500 leading-relaxed text-center">
        * 붕소(B)는 pH가 상승하여 붕산염(B(OH)₄⁻)으로 이온화될수록 정전기적
        반발력에 의해 RO 멤브레인 제거율이 99% 이상으로 급상승합니다. (중성 붕산
        제거율은 약 40%로 가정)
      </div>
    </div>
  );
}

export const ChemistryTab = memo(function ChemistryTab({
  chemistry,
  dosing,
  feedWater,
}: {
  chemistry: any;
  dosing?: any;
  feedWater?: any;
}) {
  const feed = chemistry?.feed || {};
  const brine = chemistry?.final_brine || {};
  const hasData = chemistry && Object.keys(feed).length > 0;

  const currentPh = Number(dosing?.target_ph ?? feedWater?.ph ?? 7.5);
  const tempC = Number(feedWater?.temperature_C ?? 25.0);

  return (
    <div className="p-8 max-w-[1200px] mx-auto animate-in fade-in duration-300">
      <div className="mb-6 flex items-end justify-between border-b border-slate-800 pb-4">
        <div>
          <h3 className="text-xl font-bold text-slate-100 flex items-center gap-2">
            <FlaskConical className="w-6 h-6 text-purple-400" /> 수질 화학 및
            스케일링 (Chemistry & Scaling)
          </h3>
          <p className="text-xs text-slate-400 mt-2 tracking-wide">
            유입수 수질을 기반으로 농축수(Brine)에서 발생할 수 있는 스케일링
            리스크를 예측합니다.
          </p>
        </div>
      </div>

      {!hasData ? (
        <div className="flex flex-col items-center justify-center min-h-[300px] text-slate-400 bg-slate-900/40 rounded-xl border border-slate-700/50 shadow-inner">
          <Info className="w-10 h-10 mb-3 text-blue-400/70" />
          <p className="text-sm font-bold text-slate-300">
            수질 화학 연산 결과가 없습니다.
          </p>
          <p className="text-xs mt-2 text-slate-500">
            UF 등 물리적 여과 스테이지이거나, 화학 모듈이 비활성화된 상태입니다.
          </p>
        </div>
      ) : (
        <div className="space-y-6">
          {chemistry.final_brine && (
            <div className="bg-slate-900/40 border border-slate-700/50 rounded-xl p-5 shadow-lg">
              <div className="text-[11px] font-bold text-slate-300 uppercase tracking-wide mb-4">
                주요 스케일링 지표 모니터링 (농축수 기준)
              </div>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <ScalingBadge
                  label="LSI (랑겔리아)"
                  value={brine.lsi ?? -99}
                  limit={1.8}
                />
                <ScalingBadge
                  label="S&DSI"
                  value={brine.sdsi ?? -99}
                  limit={1.8}
                />
                <ScalingBadge
                  label="CaSO4 포화도"
                  value={brine.caso4_sat_pct ?? 0}
                  limit={100}
                  isPercentage
                />
                <ScalingBadge
                  label="SiO2 포화도"
                  value={brine.sio2_sat_pct ?? 0}
                  limit={100}
                  isPercentage
                />
              </div>
            </div>
          )}

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <ChemCard title="유입수 (Feed Water)" color="blue" data={feed} />
            {chemistry.final_brine ? (
              <ChemCard
                title="농축수 (Concentrate / Brine)"
                color="orange"
                data={brine}
              />
            ) : (
              <div className="bg-slate-900/20 border border-slate-800 border-dashed rounded-xl flex items-center justify-center h-full text-slate-500">
                농축수 데이터 없음 (No Brine Data)
              </div>
            )}

            {/* 🚀 무적의 붕소 이온화 차트 */}
            <BoronIonizationChart currentPh={currentPh} tempC={tempC} />
          </div>
        </div>
      )}
    </div>
  );
});
