// ui/src/features/simulation/results/pdf/theme.ts

export const THEME = {
  // ✅ 수정: 인쇄 시 배경색 강제 인쇄, 여백/그림자 초기화 적용
  PAGE: 'w-[210mm] min-h-[297mm] bg-white text-slate-800 font-sans p-10 mx-auto mb-10 relative box-border print:m-0 print:p-8 print:shadow-none print:color-adjust-exact [-webkit-print-color-adjust:exact]',
  H1: 'text-3xl font-black text-slate-900 tracking-tight',
  H2: 'text-[11px] font-extrabold text-slate-500 uppercase tracking-widest',

  // ✅ 수정: 섹션이 페이지 중간에서 잘리는 현상 방지 (break-inside-avoid)
  SECTION:
    'rounded-xl border border-slate-200 bg-white overflow-hidden print:break-inside-avoid',
  SECTION_HEAD:
    'px-4 py-3 bg-slate-50 border-b border-slate-200 flex items-center justify-between',
  SECTION_TITLE:
    'text-[12px] font-extrabold text-slate-800 tracking-wide flex items-center gap-2',
  SECTION_BODY: 'p-4',

  MUTED: 'text-[10px] text-slate-500',

  // ✅ 수정: 테이블 래퍼가 잘리는 현상 방지
  TABLE_WRAP:
    'rounded-xl border border-slate-200 overflow-hidden print:break-inside-avoid',
  TABLE: 'w-full text-[10px] border-collapse',
  TH: 'bg-slate-100 text-slate-600 font-bold uppercase tracking-tight text-left py-2 px-3 border-b border-slate-200',
  TR: 'border-b border-slate-100 last:border-0',
  TD: 'py-1.5 px-3 text-slate-700 font-mono align-top',
  TD_LABEL: 'py-1.5 px-3 text-slate-700 font-sans font-semibold align-top',
} as const;

export default THEME;
