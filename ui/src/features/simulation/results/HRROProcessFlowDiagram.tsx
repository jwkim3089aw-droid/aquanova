import {
  useMemo,
  useState,
} from 'react';

import {
  Activity,
  AlertTriangle,
  ArrowDown,
  ArrowRight,
  CheckCircle2,
  Clock3,
  Gauge,
  RotateCcw,
  Waves,
} from 'lucide-react';

type PhaseName = 'CC' | 'PF';

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

type HistoryPoint = {
  time_min?: number;
  recovery_pct?: number;
  pressure_bar?: number;
  tds_mgL?: number;
  flux_lmh?: number;
  ndp_bar?: number;
  permeate_flow_m3h?: number;
  permeate_tds_mgL?: number;
  specific_energy_kwh_m3?: number;
  phase?: string;
  feed_flow_m3h?: number;
  recirc_flow_m3h?: number;
  concentrate_flow_m3h?: number;
};

const ACCENTS: Record<Accent, string> = {
  blue: 'border-blue-500/40 bg-blue-950/20',
  cyan: 'border-cyan-500/40 bg-cyan-950/20',
  emerald: 'border-emerald-500/40 bg-emerald-950/20',
  amber: 'border-amber-500/40 bg-amber-950/20',
  violet: 'border-violet-500/40 bg-violet-950/20',
  slate: 'border-slate-600/60 bg-slate-900/50',
};

function asNumber(value: unknown): number | null {
  if (
    value === null ||
    value === undefined ||
    value === ''
  ) {
    return null;
  }

  const parsed = Number(value);

  return Number.isFinite(parsed)
    ? parsed
    : null;
}

