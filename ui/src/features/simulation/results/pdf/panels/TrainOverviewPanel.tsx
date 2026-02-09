// ui/src/features/simulation/results/pdf/panels/TrainOverviewPanel.tsx
import React from 'react';
import { GitBranch } from 'lucide-react';
import { Badge } from '../components';
import { safeArr } from '../utils';

export function TrainOverviewPanel({ stages }: { stages: any[] }) {
  const st = safeArr(stages);
  if (!st.length) {
    return <div className="text-[10px] text-slate-500">No stage data.</div>;
  }

  const items = st.map((s, idx) => ({
    stage: s?.stage ?? idx + 1,
    type: String(s?.module_type ?? 'RO').toUpperCase(),
  }));

  const counts = items.reduce<Record<string, number>>((acc, it) => {
    acc[it.type] = (acc[it.type] || 0) + 1;
    return acc;
  }, {});

  const chips = Object.entries(counts).map(([k, v]) => (
    <Badge key={k} text={`${k} ${v}`} tone={k === 'HRRO' ? 'violet' : 'blue'} />
  ));

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 flex-wrap">{chips}</div>

      <div className="rounded-xl border border-slate-200 bg-white p-3">
        <div className="flex items-center gap-2 text-[10px] font-extrabold text-slate-500 uppercase tracking-widest mb-3">
          <GitBranch className="w-4 h-4 opacity-70" />
          Train Map (PFD-lite)
        </div>

        <div className="flex items-center flex-wrap gap-2">
          <div className="px-3 py-2 rounded-lg border border-slate-200 bg-slate-50 text-[11px] font-bold">
            Feed
          </div>

          {items.map((it, i) => (
            <React.Fragment key={`${it.type}-${i}`}>
              <div className="text-slate-400 text-xs">→</div>
              <div className="px-3 py-2 rounded-lg border border-slate-200 bg-white text-[11px] font-bold">
                {`Stage ${it.stage}`}
                <span className="ml-2 text-[10px] font-black text-slate-500">
                  {it.type}
                </span>
              </div>
            </React.Fragment>
          ))}

          <div className="text-slate-400 text-xs">→</div>
          <div className="px-3 py-2 rounded-lg border border-slate-200 bg-emerald-50 text-[11px] font-bold text-emerald-700">
            Product
          </div>

          <div className="text-slate-400 text-xs">/</div>
          <div className="px-3 py-2 rounded-lg border border-slate-200 bg-slate-50 text-[11px] font-bold">
            Brine
          </div>
        </div>

        <div className="mt-3 text-[10px] text-slate-500">
          * Wave의 스트림 번호 기반 PFD 대신, 현재 계산 결과(stage_metrics)를
          기반으로 공정 트레인 구조를 간단히 시각화했습니다.
        </div>
      </div>
    </div>
  );
}
