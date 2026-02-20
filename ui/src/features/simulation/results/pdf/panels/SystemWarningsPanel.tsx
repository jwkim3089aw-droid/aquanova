// ui/src/features/simulation/results/pdf/panels/SystemWarningsPanel.tsx
import React from 'react';
import { THEME } from '../theme';
import { Badge } from '../components';
import { safeArr, safeObj } from '../utils';

function collectViolationsByStage(stages: any[]) {
  const out: any[] = [];
  for (let i = 0; i < stages.length; i++) {
    const s = stages[i];
    const stageNo = s?.stage ?? i + 1;
    const moduleType = String(s?.module_type ?? 'RO');
    const chem = safeObj(s?.chemistry);
    const vlist = safeArr(chem?.violations ?? []);

    for (const v of vlist) {
      out.push({
        stage: `Stage ${stageNo}`,
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

export function SystemWarningsPanel({
  stages,
  globalWarnings,
}: {
  stages: any[];
  globalWarnings?: any[];
}) {
  // ✅ 백엔드에서 받은 globalWarnings가 있으면 그것을 사용, 없으면 기존처럼 수집
  const rows = globalWarnings?.length
    ? globalWarnings
    : collectViolationsByStage(stages);

  if (!rows.length) {
    return (
      <div className="flex items-center gap-2">
        <Badge text="NO WARN" tone="emerald" />
        <div className="text-[10px] text-slate-500">
          No system warnings. Operations are within guidelines.
        </div>
      </div>
    );
  }

  const maxRows = 30;
  const slice = rows.slice(0, maxRows);
  const tone = rows.length > 0 ? 'rose' : 'emerald';

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <Badge text={`WARN ${rows.length}`} tone={tone as any} />
        <div className="text-[10px] text-slate-500">
          System Guideline Violations (Showing up to {maxRows})
        </div>
      </div>

      <div className={THEME.TABLE_WRAP}>
        <div className="overflow-x-auto">
          <table className={THEME.TABLE}>
            <thead>
              <tr>
                <th className={THEME.TH}>Stage</th>
                <th className={THEME.TH}>Type</th>
                <th className={THEME.TH}>Message</th>
                <th className={THEME.TH}>Value</th>
                <th className={THEME.TH}>Limit</th>
              </tr>
            </thead>
            <tbody>
              {slice.map((r, i) => (
                <tr key={i} className={THEME.TR}>
                  <td className={THEME.TD_LABEL}>{r.stage}</td>
                  <td className={THEME.TD}>{r.module_type}</td>
                  <td className={THEME.TD}>
                    <div className="font-sans font-semibold text-[10px] text-rose-600">
                      {r.message}
                    </div>
                  </td>
                  <td className={THEME.TD}>
                    {String(r.value ?? '-')} {r.unit}
                  </td>
                  <td className={THEME.TD}>{String(r.limit ?? '-')}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
