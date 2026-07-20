import {
  Activity,
  AlertTriangle,
  ArrowDown,
  ArrowRight,
  CheckCircle2,
  Gauge,
  RotateCcw,
  Waves,
} from 'lucide-react';

type FlowRow = {
  label: string;
  value: string;
};

type Accent =
  | 'blue'
  | 'cyan'
  | 'emerald'
  | 'amber'
  | 'violet'
  | 'slate';

const ACCENTS: Record<Accent, string> = {
  blue: 'border-blue-500/40 bg-blue-950/20',
  cyan: 'border-cyan-500/40 bg-cyan-950/20',
  emerald: 'border-emerald-500/40 bg-emerald-950/20',
  amber: 'border-amber-500/40 bg-amber-950/20',
  violet: 'border-violet-500/40 bg-violet-950/20',
  slate: 'border-slate-600/60 bg-slate-900/50',
};

function asNumber(value: unknown): number | null {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function numberText(
  value: unknown,
  digits = 3,
): string {
  const parsed = asNumber(value);

  if (parsed == null) {
    return '—';
  }

  return parsed.toLocaleString('ko-KR', {
    minimumFractionDigits: 0,
    maximumFractionDigits: digits,
  });
}

function flowText(value: unknown): string {
  return `${numberText(value)} m³/h/PV`;
}

function percentText(value: unknown): string {
  return `${numberText(value, 1)}%`;
}

function FlowCard({
  title,
  subtitle,
  rows,
  accent = 'slate',
  testId,
}: {
  title: string;
  subtitle?: string;
  rows: FlowRow[];
  accent?: Accent;
  testId?: string;
}) {
  return (
    <div
      data-testid={testId}
      className={`min-w-0 rounded-lg border p-3 shadow-inner ${ACCENTS[accent]}`}
    >
      <div className="text-[10.5px] font-black tracking-wide text-slate-100">
        {title}
      </div>

      {subtitle && (
        <div className="mt-0.5 text-[9px] font-medium text-slate-500">
          {subtitle}
        </div>
      )}

      <div className="mt-2 space-y-1.5">
        {rows.map((row) => (
          <div
            key={row.label}
            className="flex items-center justify-between gap-3"
          >
            <span className="text-[9px] font-medium text-slate-500">
              {row.label}
            </span>
            <span className="text-right font-mono text-[10px] font-bold tabular-nums text-slate-200">
              {row.value}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

export function HRROProcessFlowDiagram({
  stage,
  unitPress,
}: {
  stage: any;
  unitPress: string;
}) {
  const cycle = stage?.chemistry?.ccro_cycle;

  if (!cycle) {
    return null;
  }

  const mode = String(
    cycle.pf_mode ?? 'wave_true_plug_flow',
  );

  const modeLabel =
    mode === 'smart_partial_drain'
      ? 'Smart Partial Drain'
      : mode === 'field_optimized_low_fr'
        ? 'Low-FR Field Optimized'
        : 'WAVE True Plug-Flow';

  const smartMode =
    mode === 'smart_partial_drain' ||
    mode === 'field_optimized_low_fr';

  const crossflowOk = cycle.crossflow_ok !== false;
  const capacityOk =
    cycle.p3_recycle_capacity_ok !== false;
  const massBalanceOk =
    cycle.partial_drain_mass_balance_ok !== false;
  const slowFlush =
    cycle.slow_flush_or_poor_salt_displacement === true;

  const healthy =
    crossflowOk &&
    capacityOk &&
    massBalanceOk &&
    !slowFlush;

  const pfFeed =
    cycle.pf_feed_flow_m3h_per_pv;

  const product =
    cycle.pf_permeate_flow_m3h_per_pv ??
    cycle.average_permeate_flow_m3h ??
    stage?.Qp;

  const membraneFeed =
    cycle.pf_membrane_total_feed_flow_m3h_per_pv;

  const concentrate =
    cycle.pf_membrane_concentrate_out_m3h_per_pv ??
    cycle.pf_concentrate_flow_m3h_per_pv;

  const recycle =
    cycle.pf_p3_recycle_flow_m3h_per_pv;

  const drain =
    cycle.pf_external_drain_setpoint_m3h_per_pv ??
    cycle.pf_drain_setpoint_m3h_per_pv;

  const drainFraction =
    asNumber(cycle.pf_drain_fraction_of_concentrate);

  return (
    <div
      data-testid="hrro-process-flow-diagram"
      className="mt-3 border-t border-dashed border-slate-700/50 pt-3"
    >
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-1.5 text-[10.5px] font-bold uppercase text-slate-400">
          <Waves className="h-3.5 w-3.5 text-cyan-400" />
          HRRO / CCRO 공정도
          <span className="normal-case text-slate-600">
            (Process Flow)
          </span>
        </div>

        <div className="flex flex-wrap items-center justify-end gap-1.5">
          <span
            className={`rounded border px-2 py-1 text-[9px] font-bold ${
              smartMode
                ? 'border-cyan-500/30 bg-cyan-950/40 text-cyan-300'
                : 'border-amber-500/30 bg-amber-950/40 text-amber-300'
            }`}
          >
            {modeLabel}
          </span>

          <span className="rounded border border-slate-600 bg-slate-900 px-2 py-1 text-[9px] font-bold text-slate-300">
            FR {numberText(cycle.pf_feed_ratio_pct, 0)}%
          </span>

          <span
            className={`flex items-center gap-1 rounded border px-2 py-1 text-[9px] font-bold ${
              healthy
                ? 'border-emerald-500/30 bg-emerald-950/40 text-emerald-300'
                : 'border-amber-500/30 bg-amber-950/40 text-amber-300'
            }`}
          >
            {healthy ? (
              <CheckCircle2 className="h-3 w-3" />
            ) : (
              <AlertTriangle className="h-3 w-3" />
            )}
            {healthy ? '운전 조건 정상' : '설계 경고 확인'}
          </span>
        </div>
      </div>

      <div className="overflow-x-auto rounded-xl border border-slate-800 bg-slate-950/45 p-3">
        <div className="min-w-[720px]">
          <div className="grid grid-cols-[1fr_38px_1.3fr_38px_1fr] items-center gap-2">
            <FlowCard
              title="Feed / P-2"
              subtitle="PF 원수 공급 · VFD/PID"
              accent="blue"
              testId="hrro-flow-feed"
              rows={[
                {
                  label: 'PF Feed',
                  value: flowText(pfFeed),
                },
                {
                  label: 'Feed Ratio',
                  value: percentText(
                    cycle.pf_feed_ratio_pct,
                  ),
                },
                {
                  label: '막 입구 압력',
                  value: `${numberText(stage?.p_in_bar, 2)} ${unitPress}`,
                },
              ]}
            />

            <div className="flex justify-center text-blue-400">
              <ArrowRight className="h-5 w-5" />
            </div>

            <FlowCard
              title="HRRO Membrane"
              subtitle="CC 농축 → PF 부분 배출"
              accent="cyan"
              testId="hrro-flow-membrane"
              rows={[
                {
                  label: '막 총 유입',
                  value: flowText(membraneFeed),
                },
                {
                  label: '농축수 출구',
                  value: flowText(concentrate),
                },
                {
                  label: '시스템 회수율',
                  value: percentText(
                    stage?.recovery_pct,
                  ),
                },
              ]}
            />

            <div className="flex justify-center text-emerald-400">
              <ArrowRight className="h-5 w-5" />
            </div>

            <FlowCard
              title="Product"
              subtitle="생산수"
              accent="emerald"
              testId="hrro-flow-product"
              rows={[
                {
                  label: '생산수 유량',
                  value: flowText(product),
                },
                {
                  label: '생산수 TDS',
                  value: `${numberText(stage?.Cp, 2)} mg/L`,
                },
                {
                  label: 'PF Recovery',
                  value: percentText(
                    cycle.pf_recovery_pct,
                  ),
                },
              ]}
            />
          </div>

          <div className="my-2 flex justify-center text-cyan-400">
            <ArrowDown className="h-5 w-5" />
          </div>

          <div className="grid grid-cols-3 items-stretch gap-3">
            <FlowCard
              title="Brine Valve / Drain"
              subtitle={
                smartMode
                  ? '부분 개방 PID 배출'
                  : '전개방 배출'
              }
              accent={
                slowFlush ? 'amber' : 'violet'
              }
              testId="hrro-flow-drain"
              rows={[
                {
                  label: '외부 배출',
                  value: flowText(drain),
                },
                {
                  label: '배출 비율',
                  value:
                    drainFraction == null
                      ? '—'
                      : percentText(
                          drainFraction * 100,
                        ),
                },
                {
                  label: '밸브 모드',
                  value: String(
                    cycle.brine_valve_mode ?? '—',
                  ),
                },
              ]}
            />

            <FlowCard
              title="Concentrate Header"
              subtitle="막 출구 농축수 분기"
              accent="slate"
              testId="hrro-flow-concentrate"
              rows={[
                {
                  label: '농축수 유량',
                  value: flowText(concentrate),
                },
                {
                  label: 'CC 재순환',
                  value: flowText(
                    cycle.cc_concentrate_flow_m3h_per_pv,
                  ),
                },
                {
                  label: 'Crossflow',
                  value: crossflowOk
                    ? '정상'
                    : '부족',
                },
              ]}
            />

            <FlowCard
              title="P-3 Recycle"
              subtitle={
                smartMode
                  ? 'PF 중 운전 유지'
                  : 'PF 중 정지'
              }
              accent={
                capacityOk ? 'cyan' : 'amber'
              }
              testId="hrro-flow-recycle"
              rows={[
                {
                  label: '재순환 유량',
                  value: flowText(recycle),
                },
                {
                  label: '설치 용량',
                  value: flowText(
                    cycle.p3_recycle_capacity_m3h_per_pv,
                  ),
                },
                {
                  label: '용량 판정',
                  value: capacityOk
                    ? '정상'
                    : '용량 부족',
                },
              ]}
            />
          </div>

          <div className="mt-3 flex items-center justify-end gap-2 rounded-lg border border-dashed border-cyan-700/40 bg-cyan-950/15 px-3 py-2 text-[9.5px] font-bold text-cyan-300">
            <RotateCcw className="h-3.5 w-3.5" />
            P-3 재순환수는 HRRO 막 입구로 복귀
            <ArrowRight className="h-3.5 w-3.5" />
            막 총 유입 {flowText(membraneFeed)}
          </div>
        </div>
      </div>

      <div className="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-4">
        <div className="rounded border border-slate-800 bg-slate-950/40 p-2">
          <div className="flex items-center gap-1 text-[8.5px] font-bold text-slate-500">
            <Activity className="h-3 w-3" />
            CC 시간
          </div>
          <div className="mt-1 font-mono text-[10px] font-bold text-slate-200">
            {numberText(
              cycle.cc_sequence_duration_min,
              2,
            )}{' '}
            min
          </div>
        </div>

        <div className="rounded border border-slate-800 bg-slate-950/40 p-2">
          <div className="flex items-center gap-1 text-[8.5px] font-bold text-slate-500">
            <Activity className="h-3 w-3" />
            PF 시간
          </div>
          <div className="mt-1 font-mono text-[10px] font-bold text-slate-200">
            {numberText(
              cycle.pf_sequence_duration_min,
              2,
            )}{' '}
            min
          </div>
        </div>

        <div className="rounded border border-slate-800 bg-slate-950/40 p-2">
          <div className="flex items-center gap-1 text-[8.5px] font-bold text-slate-500">
            <Gauge className="h-3 w-3" />
            질량수지
          </div>
          <div
            className={`mt-1 font-mono text-[10px] font-bold ${
              massBalanceOk
                ? 'text-emerald-300'
                : 'text-rose-300'
            }`}
          >
            {massBalanceOk ? '정상' : '오류'}
          </div>
        </div>

        <div className="rounded border border-slate-800 bg-slate-950/40 p-2">
          <div className="flex items-center gap-1 text-[8.5px] font-bold text-slate-500">
            <Waves className="h-3 w-3" />
            완전 사이클
          </div>
          <div className="mt-1 font-mono text-[10px] font-bold text-slate-200">
            {numberText(
              cycle.complete_sequence_duration_min,
              2,
            )}{' '}
            min
          </div>
        </div>
      </div>
    </div>
  );
}
