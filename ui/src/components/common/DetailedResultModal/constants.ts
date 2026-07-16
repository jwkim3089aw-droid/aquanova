// ui/src/components/common/DetailedResultModal/constants.ts

export const STYLES = {
  OVERLAY:
    'fixed inset-0 z-[9999] flex items-center justify-center bg-black/80 backdrop-blur-md animate-in fade-in duration-200',
  CONTAINER:
    'w-[95vw] max-w-[1600px] h-[92vh] bg-[#0b1120] border border-slate-700 rounded-xl shadow-2xl flex flex-col overflow-hidden ring-1 ring-white/10 font-sans',
  HEADER:
    'flex-none h-16 border-b border-slate-700 bg-[#0f172a] flex items-center justify-between px-6 select-none shrink-0',
  SIDEBAR:
    'w-72 bg-[#0f172a] border-r border-slate-700 flex flex-col overflow-y-auto shrink-0 scrollbar-thin scrollbar-thumb-slate-800',
  CONTENT: 'flex-1 flex flex-col bg-[#0b1120] relative min-w-0 overflow-hidden',
  TAB_BAR:
    'flex-none border-b border-slate-700 bg-[#1e293b]/50 backdrop-blur-sm flex px-4 gap-1 overflow-x-auto',
  SCROLL_AREA:
    'flex-1 overflow-y-auto p-0 scrollbar-thin scrollbar-thumb-slate-700',

  // Tables
  TH: 'px-4 py-3 text-left font-semibold text-slate-500 uppercase text-[10px] bg-slate-900/90 border-b border-slate-700 sticky top-0 backdrop-blur-md z-10 whitespace-nowrap',
  TD: 'px-4 py-3 text-right font-mono text-slate-300 border-b border-slate-800/50 text-[11px] tabular-nums',
  TD_L: 'px-4 py-3 text-left font-bold text-slate-400 border-b border-slate-800/50 text-[11px] whitespace-nowrap',
};
