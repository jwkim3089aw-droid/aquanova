// ui/src/features/simulation/results/pdf/panels/BalancePanel.tsx
import React from 'react';
import { Badge } from '../components';
import { fmt, pickNumber } from '../utils';
import { UnitLabels } from '../types';

export function BalancePanel({
  feed,
  perm,
  brine,
  kpi, // ✅ 새로 추가: 백엔드에서 넘겨주는 kpi 객체
  u,
}: {
  feed?: any;
  perm?: any;
  brine?: any;
  kpi?: any;
  u: UnitLabels;
}) {
  // ✅ 1. 백엔드 데이터 최우선 사용 (방금 추가한 mass_balance)
  const mb = kpi?.mass_balance;

  // 2. 백엔드 데이터가 없을 경우를 대비한 Fallback (이전 로직)
  const Qf = pickNumber(feed?.flow_m3h ?? feed?.Q_m3h ?? feed?.Q);
  const Qp = pickNumber(perm?.flow_m3h ?? perm?.Q_m3h ?? perm?.Q);
  const Qb = pickNumber(brine?.flow_m3h ?? brine?.Q_m3h ?? brine?.Q);

  const Cf = pickNumber(feed?.tds_mgL ?? feed?.tds ?? feed?.TDS);
  const Cp = pickNumber(perm?.tds_mgL ?? perm?.tds ?? perm?.TDS);
  const Cb = pickNumber(brine?.tds_mgL ?? brine?.tds ?? brine?.TDS);

  const flowOk = [Qf, Qp, Qb].every((x) => x != null);
  const saltOk = flowOk && [Cf, Cp, Cb].every((x) => x != null);

  const flowErrPct =
    mb?.flow_error_pct ??
    (flowOk && Qf
      ? (((Qf as number) - ((Qp as number) + (Qb as number))) /
          (Qf as number)) *
        100
      : null);
  const flowErr =
    mb?.flow_error_m3h ??
    (flowOk ? (Qf as number) - ((Qp as number) + (Qb as number)) : null);

  const Sf = saltOk ? ((Qf as number) * (Cf as number) * 1000) / 1e6 : null;
  const Sp = saltOk ? ((Qp as number) * (Cp as number) * 1000) / 1e6 : null;
  const Sb = saltOk ? ((Qb as number) * (Cb as number) * 1000) / 1e6 : null;

  const saltErrPct =
    mb?.salt_error_pct ??
    (saltOk && Sf
      ? (((Sf as number) - ((Sp as number) + (Sb as number))) /
          (Sf as number)) *
        100
      : null);
  const saltErr =
    mb?.salt_error_kgh ??
    (saltOk ? (Sf as number) - ((Sp as number) + (Sb as number)) : null);

  const rejectionPct =
    mb?.system_rejection_pct ??
    (saltOk && Cf && Cf > 0
      ? (1 - (Cp as number) / (Cf as number)) * 100
      : null);

  const isBalanced =
    mb?.is_balanced ??
    (flowErrPct != null &&
      Math.abs(flowErrPct) < 1 &&
      saltErrPct != null &&
      Math.abs(saltErrPct) < 5);

  const tone = isBalanced
    ? 'emerald'
    : flowErrPct != null && Math.abs(flowErrPct) > 1
      ? 'rose'
      : 'amber';

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <Badge
          text={
            tone === 'emerald'
              ? 'BAL OK'
              : tone === 'amber'
                ? 'BAL WARN'
                : 'BAL FAIL'
          }
          tone={tone as any}
        />
        <div className="text-[10px] text-slate-500">
          Flow closure: Qf − (Qp+Qb), Salt closure: Sf − (Sp+Sb)
        </div>
      </div>

      <div className="grid grid-cols-3 gap-2">
        <div className="rounded-xl border border-slate-200 bg-white p-3">
          <div className="text-[10px] font-extrabold text-slate-500 uppercase tracking-widest">
            Flow closure
          </div>
          <div className="mt-1 font-mono text-base font-black text-slate-900">
            {flowErrPct == null ? '-' : `${flowErrPct.toFixed(2)} %`}
          </div>
          <div className="text-[10px] text-slate-500">
            err={flowErr == null ? '-' : fmt(flowErr)} {u.flow}
          </div>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-3">
          <div className="text-[10px] font-extrabold text-slate-500 uppercase tracking-widest">
            Salt closure
          </div>
          <div className="mt-1 font-mono text-base font-black text-slate-900">
            {saltErrPct == null ? '-' : `${saltErrPct.toFixed(2)} %`}
          </div>
          <div className="text-[10px] text-slate-500">
            err={saltErr == null ? '-' : fmt(saltErr)} kg/h
          </div>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-3">
          <div className="text-[10px] font-extrabold text-slate-500 uppercase tracking-widest">
            Rejection
          </div>
          <div className="mt-1 font-mono text-base font-black text-slate-900">
            {rejectionPct == null ? '-' : `${rejectionPct.toFixed(2)} %`}
          </div>
          <div className="text-[10px] text-slate-500">1 − Cp/Cf</div>
        </div>
      </div>
    </div>
  );
}
