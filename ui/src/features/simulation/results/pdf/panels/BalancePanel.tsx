// ui/src/features/simulation/results/pdf/panels/BalancePanel.tsx
import React from 'react';
import { Badge } from '../components';
import { fmt, pickNumber } from '../utils';
import { UnitLabels } from '../types';

export function BalancePanel({
  feed,
  perm,
  brine,
  u,
}: {
  feed: any;
  perm: any;
  brine: any;
  u: UnitLabels;
}) {
  const Qf = pickNumber(feed?.flow_m3h ?? feed?.Q_m3h ?? feed?.Q);
  const Qp = pickNumber(perm?.flow_m3h ?? perm?.Q_m3h ?? perm?.Q);
  const Qb = pickNumber(brine?.flow_m3h ?? brine?.Q_m3h ?? brine?.Q);

  const Cf = pickNumber(feed?.tds_mgL ?? feed?.tds ?? feed?.TDS);
  const Cp = pickNumber(perm?.tds_mgL ?? perm?.tds ?? perm?.TDS);
  const Cb = pickNumber(brine?.tds_mgL ?? brine?.tds ?? brine?.TDS);

  const flowOk = [Qf, Qp, Qb].every((x) => x != null);
  const saltOk = flowOk && [Cf, Cp, Cb].every((x) => x != null);

  const flowErr = flowOk
    ? (Qf as number) - ((Qp as number) + (Qb as number))
    : null;
  const flowErrPct =
    flowOk && Qf ? ((flowErr as number) / (Qf as number)) * 100 : null;

  // mg/L * m3/h * 1000 L/m3 => mg/h => /1e6 => kg/h
  const Sf = saltOk ? ((Qf as number) * (Cf as number) * 1000) / 1e6 : null;
  const Sp = saltOk ? ((Qp as number) * (Cp as number) * 1000) / 1e6 : null;
  const Sb = saltOk ? ((Qb as number) * (Cb as number) * 1000) / 1e6 : null;

  const saltErr = saltOk
    ? (Sf as number) - ((Sp as number) + (Sb as number))
    : null;
  const saltErrPct =
    saltOk && Sf ? ((saltErr as number) / (Sf as number)) * 100 : null;

  const rejectionPct =
    saltOk && Cf && Cf > 0 ? (1 - (Cp as number) / (Cf as number)) * 100 : null;

  const tone =
    flowErrPct != null && Math.abs(flowErrPct) > 1
      ? 'rose'
      : flowErrPct != null && Math.abs(flowErrPct) > 0.2
        ? 'amber'
        : 'emerald';

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

      <div className="text-[10px] text-slate-500">
        * Wave 보고서에서 “밸런스/품질 신뢰도”를 주는 핵심 블록을 AquaNova
        스트림 값으로 재구성했습니다.
      </div>
    </div>
  );
}
