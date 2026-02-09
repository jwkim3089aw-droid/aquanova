// ui\src\features\simulation\chemistry\format.ts
export function n0(v: any): number {
  const x = Number(v);
  return Number.isFinite(x) ? x : 0;
}

export function roundTo(v: number, dp: number): number {
  const p = Math.pow(10, dp);
  return Math.round(v * p) / p;
}

export function fmtNumber(v: any, dp = 1): string {
  const x = Number(v);
  if (!Number.isFinite(x)) return '0';
  const s = x.toFixed(dp);
  return s.replace(/\.0+$/, '');
}

export function fmtInputNumber(v: any, maxDp = 3): string {
  if (v === '' || v === null || v === undefined) return '';
  const x = Number(v);
  if (!Number.isFinite(x)) return '';
  const s = x.toFixed(maxDp);
  return s.replace(/\.?0+$/, '');
}
