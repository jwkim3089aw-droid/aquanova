// ui/src/features/simulation/results/pdf/utils.ts
import { fmt as _fmt, pct as _pct } from '../../model/types';

export const fmt = _fmt;
export const pct = _pct;

export function safeObj(v: any): Record<string, any> {
  return v && typeof v === 'object' ? v : {};
}
export function safeArr(v: any): any[] {
  return Array.isArray(v) ? v : [];
}
export function pickNumber(v: any): number | null {
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}
export function first<T>(...candidates: T[]): T | null {
  for (const c of candidates) {
    if (c !== undefined && c !== null) return c;
  }
  return null;
}
export function pickNumFromKeys(obj: any, keys: string[]): number | null {
  for (const k of keys) {
    const n = pickNumber(obj?.[k]);
    if (n != null) return n;
  }
  return null;
}
export function pickAnyFromKeys(obj: any, keys: string[]): any {
  for (const k of keys) {
    const v = obj?.[k];
    if (v !== undefined && v !== null && v !== '') return v;
  }
  return null;
}
export function trunc(s: string, max = 12000) {
  if (!s) return s;
  return s.length > max ? s.slice(0, max) + '\n…(truncated)' : s;
}
export function pretty(v: any): string {
  if (v == null) return '';
  if (typeof v === 'string') return v;
  if (typeof v === 'number' || typeof v === 'boolean') return String(v);
  try {
    return JSON.stringify(v, null, 2);
  } catch {
    return String(v);
  }
}
export function summarizeValue(v: any): string {
  if (v == null) return '-';
  if (typeof v === 'number') return fmt(v);
  if (typeof v === 'boolean') return v ? 'true' : 'false';
  if (typeof v === 'string') {
    const s = v.trim();
    return s.length > 80 ? s.slice(0, 80) + '…' : s;
  }
  if (Array.isArray(v)) return `Array(${v.length})`;
  if (typeof v === 'object') return `Object(${Object.keys(v).length})`;
  return String(v);
}
export function hasAnyNumber(rows: any[], key: string): boolean {
  for (const r of rows) {
    const n = pickNumber(r?.[key]);
    if (n != null) return true;
  }
  return false;
}
