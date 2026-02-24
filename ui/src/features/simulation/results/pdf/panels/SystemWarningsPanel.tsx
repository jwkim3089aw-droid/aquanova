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
  // ✅ 백엔드에서 넘겨준 globalWarnings(스케일링 등)를 병합
  const collected = collectViolationsByStage(stages);
  const rows =
    globalWarnings && globalWarnings.length > 0 ? globalWarnings : collected;

  if (!rows.length) {
    return (
      <div className="flex items-center gap-2 p-2 border border-emerald-900/30 bg-emerald-950/10 rounded">
        <Badge text="NO WARN" tone="emerald" />
        <div className="text-[10px] text-emerald-600/80 font-bold">
          No system warnings detected. Operations are within design guidelines.
        </div>
      </div>
    );
  }

  const maxRows = 30;
  const slice = rows.slice(0, maxRows);
  const isCritical = rows.length > 2;

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2 mb-1">
        <Badge
          text={`${rows.length} WARNINGS`}
          tone={isCritical ? 'rose' : 'amber'}
        />
        <div className="text-[10px] text-slate-500 font-medium">
          System Guideline Violations (Showing up to {maxRows})
        </div>
      </div>

      <div className={THEME.TABLE_WRAP}>
        <div className="overflow-x-auto">
          <table className={THEME.TABLE}>
            <thead>
              <tr className="bg-rose-950/20">
                <th className={THEME.TH}>Stage</th>
                <th className={THEME.TH}>Type</th>
                <th className={THEME.TH}>Warning Message</th>
                <th className={THEME.TH}>Value</th>
                <th className={THEME.TH}>Limit</th>
              </tr>
            </thead>
            <tbody>
              {slice.map((r, i) => (
                <tr
                  key={i}
                  className={`${THEME.TR} border-l-2 border-l-rose-500`}
                >
                  <td className={`${THEME.TD_LABEL} font-bold text-slate-300`}>
                    {r.stage || 'SYS'}
                  </td>
                  <td className={THEME.TD}>{r.module_type || '-'}</td>
                  <td className={THEME.TD}>
                    <div className="font-sans font-bold text-[10.5px] text-rose-500">
                      {r.message}
                    </div>
                  </td>
                  <td className={`${THEME.TD} font-mono text-slate-300`}>
                    {typeof r.value === 'number'
                      ? r.value.toFixed(2)
                      : String(r.value ?? '-')}{' '}
                    <span className="text-[9px]">{r.unit}</span>
                  </td>
                  <td className={`${THEME.TD} font-mono text-slate-500`}>
                    {String(r.limit ?? '-')}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
