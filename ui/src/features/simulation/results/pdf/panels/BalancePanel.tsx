// ui/src/features/simulation/results/pdf/panels/BalancePanel.tsx
import React from 'react';
import { fmt } from '../utils';
import { UnitLabels } from '../types';

export function BalancePanel({
  kpi,
  u,
}: {
  feed?: any;
  perm?: any;
  brine?: any;
  kpi?: any;
  u: UnitLabels;
}) {
  // 백엔드가 완벽하게 계산해서 보내준 mass_balance 데이터를 100% 신뢰하여 그대로 출력합니다.
  const mb = kpi?.mass_balance;

  const flowErrPct = mb?.flow_error_pct;
  const flowErr = mb?.flow_error_m3h;

  const saltErrPct = mb?.salt_error_pct;
  const saltErr = mb?.salt_error_kgh;

  const rejectionPct = mb?.system_rejection_pct;

  // 에러율이 0.1% 미만이면 BAL OK 처리
  const isBalanced = mb?.is_balanced ?? Math.abs(flowErrPct || 0) < 0.1;

  const statusText = isBalanced ? '정상 (BAL OK)' : '경고 (BAL WARN)';
  const statusColor = isBalanced
    ? 'text-emerald-700 bg-emerald-50 border-emerald-400'
    : 'text-rose-600 bg-rose-50 border-rose-300';

  // 💡 명품 Slate 테마 (이전 패널들과 100% 동일한 서식)
  const tableClass =
    'w-full border-collapse border-2 border-slate-500 shadow-sm';
  const thClass =
    'py-1.5 px-3 text-[11px] font-bold text-slate-800 border border-slate-400 bg-slate-200 text-center w-1/3';
  const tdClass =
    'py-1.5 px-3 text-[12px] font-mono font-bold text-slate-900 border border-slate-300 bg-white text-center tabular-nums';
  const tdSubClass =
    'py-1 px-3 text-[10px] font-mono text-slate-500 border border-slate-300 bg-slate-50 text-center';

  return (
    <div className="w-full print:break-inside-avoid">
      <div className="flex items-center gap-3 mb-2">
        <span
          className={`text-[10px] font-bold px-2 py-0.5 border uppercase tracking-wider rounded-sm ${statusColor}`}
        >
          {statusText}
        </span>
        <div className="text-[10px] font-semibold text-slate-700">
          유량 검증 (Flow closure): Qf = (Qp+Qb){' '}
          <span className="text-slate-300 mx-1">|</span> 염분 검증 (Salt
          closure): Sf = (Sp+Sb)
        </div>
      </div>

      <table className={tableClass}>
        <thead>
          <tr>
            <th className={thClass}>유량 오차 (Flow Error)</th>
            <th className={thClass}>염분 오차 (Salt Error)</th>
            <th className={thClass}>시스템 염분 제거율 (Rejection)</th>
          </tr>
        </thead>
        <tbody>
          {/* 메인 퍼센트(%) 값 행 */}
          <tr>
            <td className={tdClass}>
              {flowErrPct == null ? '-' : `${Math.abs(flowErrPct).toFixed(2)}%`}
            </td>
            <td className={tdClass}>
              {saltErrPct == null ? '-' : `${Math.abs(saltErrPct).toFixed(2)}%`}
            </td>
            <td className={tdClass}>
              {rejectionPct == null ? '-' : `${rejectionPct.toFixed(2)}%`}
            </td>
          </tr>
          {/* 하단 상세 수치(절대량) 및 공식 행 */}
          <tr>
            <td className={tdSubClass}>
              Δ {flowErr == null ? '-' : fmt(Math.abs(flowErr))} {u.flow}
            </td>
            <td className={tdSubClass}>
              Δ {saltErr == null ? '-' : fmt(Math.abs(saltErr))} kg/h
            </td>
            <td className={tdSubClass}>1 − (Cp/Cf)</td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}
