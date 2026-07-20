import type {
  PrecisionCorrection,
  PrecisionReport,
} from '@/api/types';

function metricLabel(
  metric: string | null | undefined,
): string {
  const labels: Record<string, string> = {
    feed_pressure: '유입 압력',
    product_tds: '생산수 TDS',
    specific_energy: '비에너지',
    final_concentrate_tds: '최종 농축수 TDS',
    recovery: '회수율',
  };

  return labels[String(metric ?? '')] ??
    String(metric ?? '알 수 없는 항목');
}

function numberText(
  value: number | null | undefined,
): string {
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    return '-';
  }

  return value.toLocaleString(undefined, {
    maximumFractionDigits: 6,
  });
}

function isShadow(
  correction: PrecisionCorrection,
): boolean {
  return String(correction.status ?? '')
    .toLowerCase()
    .includes('shadow');
}

export function PrecisionReportPanel({
  report,
}: {
  report?: PrecisionReport | null;
}) {
  const rows = report?.corrections ?? [];
  const shadowCount = rows.filter(isShadow).length;
  const enabled = Boolean(report?.enabled);

  if (!report || !enabled) {
    return (
      <div
        data-testid="precision-report-panel"
        data-precision-mode="raw"
        className="rounded-xl border border-slate-700/60 bg-slate-900/40 p-3.5 shadow-lg"
      >
        <div className="flex items-center justify-between gap-3">
          <div>
            <div className="text-[11px] font-bold text-slate-300">
              계산 모드
            </div>
            <div className="mt-1 text-[10px] text-slate-500">
              보정 레이어를 적용하지 않은 AquaNova 물리 계산값입니다.
            </div>
          </div>

          <span className="rounded-full border border-slate-600 bg-slate-800 px-2.5 py-1 text-[10px] font-bold text-slate-300">
            기본 계산
          </span>
        </div>
      </div>
    );
  }

  return (
    <div
      data-testid="precision-report-panel"
      data-precision-mode="precision"
      className="rounded-xl border border-emerald-500/30 bg-emerald-950/20 p-3.5 shadow-lg"
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-[11px] font-bold text-emerald-300">
            AquaNova 정밀 계산
          </div>

          <div className="mt-1 text-[10px] text-emerald-200/70">
            검증된 WAVE 비교 조건에 해당하는 항목만 보정했습니다.
          </div>
        </div>

        <span className="rounded-full border border-emerald-500/40 bg-emerald-900/40 px-2.5 py-1 text-[10px] font-bold text-emerald-200">
          정밀 모드
        </span>
      </div>

      <div className="mt-3 grid grid-cols-3 gap-2">
        <div className="rounded border border-emerald-800/50 bg-slate-950/30 p-2">
          <div className="text-[9px] text-slate-500">
            적용
          </div>
          <div
            data-testid="precision-applied-count"
            className="mt-0.5 font-mono text-sm font-bold text-emerald-300"
          >
            {report.applied_count ?? 0}
          </div>
        </div>

        <div className="rounded border border-amber-800/40 bg-slate-950/30 p-2">
          <div className="text-[9px] text-slate-500">
            검증 중
          </div>
          <div
            data-testid="precision-shadow-count"
            className="mt-0.5 font-mono text-sm font-bold text-amber-300"
          >
            {shadowCount}
          </div>
        </div>

        <div className="rounded border border-slate-700 bg-slate-950/30 p-2">
          <div className="text-[9px] text-slate-500">
            미적용
          </div>
          <div className="mt-0.5 font-mono text-sm font-bold text-slate-300">
            {report.skipped_count ?? 0}
          </div>
        </div>
      </div>

      {rows.length > 0 && (
        <div className="mt-3 space-y-1.5">
          {rows.map((row, index) => {
            const shadow = isShadow(row);
            const applied =
              String(row.status ?? '').toLowerCase() ===
              'applied';

            return (
              <div
                key={`${row.metric ?? 'metric'}-${index}`}
                data-testid={`precision-correction-${row.metric ?? index}`}
                className="flex items-center justify-between gap-3 rounded border border-slate-700/60 bg-slate-950/30 px-2.5 py-2"
              >
                <div className="min-w-0">
                  <div className="truncate text-[10px] font-bold text-slate-300">
                    {metricLabel(row.metric)}
                  </div>

                  <div className="mt-0.5 font-mono text-[9px] text-slate-500">
                    {shadow
                      ? `${numberText(row.raw_value)} · 공개값 유지`
                      : `${numberText(row.raw_value)} → ${numberText(
                          row.corrected_value,
                        )}`}
                  </div>
                </div>

                <span
                  className={
                    shadow
                      ? 'text-[9px] font-bold text-amber-300'
                      : applied
                        ? 'text-[9px] font-bold text-emerald-300'
                        : 'text-[9px] font-bold text-slate-500'
                  }
                >
                  {shadow
                    ? 'SHADOW'
                    : applied
                      ? 'APPLIED'
                      : 'SKIPPED'}
                </span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
