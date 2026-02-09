// ui/src/features/simulation/results/pdf/panels/SystemWarningsPanel.tsx
import React from 'react';
import { THEME } from '../theme';
import { Badge } from '../components';
import { safeArr, safeObj } from '../utils';

function collectViolationsByStage(stages: any[]) {
  const out: Array<{
    stage: number;
    module_type: string;
    key: string;
    message: string;
    value: any;
    limit: any;
    unit: any;
  }> = [];

  for (let i = 0; i < stages.length; i++) {
    const s = stages[i];
    const stageNo = s?.stage ?? i + 1;
    const moduleType = String(s?.module_type ?? 'RO');

    const chem = safeObj(s?.chemistry);
    const vlist = safeArr(chem?.violations ?? []);

    for (const v of vlist) {
      out.push({
        stage: stageNo,
        module_type: moduleType,
        key: String(v?.key ?? '-'),
        message: String(v?.message ?? v?.msg ?? '-'),
        value: v?.value ?? '-',
        limit: v?.limit ?? '-',
        unit: v?.unit ?? '-',
      });
    }
  }
  return out;
}

export function SystemWarningsPanel({ stages }: { stages: any[] }) {
  const rows = collectViolationsByStage(stages);
  if (!rows.length) {
    return <div className="text-[10px] text-slate-500">No violations.</div>;
  }

  const maxRows = 30;
  const slice = rows.slice(0, maxRows);
  const tone = rows.length ? 'rose' : 'emerald';

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <Badge text={`WARN ${rows.length}`} tone={tone as any} />
        <div className="text-[10px] text-slate-500">
          stage별 chemistry.violations 집계(최대 {maxRows}개 표시)
        </div>
      </div>

      <div className={THEME.TABLE_WRAP}>
        <div className="overflow-x-auto">
          <table className={THEME.TABLE}>
            <thead>
              <tr>
                <th className={THEME.TH}>Stage</th>
                <th className={THEME.TH}>Type</th>
                <th className={THEME.TH}>Key</th>
                <th className={THEME.TH}>Message</th>
                <th className={THEME.TH}>Value</th>
                <th className={THEME.TH}>Limit</th>
                <th className={THEME.TH}>Unit</th>
              </tr>
            </thead>
            <tbody>
              {slice.map((r, i) => (
                <tr key={i} className={THEME.TR}>
                  <td className={THEME.TD_LABEL}>{`Stage ${r.stage}`}</td>
                  <td className={THEME.TD}>{r.module_type}</td>
                  <td className={THEME.TD}>{r.key}</td>
                  <td className={THEME.TD}>
                    <div className="font-sans text-[10px]">{r.message}</div>
                  </td>
                  <td className={THEME.TD}>{String(r.value)}</td>
                  <td className={THEME.TD}>{String(r.limit)}</td>
                  <td className={THEME.TD}>{String(r.unit)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {rows.length > slice.length ? (
          <div className="px-3 py-2 text-[10px] text-slate-500 bg-white border-t border-slate-200">
            * {slice.length}개까지만 표시(총 {rows.length}개). 전체는 HRRO
            상세/Raw(접기)에서 확인하세요.
          </div>
        ) : null}
      </div>
    </div>
  );
}
