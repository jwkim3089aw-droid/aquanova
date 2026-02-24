// ui/src/features/simulation/editors/UnitForms/utils.ts

export const GROUP_CLS =
  'p-2 border border-slate-800 rounded-lg bg-slate-900/40 mb-2 shadow-sm flex flex-col';
export const HEADER_CLS =
  'text-[11px] font-bold text-slate-300 mb-2 border-b border-slate-700/50 pb-1 flex items-center gap-1.5 shrink-0';
export const INPUT_CLS =
  'h-7 text-xs bg-slate-950 border-slate-700 focus:border-blue-500 focus:bg-slate-900 transition-colors w-full rounded px-2 outline-none text-slate-100 placeholder:text-slate-600';
export const READONLY_CLS =
  'h-7 bg-slate-800/80 border border-slate-700/50 rounded px-2 flex items-center text-xs font-bold';

export const mapMembraneChange = (updates: any) => {
  const patch: any = {};
  if (updates.mode !== undefined) patch.membrane_mode = updates.mode;
  if (updates.model !== undefined) patch.membrane_model = updates.model;
  if (updates.area !== undefined) patch.custom_area_m2 = updates.area;
  if (updates.A !== undefined) patch.custom_A_lmh_bar = updates.A;
  if (updates.B !== undefined) patch.custom_B_lmh = updates.B;
  if (updates.rej !== undefined) patch.custom_salt_rejection_pct = updates.rej;
  return patch;
};
