type PhaseName = 'CC' | 'PF';

type HistoryPoint = {
  time_min?: number;
  recovery_pct?: number;
  pressure_bar?: number;
  tds_mgL?: number;
  permeate_flow_m3h?: number;
  permeate_tds_mgL?: number;
  feed_flow_m3h?: number;
  recirc_flow_m3h?: number;
  concentrate_flow_m3h?: number;
  phase?: string;
};

type PhaseFlowProps = {
  phase: PhaseName;
  feed: number | null;
  product: number | null;
  recycle: number | null;
  membraneFeed: number | null;
  concentrate: number | null;
  drain: number | null;
  pressureStart: number | null;
  pressureEnd: number | null;
  tdsStart: number | null;
  tdsEnd: number | null;
  recoveryStart: number | null;
  recoveryEnd: number | null;
  productTds: number | null;
  valveState: string;
  p3Running: boolean;
  pressureUnit: string;
};

function asNumber(
  value: unknown,
): number | null {
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

function formatNumber(
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

function flowText(
  value: unknown,
): string {
  return `${formatNumber(value)} m³/h/PV`;
}

function percentText(
  value: unknown,
): string {
  return `${formatNumber(value, 1)}%`;
}

function rangeText(
  start: unknown,
  end: unknown,
  unit: string,
  digits = 2,
): string {
  const first = asNumber(start);
  const last = asNumber(end);

  if (first == null && last == null) {
    return '—';
  }

  if (first == null) {
    return `${formatNumber(last, digits)} ${unit}`;
  }

  if (last == null) {
    return `${formatNumber(first, digits)} ${unit}`;
  }

  if (Math.abs(first - last) < 1e-9) {
    return `${formatNumber(first, digits)} ${unit}`;
  }

  return (
    `${formatNumber(first, digits)}`
    + ` → ${formatNumber(last, digits)} ${unit}`
  );
}

function FlowBox({
  title,
  subtitle,
  rows,
  tone = 'slate',
  testId,
}: {
  title: string;
  subtitle?: string;
  rows: Array<{
    label: string;
    value: string;
  }>;
  tone?: 'blue' | 'cyan' | 'emerald' | 'violet' | 'slate';
  testId?: string;
}) {
  const tones = {
    blue: 'border-blue-400 bg-blue-50',
    cyan: 'border-cyan-400 bg-cyan-50',
    emerald: 'border-emerald-500 bg-emerald-50',
    violet: 'border-violet-400 bg-violet-50',
    slate: 'border-slate-400 bg-slate-50',
  };

  return (
    <div
      data-testid={testId}
      className={[
        'min-w-0 border-2 p-2',
        tones[tone],
      ].join(' ')}
    >
      <div className="text-[10px] font-black tracking-wide text-slate-900">
        {title}
      </div>

      {subtitle && (
        <div className="mt-0.5 text-[8px] font-bold text-slate-500">
          {subtitle}
        </div>
      )}

      <div className="mt-1.5 space-y-0.5">
        {rows.map((row) => (
          <div
            key={row.label}
            className="flex items-start justify-between gap-2"
          >
            <span className="text-[8px] font-bold text-slate-500">
              {row.label}
            </span>

            <span className="text-right font-mono text-[8.5px] font-bold tabular-nums text-slate-900">
              {row.value}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

function Arrow({
  direction = 'right',
}: {
  direction?: 'right' | 'down' | 'return';
}) {
  const text =
    direction === 'down'
      ? '↓'
      : direction === 'return'
        ? '↶'
        : '→';

  return (
    <div className="flex items-center justify-center text-[15px] font-black text-slate-700">
      {text}
    </div>
  );
}

function PhaseFlow({
  phase,
  feed,
  product,
  recycle,
  membraneFeed,
  concentrate,
  drain,
  pressureStart,
  pressureEnd,
  tdsStart,
  tdsEnd,
  recoveryStart,
  recoveryEnd,
  productTds,
  valveState,
  p3Running,
  pressureUnit,
}: PhaseFlowProps) {
  const isPF = phase === 'PF';

  return (
    <div
      data-testid={`hrro-report-${phase.toLowerCase()}`}
      className={[
        'print:break-inside-avoid border-2 p-2.5',
        isPF
          ? 'border-cyan-600 bg-cyan-50/30'
          : 'border-blue-700 bg-blue-50/30',
      ].join(' ')}
    >
      <div className="mb-2 flex items-center justify-between gap-3">
        <div>
          <div
            className={[
              'text-[11px] font-black tracking-wide',
              isPF
                ? 'text-cyan-900'
                : 'text-blue-900',
            ].join(' ')}
          >
            {isPF
              ? 'PF 플러시 운전'
              : 'CC 농축 운전'}
          </div>

          <div className="mt-0.5 text-[8px] font-bold text-slate-500">
            {isPF
              ? '부분 배출과 P-3 재순환을 이용한 저농도 원수 치환'
              : 'P-3 재순환과 P-2 승압을 이용한 회분식 농축'}
          </div>
        </div>

        <div className="grid grid-cols-3 gap-1.5">
          <div className="border border-slate-300 bg-white px-2 py-1 text-center">
            <div className="text-[7px] font-bold text-slate-500">
              압력
            </div>
            <div className="font-mono text-[8px] font-bold text-slate-900">
              {rangeText(
                pressureStart,
                pressureEnd,
                pressureUnit,
              )}
            </div>
          </div>

          <div className="border border-slate-300 bg-white px-2 py-1 text-center">
            <div className="text-[7px] font-bold text-slate-500">
              Loop TDS
            </div>
            <div className="font-mono text-[8px] font-bold text-slate-900">
              {rangeText(
                tdsStart,
                tdsEnd,
                'mg/L',
                1,
              )}
            </div>
          </div>

          <div className="border border-slate-300 bg-white px-2 py-1 text-center">
            <div className="text-[7px] font-bold text-slate-500">
              회수율
            </div>
            <div className="font-mono text-[8px] font-bold text-slate-900">
              {rangeText(
                recoveryStart,
                recoveryEnd,
                '%',
                1,
              )}
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-[1fr_22px_1.2fr_22px_1fr] items-center gap-1.5">
        <FlowBox
          title="Feed / P-2"
          subtitle={
            isPF
              ? 'PF 원수 공급'
              : '생산수량 보충'
          }
          tone="blue"
          rows={[
            {
              label: `${phase} Feed`,
              value: flowText(feed),
            },
            {
              label: 'P-2 제어',
              value: isPF
                ? 'VFD 감속'
                : 'VFD 승압',
            },
          ]}
        />

        <Arrow />

        <FlowBox
          title="HRRO Membrane"
          subtitle={
            isPF
              ? '농축수 치환'
              : '회분식 농축'
          }
          tone="cyan"
          rows={[
            {
              label: '막 총 유입',
              value: flowText(membraneFeed),
            },
            {
              label: '농축수 출구',
              value: flowText(concentrate),
            },
          ]}
        />

        <Arrow />

        <FlowBox
          title="Product"
          subtitle="생산수"
          tone="emerald"
          rows={[
            {
              label: '유량',
              value: flowText(product),
            },
            {
              label: 'TDS',
              value:
                `${formatNumber(
                  productTds,
                  2,
                )} mg/L`,
            },
          ]}
        />
      </div>

      <div className="my-1 flex justify-center">
        <Arrow direction="down" />
      </div>

      <div className="grid grid-cols-[1fr_22px_1fr_22px_1fr] items-center gap-1.5">
        <FlowBox
          title="Brine Valve / Drain"
          subtitle={
            isPF
              ? '외부 배출'
              : '외부 배출 없음'
          }
          tone="violet"
          testId={`hrro-report-${phase.toLowerCase()}-drain`}
          rows={[
            {
              label: 'Drain',
              value: flowText(drain),
            },
            {
              label: '밸브 상태',
              value: valveState,
            },
          ]}
        />

        <Arrow direction="return" />

        <FlowBox
          title="Concentrate Header"
          subtitle="막 출구 농축수 분기"
          tone="slate"
          rows={[
            {
              label: '농축수',
              value: flowText(concentrate),
            },
            {
              label: '운전 단계',
              value: phase,
            },
          ]}
        />

        <Arrow direction="return" />

        <FlowBox
          title="P-3 Recycle"
          subtitle="막 입구로 복귀"
          tone="cyan"
          testId={`hrro-report-${phase.toLowerCase()}-recycle`}
          rows={[
            {
              label: '재순환',
              value: flowText(recycle),
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

      <div className="mt-1.5 text-right text-[7.5px] font-bold text-slate-500">
        질량수지: 막 총 유입 = Feed + P-3 Recycle
      </div>
    </div>
  );
}

export function HRROProcessFlowPanel({
  stage,
  unitLabels,
}: {
  stage: any;
  unitLabels: any;
}) {
  const cycle =
    stage?.chemistry?.ccro_cycle;

  if (!cycle) {
    return null;
  }

  const history: HistoryPoint[] =
    Array.isArray(stage?.time_history)
      ? stage.time_history
      : [];

  const ccRows = history.filter(
    (row) =>
      String(row?.phase ?? '').toUpperCase()
      === 'CC',
  );

  const pfRows = history.filter(
    (row) =>
      String(row?.phase ?? '').toUpperCase()
      === 'PF',
  );

  const ccFirst = ccRows[0] ?? {};
  const ccLast =
    ccRows[ccRows.length - 1] ?? ccFirst;

  const pfFirst = pfRows[0] ?? {};
  const pfLast =
    pfRows[pfRows.length - 1] ?? pfFirst;

  const ccFeed = firstNumber(
    ccFirst.feed_flow_m3h,
    cycle.cc_permeate_flow_m3h_per_pv,
    stage?.Qp,
  );

  const ccProduct = firstNumber(
    ccFirst.permeate_flow_m3h,
    cycle.cc_permeate_flow_m3h_per_pv,
    cycle.average_permeate_flow_m3h,
    stage?.Qp,
  );

  const ccRecycle = firstNumber(
    ccFirst.recirc_flow_m3h,
    cycle.cc_concentrate_flow_m3h_per_pv,
  );

  const ccMembraneFeed =
    ccFeed != null && ccRecycle != null
      ? ccFeed + ccRecycle
      : firstNumber(
          cycle.cc_net_feed_flow_m3h_per_pv,
        );

  const ccConcentrate = firstNumber(
    ccFirst.concentrate_flow_m3h,
    cycle.cc_concentrate_flow_m3h_per_pv,
  );

  const pfFeed = firstNumber(
    cycle.pf_feed_flow_m3h_per_pv,
    pfFirst.feed_flow_m3h,
  );

  const pfProduct = firstNumber(
    cycle.pf_permeate_flow_m3h_per_pv,
    pfFirst.permeate_flow_m3h,
    cycle.average_permeate_flow_m3h,
    stage?.Qp,
  );

  const pfRecycle = firstNumber(
    cycle.pf_p3_recycle_flow_m3h_per_pv,
    pfFirst.recirc_flow_m3h,
  );

  const pfMembraneFeed = firstNumber(
    cycle.pf_membrane_total_feed_flow_m3h_per_pv,
    pfFeed != null && pfRecycle != null
      ? pfFeed + pfRecycle
      : null,
  );

  const pfConcentrate = firstNumber(
    cycle.pf_membrane_concentrate_out_m3h_per_pv,
    cycle.pf_concentrate_flow_m3h_per_pv,
    pfFirst.concentrate_flow_m3h,
  );

  const pfDrain = firstNumber(
    cycle.pf_external_drain_setpoint_m3h_per_pv,
    cycle.pf_drain_setpoint_m3h_per_pv,
  );

  const mode = String(
    cycle.pf_mode ?? '',
  );

  const modeLabel =
    mode === 'smart_partial_drain'
      ? 'Smart Partial Drain'
      : mode === 'field_optimized_low_fr'
        ? 'Field Optimized Low-FR'
        : 'True Plug-Flow';

  const crossflowOk =
    cycle.crossflow_ok !== false;

  const p3CapacityOk =
    cycle.p3_recycle_capacity_ok !== false;

  const massBalanceOk =
    cycle.partial_drain_mass_balance_ok !== false;

  const slowFlush =
    cycle.slow_flush_or_poor_salt_displacement
    === true;

  const healthy =
    crossflowOk
    && p3CapacityOk
    && massBalanceOk
    && !slowFlush;

  const pressureUnit =
    unitLabels?.pressure ?? 'bar';

  return (
    <div
      data-testid="hrro-report-process-flow"
      className="w-full space-y-2 print:break-inside-avoid"
    >
      <div className="grid grid-cols-6 border-2 border-slate-500">
        <div className="col-span-2 border-r border-slate-300 bg-slate-100 px-2.5 py-2">
          <div className="text-[8px] font-bold text-slate-500">
            PF 운전 방식
          </div>
          <div className="mt-0.5 text-[10px] font-black text-slate-900">
            {modeLabel}
          </div>
        </div>

        <div className="border-r border-slate-300 bg-white px-2.5 py-2">
          <div className="text-[8px] font-bold text-slate-500">
            Feed Ratio
          </div>
          <div className="mt-0.5 font-mono text-[10px] font-black text-slate-900">
            {percentText(
              cycle.pf_feed_ratio_pct,
            )}
          </div>
        </div>

        <div className="border-r border-slate-300 bg-white px-2.5 py-2">
          <div className="text-[8px] font-bold text-slate-500">
            CC 시간
          </div>
          <div className="mt-0.5 font-mono text-[10px] font-black text-slate-900">
            {formatNumber(
              cycle.cc_sequence_duration_min,
              2,
            )} min
          </div>
        </div>

        <div className="border-r border-slate-300 bg-white px-2.5 py-2">
          <div className="text-[8px] font-bold text-slate-500">
            PF 시간
          </div>
          <div className="mt-0.5 font-mono text-[10px] font-black text-slate-900">
            {formatNumber(
              cycle.pf_sequence_duration_min,
              2,
            )} min
          </div>
        </div>

        <div
          className={[
            'px-2.5 py-2',
            healthy
              ? 'bg-emerald-50'
              : 'bg-amber-50',
          ].join(' ')}
        >
          <div className="text-[8px] font-bold text-slate-500">
            운전 판정
          </div>
          <div
            className={[
              'mt-0.5 text-[10px] font-black',
              healthy
                ? 'text-emerald-800'
                : 'text-amber-800',
            ].join(' ')}
          >
            {healthy
              ? '정상'
              : '경고 확인'}
          </div>
        </div>
      </div>

      <PhaseFlow
        phase="CC"
        feed={ccFeed}
        product={ccProduct}
        recycle={ccRecycle}
        membraneFeed={ccMembraneFeed}
        concentrate={ccConcentrate}
        drain={0}
        pressureStart={firstNumber(
          ccFirst.pressure_bar,
          stage?.p_in_bar,
        )}
        pressureEnd={firstNumber(
          ccLast.pressure_bar,
          stage?.p_in_bar,
        )}
        tdsStart={firstNumber(
          ccFirst.tds_mgL,
          stage?.Cf,
        )}
        tdsEnd={firstNumber(
          ccLast.tds_mgL,
          stage?.Cc,
        )}
        recoveryStart={firstNumber(
          ccFirst.recovery_pct,
          0,
        )}
        recoveryEnd={firstNumber(
          ccLast.recovery_pct,
          stage?.recovery_pct,
        )}
        productTds={firstNumber(
          ccLast.permeate_tds_mgL,
          stage?.Cp,
        )}
        valveState="Recycle"
        p3Running={(ccRecycle ?? 0) > 0}
        pressureUnit={pressureUnit}
      />

      <PhaseFlow
        phase="PF"
        feed={pfFeed}
        product={pfProduct}
        recycle={pfRecycle}
        membraneFeed={pfMembraneFeed}
        concentrate={pfConcentrate}
        drain={pfDrain}
        pressureStart={firstNumber(
          pfFirst.pressure_bar,
          stage?.p_in_bar,
        )}
        pressureEnd={firstNumber(
          pfLast.pressure_bar,
          stage?.p_in_bar,
        )}
        tdsStart={firstNumber(
          pfFirst.tds_mgL,
          stage?.Cc,
        )}
        tdsEnd={firstNumber(
          pfLast.tds_mgL,
          stage?.Cc,
        )}
        recoveryStart={firstNumber(
          pfFirst.recovery_pct,
          stage?.recovery_pct,
        )}
        recoveryEnd={firstNumber(
          pfLast.recovery_pct,
          stage?.recovery_pct,
        )}
        productTds={firstNumber(
          pfLast.permeate_tds_mgL,
          stage?.Cp,
        )}
        valveState={
          cycle.brine_valve_mode
          === 'partial_pid'
            ? 'Partial PID'
            : cycle.brine_valve_mode
              ?? '—'
        }
        p3Running={(pfRecycle ?? 0) > 0}
        pressureUnit={pressureUnit}
      />

      <div className="text-[7.5px] font-medium text-slate-500">
        * 표시값은 현재 HRRO 계산 결과의 CC/PF 시계열 및
        ccro_cycle 질량수지 결과를 사용합니다.
      </div>
    </div>
  );
}