function firstNumber(
  ...values: unknown[]
): number | null {
  for (const value of values) {
    const parsed = asNumber(value);

    if (parsed != null) {
      return parsed;
    }
  }

  return null;
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

function PhaseButton({
  phase,
  active,
  available,
  onClick,
}: {
  phase: PhaseName;
  active: boolean;
  available: boolean;
  onClick: () => void;
}) {
  const label =
    phase === 'CC'
      ? 'CC 농축'
      : 'PF 플러시';

  return (
    <button
      type="button"
      data-testid={`hrro-phase-${phase.toLowerCase()}`}
      disabled={!available}
      onClick={onClick}
      className={[
        'rounded-md border px-2.5 py-1.5 text-[9.5px] font-bold transition-colors',
        active
          ? 'border-cyan-400/60 bg-cyan-950/70 text-cyan-200'
          : 'border-slate-700 bg-slate-900 text-slate-400 hover:border-slate-600',
        available
          ? ''
          : 'cursor-not-allowed opacity-40',
      ].join(' ')}
    >
      {label}
    </button>
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

  const history = useMemo<HistoryPoint[]>(
    () =>
      Array.isArray(stage?.time_history)
        ? stage.time_history
        : [],
    [stage?.time_history],
  );

  const phaseRows = useMemo(
    () => ({
      CC: history.filter(
        (row) =>
          String(row?.phase ?? '').toUpperCase()
          === 'CC',
      ),
      PF: history.filter(
        (row) =>
          String(row?.phase ?? '').toUpperCase()
          === 'PF',
      ),
    }),
    [history],
  );

  const [selectedPhase, setSelectedPhase] =
    useState<PhaseName>('PF');

  const [sampleIndex, setSampleIndex] =
    useState(0);

  if (!cycle) {
    return null;
  }

  const effectivePhase: PhaseName =
    phaseRows[selectedPhase].length > 0
      ? selectedPhase
      : phaseRows.PF.length > 0
        ? 'PF'
        : 'CC';

  const selectedRows =
    phaseRows[effectivePhase];

  const safeSampleIndex =
    selectedRows.length > 0
      ? Math.min(
          sampleIndex,
          selectedRows.length - 1,
        )
      : 0;

  const point =
    selectedRows[safeSampleIndex] ?? {};

  const isPF = effectivePhase === 'PF';

  const mode = String(
    cycle.pf_mode ?? 'wave_true_plug_flow',
  );

  const modeLabel =
    mode === 'wave_true_plug_flow'
      ? '고유량 PF 운전'
      : mode === 'field_optimized_low_fr'
        ? '저유량 PF 운전'
        : '자동 PF 운전';

  const smartMode =
    mode === 'smart_partial_drain' ||
    mode === 'field_optimized_low_fr';

  const crossflowOk =
    cycle.crossflow_ok !== false;

  const capacityOk =
    cycle.p3_recycle_capacity_ok !== false;

  const massBalanceOk =
    cycle.partial_drain_mass_balance_ok !== false;

  const slowFlush =
    cycle.slow_flush_or_poor_salt_displacement
    === true;

  const healthy =
    crossflowOk &&
    capacityOk &&
    massBalanceOk &&
    !slowFlush;

  const phaseFeed = firstNumber(
    point.feed_flow_m3h,
    isPF
      ? cycle.pf_feed_flow_m3h_per_pv
      : cycle.cc_permeate_flow_m3h_per_pv,
  );

  const phaseProduct = firstNumber(
    point.permeate_flow_m3h,
    isPF
      ? cycle.pf_permeate_flow_m3h_per_pv
      : cycle.cc_permeate_flow_m3h_per_pv,
    cycle.average_permeate_flow_m3h,
    stage?.Qp,
  );

  const phaseRecycle = firstNumber(
    point.recirc_flow_m3h,
    isPF
      ? cycle.pf_p3_recycle_flow_m3h_per_pv
      : cycle.cc_concentrate_flow_m3h_per_pv,
  );

  const calculatedMembraneFeed =
    phaseFeed != null &&
    phaseRecycle != null
      ? phaseFeed + phaseRecycle
      : null;

  const phaseMembraneFeed = firstNumber(
    calculatedMembraneFeed,
    isPF
      ? cycle.pf_membrane_total_feed_flow_m3h_per_pv
      : cycle.cc_net_feed_flow_m3h_per_pv,
  );

  const phaseConcentrate = firstNumber(
    point.concentrate_flow_m3h,
    isPF
      ? cycle.pf_membrane_concentrate_out_m3h_per_pv
      : cycle.cc_concentrate_flow_m3h_per_pv,
  );

  const phaseDrain = isPF
    ? firstNumber(
        cycle.pf_external_drain_setpoint_m3h_per_pv,
        cycle.pf_drain_setpoint_m3h_per_pv,
      )
    : 0;

  const phasePressure = firstNumber(
    point.pressure_bar,
    stage?.p_in_bar,
  );

  const phaseTds = firstNumber(
    point.tds_mgL,
    stage?.Cc,
  );

  const phaseProductTds = firstNumber(
    point.permeate_tds_mgL,
    stage?.Cp,
  );

  const phaseRecovery = firstNumber(
    point.recovery_pct,
    stage?.recovery_pct,
  );

  const phaseTime = firstNumber(
    point.time_min,
    0,
  );

  const drainFraction =
    isPF
      ? asNumber(
          cycle.pf_drain_fraction_of_concentrate,
        )
      : 0;

  const p3Running =
    (phaseRecycle ?? 0) > 0;

  const phaseDescription =
    isPF
      ? 'P-3 운전 · 부분 배출 · 저농도 원수 치환'
      : 'P-3 재순환 · 농축 진행 · P-2 압력 상승';

  const valveDescription =
    isPF
      ? smartMode
        ? '자동 조절'
        : '완전 개방'
      : 'CC 재순환';

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
            FR {numberText(
              cycle.pf_feed_ratio_pct,
              0,
            )}%
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

            {healthy
              ? '운전 조건 정상'
              : '설계 경고 확인'}
          </span>
        </div>
      </div>

      <div className="mb-3 rounded-lg border border-slate-800 bg-slate-950/50 p-2.5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-1.5">
            <PhaseButton
              phase="CC"
              active={effectivePhase === 'CC'}
              available={phaseRows.CC.length > 0}
              onClick={() => {
                setSelectedPhase('CC');
                setSampleIndex(0);
              }}
            />

            <PhaseButton
              phase="PF"
              active={effectivePhase === 'PF'}
              available={phaseRows.PF.length > 0}
              onClick={() => {
                setSelectedPhase('PF');
                setSampleIndex(0);
              }}
            />
          </div>

          <div
            data-testid="hrro-phase-status"
            className="flex items-center gap-1.5 rounded border border-slate-700 bg-slate-900 px-2.5 py-1.5 text-[9px] font-bold text-slate-300"
          >
            <Clock3 className="h-3 w-3 text-cyan-400" />
            현재 보기: {effectivePhase}
            <span className="text-slate-600">·</span>
            {numberText(phaseTime, 2)} min
          </div>
        </div>

        <div className="mt-2 text-[9px] font-medium text-slate-500">
          {phaseDescription}
        </div>

        {selectedRows.length > 1 && (
          <div className="mt-2 grid grid-cols-[1fr_auto] items-center gap-3">
            <input
              data-testid="hrro-phase-slider"
              type="range"
              min={0}
              max={selectedRows.length - 1}
              step={1}
              value={safeSampleIndex}
              onChange={(event) =>
                setSampleIndex(
                  Number(event.target.value),
                )
              }
              className="h-1.5 w-full cursor-pointer accent-cyan-500"
            />

            <span className="min-w-[55px] text-right font-mono text-[8.5px] font-bold tabular-nums text-slate-500">
              {safeSampleIndex + 1}
              {' / '}
              {selectedRows.length}
            </span>
          </div>
        )}
      </div>

      <div className="overflow-x-auto rounded-xl border border-slate-800 bg-slate-950/45 p-3">
        <div className="min-w-[720px]">
          <div className="grid grid-cols-[1fr_38px_1.3fr_38px_1fr] items-center gap-2">
            <FlowCard
              title="Feed / P-2"
              subtitle={
                isPF
                  ? 'PF 원수 공급 · VFD/PID 감속'
                  : 'CC 생산수 보충 · VFD/PID 승압'
              }
              accent="blue"
              testId="hrro-flow-feed"
              rows={[
                {
                  label: `${effectivePhase} Feed`,
                  value: flowText(phaseFeed),
                },
                {
                  label: '막 입구 압력',
                  value:
                    `${numberText(
                      phasePressure,
                      2,
                    )} ${unitPress}`,
                },
                {
                  label: '시점',
                  value:
                    `${numberText(
                      phaseTime,
                      2,
                    )} min`,
                },
              ]}
            />

            <div className="flex justify-center text-blue-400">
              <ArrowRight className="h-5 w-5" />
            </div>

            <FlowCard
              title="HRRO Membrane"
              subtitle={
                isPF
                  ? '저농도 원수로 농축수 치환'
                  : '재순환 농축 운전'
              }
              accent="cyan"
              testId="hrro-flow-membrane"
              rows={[
                {
                  label: '막 총 유입',
                  value: flowText(
                    phaseMembraneFeed,
                  ),
                },
                {
                  label: '농축수 출구',
                  value: flowText(
                    phaseConcentrate,
                  ),
                },
                {
                  label: 'Loop TDS',
                  value:
                    `${numberText(
                      phaseTds,
                      1,
                    )} mg/L`,
                },
                {
                  label: '회수율',
                  value: percentText(
                    phaseRecovery,
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
                  value: flowText(
                    phaseProduct,
                  ),
                },
                {
                  label: '생산수 TDS',
                  value:
                    `${numberText(
                      phaseProductTds,
                      2,
                    )} mg/L`,
                },
                {
                  label: '운전 단계',
                  value: effectivePhase,
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
                isPF
                  ? '외부 배출 및 염 치환'
                  : 'CC 중 외부 배출 없음'
              }
              accent={
                slowFlush && isPF
                  ? 'amber'
                  : 'violet'
              }
              testId="hrro-flow-drain"
              rows={[
                {
                  label: '외부 배출',
                  value: flowText(phaseDrain),
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
                  label: '밸브 상태',
                  value: valveDescription,
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
                  value: flowText(
                    phaseConcentrate,
                  ),
                },
                {
                  label: 'Crossflow',
                  value: crossflowOk
                    ? '정상'
                    : '부족',
                },
                {
                  label: 'Phase',
                  value: effectivePhase,
                },
              ]}
            />

            <FlowCard
              title="P-3 Recycle"
              subtitle={
                p3Running
                  ? `${effectivePhase} 중 운전`
                  : `${effectivePhase} 중 정지`
              }
              accent={
                capacityOk
                  ? 'cyan'
                  : 'amber'
              }
              testId="hrro-flow-recycle"
              rows={[
                {
                  label: '재순환 유량',
                  value: flowText(
                    phaseRecycle,
                  ),
                },
                {
                  label: '설치 용량',
                  value: flowText(
                    cycle.p3_recycle_capacity_m3h_per_pv,
                  ),
                },
                {
                  label: 'P-3 상태',
                  value: p3Running
                    ? 'ON'
                    : 'OFF',
                },
              ]}
            />
          </div>

          <div className="mt-3 flex items-center justify-end gap-2 rounded-lg border border-dashed border-cyan-700/40 bg-cyan-950/15 px-3 py-2 text-[9.5px] font-bold text-cyan-300">
            <RotateCcw className="h-3.5 w-3.5" />
            P-3 재순환수는 HRRO 막 입구로 복귀
            <ArrowRight className="h-3.5 w-3.5" />
            막 총 유입 {flowText(
              phaseMembraneFeed,
            )}
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
            {massBalanceOk
              ? '정상'
              : '오류'}
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
