// ui/src/features/simulation/results/pdf/components/tables/ViolationsTable.tsx
import React from 'react';
import { THEME } from '../../theme';
import { safeArr } from '../../utils';

export function ViolationsTable({
  violations,
  maxRows = 20,
}: {
  violations: any[];
  maxRows?: number;
}) {
  const rows = safeArr(violations);
  if (!rows.length) {
    return <div className="text-[10px] text-slate-500">No violations.</div>;
  }

  const slice = rows.slice(0, maxRows);

  return (
    <div className={THEME.TABLE_WRAP}>
      <div className="overflow-x-auto">
        <table className={THEME.TABLE}>
          <thead>
            <tr>
              <th className={THEME.TH}>Key</th>
              <th className={THEME.TH}>Message</th>
              <th className={THEME.TH}>Value</th>
              <th className={THEME.TH}>Limit</th>
              <th className={THEME.TH}>Unit</th>
            </tr>
          </thead>
          <tbody>
            {slice.map((v, i) => (
              <tr key={i} className={THEME.TR}>
                <td className={THEME.TD_LABEL}>{v?.key ?? '-'}</td>
                <td className={THEME.TD}>
                  <div className="text-[10px] font-sans">
                    {v?.message ?? '-'}
                  </div>
                </td>
                <td className={THEME.TD}>{String(v?.value ?? '-')}</td>
                <td className={THEME.TD}>{String(v?.limit ?? '-')}</td>
                <td className={THEME.TD}>{String(v?.unit ?? '-')}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {rows.length > slice.length ? (
        <div className="px-3 py-2 text-[10px] text-slate-500 bg-white border-t border-slate-200">
          * {slice.length}개까지만 표시(총 {rows.length}개). 전체는
          Raw(접기)에서 확인하세요.
        </div>
      ) : null}
    </div>
  );
}
