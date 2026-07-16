// ui/src/features/simulation/results/pdf/components/KPI.tsx
import React from 'react';

export function KPI({
  labelKo,
  valueText,
  hint,
  icon,
  tone = 'slate',
}: {
  labelKo: string;
  valueText: string;
  hint?: string;
  icon?: React.ReactNode;
  tone?: 'slate' | 'blue' | 'emerald' | 'amber';
}) {
  // ✅ 모던 대시보드 스타일: 배경은 아주 은은하게, 아이콘 쪽은 확실한 컬러감으로 대비
  const tones: Record<string, { bg: string; iconBg: string; text: string }> = {
    slate: {
      bg: 'bg-slate-50 border-slate-200',
      iconBg: 'bg-slate-200 text-slate-600',
      text: 'text-slate-800',
    },
    blue: {
      bg: 'bg-blue-50/30 border-blue-100',
      iconBg: 'bg-blue-100 text-blue-600',
      text: 'text-blue-900',
    },
    emerald: {
      bg: 'bg-emerald-50/30 border-emerald-100',
      iconBg: 'bg-emerald-100 text-emerald-600',
      text: 'text-emerald-900',
    },
    amber: {
      bg: 'bg-amber-50/30 border-amber-100',
      iconBg: 'bg-amber-100 text-amber-600',
      text: 'text-amber-900',
    },
  };

  const t = tones[tone] || tones.slate;

  return (
    <div
      className={`rounded-2xl border p-4 flex flex-col justify-between h-full ${t.bg}`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="text-[11px] font-extrabold uppercase tracking-widest text-slate-500">
          {labelKo}
        </div>
        {/* 아이콘에 둥근 배경을 주어 시각적 포인트 형성 */}
        {icon && <div className={`p-1.5 rounded-lg ${t.iconBg}`}>{icon}</div>}
      </div>

      <div className="mt-2">
        {/* 숫자를 기존 text-xl에서 text-2xl로 키우고 자간을 좁혀 세련미 강조 */}
        <div
          className={`text-2xl font-mono font-black tracking-tight ${t.text}`}
        >
          {valueText}
        </div>
        {hint && (
          <div className="text-[10px] text-slate-400 mt-0.5 font-medium">
            {hint}
          </div>
        )}
      </div>
    </div>
  );
}
