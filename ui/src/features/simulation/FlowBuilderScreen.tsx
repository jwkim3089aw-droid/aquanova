// ui/src/features/simulation/FlowBuilderScreen.tsx
import React, { useCallback, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import ReactFlow, {
  Background,
  Controls,
  ReactFlowProvider,
  NodeChange,
} from 'reactflow';
import 'reactflow/dist/style.css';

import {
  nodeTypes,
  TopBar,
  UnitsToggle,
  LoadingOverlay,
  PaletteItemBig,
  ErrorBoundary,
} from '.';
import Footer from '@/components/Footer';

import IconRO from '@/components/icons/IconRO';
import IconHRRO from '@/components/icons/IconHRRO';
import IconUF from '@/components/icons/IconUF';
import IconMF from '@/components/icons/IconMF';
import IconNF from '@/components/icons/IconNF';

import { autoLinkLinear } from './model/logic';
import { SetEdgesFn, SetNodesFn, fmt, pct } from './model/types';
import { useFlowLogic } from './hooks/useFlowLogic';

import {
  UnitInspectorModal,
  GlobalOptionsModal,
} from '@/features/simulation/components/FlowModals';

import {
  AlertTriangle,
  ClipboardList,
  Layers,
  Loader2,
  Zap,
  Droplets,
  Activity,
  Beaker,
  FileText,
  CheckCircle2,
  XCircle,
  Gauge,
} from 'lucide-react';

const DELETE_KEYS = ['Backspace', 'Delete'] as const;

// ------------------------------------------------------------
// tiny safe helpers (local, zero dependencies)
// ------------------------------------------------------------
function safeObj<T extends Record<string, any>>(v: any): T {
  return v && typeof v === 'object' && !Array.isArray(v) ? (v as T) : ({} as T);
}
function safeArr<T = any>(v: any): T[] {
  return Array.isArray(v) ? (v as T[]) : [];
}
function pickNumber(v: any): number | null {
  return typeof v === 'number' && Number.isFinite(v) ? v : null;
}
function pickNumLike(v: any): number | null {
  const x = Number(v);
  return Number.isFinite(x) ? x : null;
}

function countWarnings(stages: any[]) {
  let n = 0;
  for (const s of stages) n += safeArr(s?.chemistry?.violations).length;
  return n;
}

function firstNonEmptyString(...xs: any[]) {
  for (const x of xs) {
    if (typeof x === 'string' && x.trim()) return x.trim();
  }
  return null;
}

function normalizeViolationLabel(v: any) {
  if (typeof v === 'string') return v.trim() || '가이드라인 위반';
  return (
    firstNonEmptyString(
      v?.label,
      v?.name,
      v?.type,
      v?.code,
      v?.message,
      v?.detail,
      v?.reason,
    ) || '가이드라인 위반'
  );
}

function shortenText(s: string, max = 64) {
  const t = String(s || '')
    .replace(/\s+/g, ' ')
    .trim();
  if (!t) return '';
  return t.length > max ? `${t.slice(0, max - 1)}…` : t;
}

function normalizeWarnKind(label: string) {
  const s = String(label || '').toLowerCase();

  if (
    s.includes('average flux') ||
    s.includes('avg flux') ||
    s.includes('flux')
  )
    return '평균 플럭스';
  if (
    s.includes('pressure drop') ||
    s.includes('delta p') ||
    s.includes('dp') ||
    s.includes('Δp')
  )
    return '압력 강하(ΔP)';
  if (s.includes('tmp')) return 'TMP';
  if (s.includes('lsi')) return 'LSI';
  if (s.includes('scaling')) return '스케일링 위험';
  if (s.includes('ph')) return 'pH';
  if (s.includes('tds')) return 'TDS';

  return null;
}

function inferSeverity(label: string) {
  const s = String(label || '').toLowerCase();
  if (
    s.includes('out of guideline') ||
    s.includes('out of range') ||
    s.includes('exceed') ||
    s.includes('above')
  )
    return '기준 초과';
  if (s.includes('below') || s.includes('under')) return '기준 미달';
  return '기준 이탈';
}

function parseRangeFromText(raw: string) {
  // ex) "Average flux 32.516 LMH is out of guideline range [20.0..26.0]"
  const s = String(raw || '')
    .replace(/\s+/g, ' ')
    .trim();

  const range =
    s.match(/\[\s*([0-9]*\.?[0-9]+)\s*\.\.\s*([0-9]*\.?[0-9]+)\s*\]/) ||
    s.match(/\(\s*([0-9]*\.?[0-9]+)\s*\.\.\s*([0-9]*\.?[0-9]+)\s*\)/);

  const au =
    s.match(
      /([0-9]*\.?[0-9]+)\s*(LMH|GFD|bar|psi|kWh\/m³|kWh\/m3|mg\/L|ppm)\b/i,
    ) || null;

  const actual = au ? Number(au[1]) : null;
  const unit = au ? au[2] : null;

  const min = range ? Number(range[1]) : null;
  const max = range ? Number(range[2]) : null;

  return {
    actual: Number.isFinite(actual as any) ? (actual as number) : null,
    min: Number.isFinite(min as any) ? (min as number) : null,
    max: Number.isFinite(max as any) ? (max as number) : null,
    unit: unit ? String(unit) : null,
  };
}

function inferSeverityByNumbers(
  actual: number | null,
  min: number | null,
  max: number | null,
) {
  if (actual == null) return null;
  if (max != null && actual > max) return '기준 초과';
  if (min != null && actual < min) return '기준 미달';
  return '기준 이탈';
}

function unitFallbackForKind(kind: string, unitLabels: any) {
  const k = String(kind || '');
  if (k.includes('플럭스')) return unitLabels?.flux ?? 'LMH';
  if (k.includes('압력') || k.includes('ΔP') || k.includes('TMP'))
    return unitLabels?.pressure ?? 'bar';
  if (k.includes('TDS')) return 'mg/L';
  return null;
}

function toWarnItem(v: any, unitLabels: any) {
  const raw = normalizeViolationLabel(v);
  const kind = normalizeWarnKind(raw) || shortenText(raw, 28);

  const actual =
    pickNumLike(v?.actual) ??
    pickNumLike(v?.value) ??
    pickNumLike(v?.observed) ??
    pickNumLike(v?.measured) ??
    null;

  const min =
    pickNumLike(v?.min) ??
    pickNumLike(v?.lower) ??
    pickNumLike(v?.guideline_min) ??
    null;

  const max =
    pickNumLike(v?.max) ??
    pickNumLike(v?.upper) ??
    pickNumLike(v?.guideline_max) ??
    null;

  const unit =
    (typeof v?.unit === 'string' && v.unit.trim() ? v.unit.trim() : null) ??
    null;

  const parsed = parseRangeFromText(raw);

  const finalActual = actual ?? parsed.actual;
  const finalMin = min ?? parsed.min;
  const finalMax = max ?? parsed.max;
  const finalUnit =
    unit ?? parsed.unit ?? unitFallbackForKind(kind, unitLabels);

  const sev =
    inferSeverityByNumbers(finalActual, finalMin, finalMax) ??
    inferSeverity(raw);

  return {
    kind,
    severity: sev,
    actual: finalActual,
    min: finalMin,
    max: finalMax,
    unit: finalUnit,
    raw,
  };
}

function formatWarnValue(it: any) {
  const a = it?.actual;
  const mi = it?.min;
  const ma = it?.max;
  const unit = it?.unit ? ` ${it.unit}` : '';

  if (a == null && mi == null && ma == null) return null;

  if (a != null && ma != null && a > ma) return `${fmt(a)} > ${fmt(ma)}${unit}`;
  if (a != null && mi != null && a < mi) return `${fmt(a)} < ${fmt(mi)}${unit}`;
  if (a != null && mi != null && ma != null)
    return `${fmt(a)} (${fmt(mi)}..${fmt(ma)})${unit}`;

  if (a != null) return `${fmt(a)}${unit}`;
  if (mi != null && ma != null) return `(${fmt(mi)}..${fmt(ma)})${unit}`;
  return null;
}

// ✅ WAVE 스타일 경고 요약(줄/불릿 + 수치 가능하면 표시)
function buildWarnInfo(stages: any[], unitLabels: any) {
  if (!stages?.length) return null;

  const perStage = stages
    .map((s: any, idx: number) => {
      const stageNo = s?.stage ?? idx + 1;
      const type = String(s?.module_type ?? '—').toUpperCase();
      const violations = safeArr(s?.chemistry?.violations);
      return { stageNo, type, n: violations.length, violations };
    })
    .filter((x) => x.n > 0)
    .sort((a, b) => b.n - a.n);

  if (perStage.length === 0) return null;

  const top = perStage[0];

  const itemsRaw = top.violations.map((v: any) => toWarnItem(v, unitLabels));

  const items: any[] = [];
  const seen = new Set<string>();
  for (const it of itemsRaw) {
    if (!it?.kind) continue;
    if (seen.has(it.kind)) continue;
    seen.add(it.kind);
    items.push(it);
    if (items.length >= 2) break;
  }

  return {
    total: perStage.reduce((acc, x) => acc + x.n, 0),
    topStage: { stageNo: top.stageNo, type: top.type, count: top.n },
    extraStageCount: Math.max(0, perStage.length - 1),
    items,
  };
}

type Tone = 'neutral' | 'ok' | 'warn' | 'error' | 'running';

function SummaryCard({
  title,
  icon,
  children,
  tone = 'neutral',
}: {
  title: string;
  icon?: React.ReactNode;
  children: React.ReactNode;
  tone?: Tone;
}) {
  const toneClass =
    tone === 'ok'
      ? 'border-emerald-800/60 bg-emerald-950/15'
      : tone === 'warn'
        ? 'border-yellow-800/60 bg-yellow-950/15'
        : tone === 'error'
          ? 'border-red-800/60 bg-red-950/15'
          : tone === 'running'
            ? 'border-sky-800/60 bg-sky-950/15'
            : 'border-slate-800 bg-slate-950/40';

  return (
    <div className={`rounded border p-3 ${toneClass}`}>
      <div className="text-[10px] text-slate-500 font-bold uppercase tracking-wider flex items-center gap-2">
        {icon ? <span className="text-slate-400">{icon}</span> : null}
        {title}
      </div>
      <div className="mt-1">{children}</div>
    </div>
  );
}

type ResultsPanelProps = {
  loading: boolean;
  err: string | null;
  result: any;
  onOpenReport: () => void;
};

function ResultsPanel({
  loading,
  err,
  result,
  onOpenReport,
}: ResultsPanelProps) {
  const r = result || {};
  const kpi = safeObj(r.kpi);
  const stages = safeArr(r.stage_metrics);
  const unitLabels = safeObj(r.unit_labels);

  const hasResult =
    Object.keys(kpi).length > 0 ||
    stages.length > 0 ||
    safeArr(r.streams).length > 0;

  const warningsCount = useMemo(() => countWarnings(stages), [stages]);
  const warnInfo = useMemo(
    () => buildWarnInfo(stages, unitLabels),
    [stages, unitLabels],
  );

  const canOpenReport = hasResult && !loading && !err;

  const unitFlow = unitLabels.flow ?? 'm³/h';

  const k = {
    recovery_pct: pickNumber(kpi.recovery_pct),
    sec_kwhm3: pickNumber(kpi.sec_kwhm3 ?? kpi.sec_kwh_m3),
    flux_lmh: pickNumber(kpi.flux_lmh ?? kpi.jw_avg_lmh),
    prod_tds: pickNumber(kpi.prod_tds),
    feed_m3h: pickNumber(kpi.feed_m3h),
    permeate_m3h: pickNumber(kpi.permeate_m3h),
  };

  const status: { tone: Tone; label: string; icon: React.ReactNode } = loading
    ? {
        tone: 'running',
        label: '계산 중',
        icon: <Loader2 className="w-4 h-4 animate-spin" />,
      }
    : err
      ? { tone: 'error', label: '오류', icon: <XCircle className="w-4 h-4" /> }
      : warningsCount > 0
        ? {
            tone: 'warn',
            label: '경고',
            icon: <AlertTriangle className="w-4 h-4" />,
          }
        : hasResult
          ? {
              tone: 'ok',
              label: '정상',
              icon: <CheckCircle2 className="w-4 h-4" />,
            }
          : {
              tone: 'neutral',
              label: '데이터 없음',
              icon: <ClipboardList className="w-4 h-4" />,
            };

  return (
    <div className="flex-none w-[450px] flex flex-col overflow-hidden rounded border border-slate-800 bg-slate-900/10 shadow-sm">
      {/* Header: 제목 크게 + 상세 리포트 버튼 */}
      <div className="flex-none px-3 h-[56px] border-b border-slate-800 bg-slate-900/50 flex justify-between items-center">
        <div className="flex items-center gap-2 min-w-0">
          <span className="text-[16px] font-extrabold text-slate-200 tracking-[0.14em]">
            분석 결과
          </span>
        </div>

        <button
          onClick={onOpenReport}
          disabled={!canOpenReport}
          className={`h-9 px-3 rounded border text-[12px] font-black inline-flex items-center gap-2 transition-colors
            ${
              !canOpenReport
                ? 'border-slate-800 bg-slate-900 text-slate-600 cursor-not-allowed'
                : 'border-blue-700/60 bg-blue-900/20 text-blue-200 hover:bg-blue-900/30'
            }`}
          title="상세 리포트 열기"
        >
          <FileText className="w-4 h-4" />
          상세 리포트
        </button>
      </div>

      {/* Body */}
      <div className="flex-1 overflow-y-auto p-2 min-h-0 custom-scrollbar bg-slate-950/20">
        {!hasResult && !err ? (
          <div className="p-4 rounded border border-slate-800 bg-slate-950/40 text-slate-400">
            <div className="flex items-center gap-2 mb-2">
              <ClipboardList className="w-4 h-4 opacity-70" />
              <span className="font-bold text-slate-300">
                결과가 아직 없습니다
              </span>
            </div>
            <ul className="text-[11px] leading-5 list-disc pl-5">
              <li>공정을 구성한 뒤</li>
              <li>상단에서 실행(Run)을 누르세요</li>
              <li>상세 내용은 “상세 리포트”에서 확인합니다</li>
            </ul>
          </div>
        ) : (
          <div className="space-y-2">
            {/* 상태 + 유량 */}
            <div className="grid grid-cols-2 gap-2">
              <SummaryCard
                title="상태"
                icon={<Gauge className="w-4 h-4" />}
                tone={status.tone}
              >
                <div className="flex items-center gap-2">
                  <span className="text-slate-200">{status.icon}</span>
                  <span className="text-[13px] font-mono font-black text-slate-100">
                    {status.label}
                  </span>

                  {/* ✅ 경고 개수는 뱃지로만 */}
                  {status.tone === 'warn' ? (
                    <span className="ml-1 text-[10px] font-black text-yellow-200 bg-yellow-950/30 px-1.5 py-0.5 rounded border border-yellow-900">
                      {warningsCount}
                    </span>
                  ) : null}
                </div>

                {/* ✅ 경고 요약(줄 정리 + 수치 표시) */}
                {status.tone === 'warn' && warnInfo ? (
                  <div className="mt-2 space-y-1">
                    <div className="text-[10px] font-extrabold text-yellow-200/90">
                      경고 요약
                    </div>

                    <div className="text-[11px] text-slate-100">
                      <span className="text-slate-400 font-bold">대상:</span>{' '}
                      <span className="font-mono font-black">
                        {warnInfo.topStage.stageNo}단({warnInfo.topStage.type})
                      </span>
                      <span className="text-slate-400"> · </span>
                      <span className="font-mono font-black">
                        {warnInfo.topStage.count}건
                      </span>
                      {warnInfo.extraStageCount > 0 ? (
                        <span className="text-slate-400">
                          {' '}
                          · +{warnInfo.extraStageCount}단
                        </span>
                      ) : null}
                    </div>

                    {warnInfo.items?.length ? (
                      <ul className="mt-1 space-y-1">
                        {warnInfo.items.map((it: any, i: number) => {
                          const v = formatWarnValue(it);
                          return (
                            <li
                              key={`${it.kind}-${i}`}
                              className="flex items-start gap-2"
                            >
                              <span className="mt-[6px] w-1.5 h-1.5 rounded-full bg-yellow-400/80 flex-none" />
                              <div className="min-w-0">
                                <div className="text-[11px] text-yellow-100/85 leading-4">
                                  <span className="font-bold">{it.kind}</span>{' '}
                                  <span className="text-yellow-200/60 font-bold">
                                    ({it.severity})
                                  </span>
                                </div>
                                {v ? (
                                  <div className="text-[10px] text-slate-200/70 font-mono leading-4">
                                    {v}
                                  </div>
                                ) : null}
                              </div>
                            </li>
                          );
                        })}
                      </ul>
                    ) : (
                      <div className="text-[10px] text-yellow-100/70">
                        (세부 항목을 불러오지 못했습니다)
                      </div>
                    )}
                  </div>
                ) : null}

                {/* ✅ 오류면 에러 메시지 */}
                {err ? (
                  <div className="text-[10px] text-red-200/80 mt-2 line-clamp-2">
                    {err}
                  </div>
                ) : null}
              </SummaryCard>

              {/* ✅ 유량(줄바꿈) + 단위 톤/크기 통일 */}
              <SummaryCard title="유량" icon={<Layers className="w-4 h-4" />}>
                <div className="space-y-1">
                  <div>
                    <div className="text-[10px] font-bold text-slate-400 leading-4">
                      원수
                    </div>
                    <div className="text-[12px] font-mono font-black text-slate-100 leading-5">
                      {k.feed_m3h != null ? fmt(k.feed_m3h) : '—'}{' '}
                      <span className="text-[12px] font-mono font-bold text-slate-300">
                        {unitFlow}
                      </span>
                    </div>
                  </div>

                  <div>
                    <div className="text-[10px] font-bold text-slate-400 leading-4">
                      생산수
                    </div>
                    <div className="text-[12px] font-mono font-black text-slate-100 leading-5">
                      {k.permeate_m3h != null ? fmt(k.permeate_m3h) : '—'}{' '}
                      <span className="text-[12px] font-mono font-bold text-slate-300">
                        {unitFlow}
                      </span>
                    </div>
                  </div>
                </div>
              </SummaryCard>
            </div>

            {/* KPI 요약 */}
            <div className="grid grid-cols-2 gap-2">
              <KpiCard
                title="회수율"
                icon={<Droplets className="w-4 h-4" />}
                value={k.recovery_pct != null ? pct(k.recovery_pct) : '—'}
              />
              <KpiCard
                title="SEC"
                icon={<Zap className="w-4 h-4" />}
                value={k.sec_kwhm3 != null ? `${fmt(k.sec_kwhm3)} kWh/m³` : '—'}
              />
              <KpiCard
                title="평균 플럭스"
                icon={<Activity className="w-4 h-4" />}
                value={k.flux_lmh != null ? `${fmt(k.flux_lmh)} LMH` : '—'}
              />
              <KpiCard
                title="생산수 TDS"
                icon={<Beaker className="w-4 h-4" />}
                value={k.prod_tds != null ? `${fmt(k.prod_tds)} mg/L` : '—'}
              />
            </div>

            {/* 스테이지 요약 */}
            <div className="rounded border border-slate-800 bg-slate-950/40 overflow-hidden">
              <div className="px-3 py-2 border-b border-slate-800 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Layers className="w-4 h-4 text-slate-300/80" />
                  <span className="text-[12px] font-extrabold text-slate-200">
                    스테이지 요약
                  </span>
                </div>
              </div>

              {stages.length === 0 ? (
                <div className="p-3 text-[12px] text-slate-500">
                  stage_metrics 데이터가 없습니다.
                </div>
              ) : (
                <div className="p-2">
                  <StageMiniTable stages={stages} unitLabels={unitLabels} />
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function KpiCard({
  title,
  value,
  icon,
}: {
  title: string;
  value: React.ReactNode;
  icon?: React.ReactNode;
}) {
  return (
    <div className="rounded border border-slate-800 bg-slate-950/40 p-3">
      <div className="flex items-center justify-between gap-2">
        <div className="min-w-0">
          <div className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">
            {title}
          </div>
          <div className="text-[13px] font-mono font-bold text-slate-100 truncate">
            {value}
          </div>
        </div>
        <div className="text-slate-400 opacity-80">{icon}</div>
      </div>
    </div>
  );
}

function StageMiniTable({
  stages,
  unitLabels,
}: {
  stages: any[];
  unitLabels: any;
}) {
  const uP = unitLabels?.pressure ?? 'bar';
  const uF = unitLabels?.flux ?? 'LMH';

  const rows = stages
    .map((s: any, idx: number) => {
      const stageNo = s?.stage ?? idx + 1;
      const type = s?.module_type ?? '—';

      const flux = s?.flux_lmh ?? s?.jw_avg_lmh ?? null;
      const rec = s?.recovery_pct ?? null;
      const sec = s?.sec_kwhm3 ?? s?.sec_kwh_m3 ?? null;

      const pin = s?.p_in_bar ?? s?.pin_bar ?? s?.pin ?? null;
      const pout = s?.p_out_bar ?? s?.pout_bar ?? s?.pout ?? null;

      const dp = s?.dp_bar ?? s?.delta_p_bar ?? s?.deltaP_bar ?? null;

      return {
        key: `${stageNo}-${type}-${idx}`,
        stageNo,
        type,
        rec,
        flux,
        sec,
        pin,
        pout,
        dp,
      };
    })
    .sort((a: any, b: any) => Number(a.stageNo) - Number(b.stageNo));

  const hasDp = rows.some((r: any) => r.dp != null);

  return (
    <div className="rounded border border-slate-800 overflow-hidden">
      <table className="w-full text-[12px]">
        <thead>
          <tr className="bg-slate-900/60">
            <th className="px-2 py-2 text-left text-[11px] font-extrabold text-slate-400">
              단
            </th>
            <th className="px-2 py-2 text-left text-[11px] font-extrabold text-slate-400">
              종류
            </th>
            <th className="px-2 py-2 text-right text-[11px] font-extrabold text-slate-400">
              회수율
            </th>
            <th className="px-2 py-2 text-right text-[11px] font-extrabold text-slate-400">
              플럭스({uF})
            </th>
            <th className="px-2 py-2 text-right text-[11px] font-extrabold text-slate-400">
              SEC
            </th>
            <th className="px-2 py-2 text-right text-[11px] font-extrabold text-slate-400">
              유입압({uP})
            </th>
            <th className="px-2 py-2 text-right text-[11px] font-extrabold text-slate-400">
              유출압({uP})
            </th>
            {hasDp ? (
              <th className="px-2 py-2 text-right text-[11px] font-extrabold text-slate-400">
                ΔP({uP})
              </th>
            ) : null}
          </tr>
        </thead>
        <tbody>
          {rows.map((r: any) => (
            <tr
              key={r.key}
              className="border-t border-slate-900/60 hover:bg-white/5 transition-colors"
            >
              <td className="px-2 py-2 text-[12px] text-slate-100 font-mono">
                {r.stageNo}
              </td>
              <td className="px-2 py-2 text-[12px] text-slate-100 font-bold">
                {r.type}
              </td>
              <td className="px-2 py-2 text-right text-[12px] text-slate-100 font-mono">
                {r.rec != null ? pct(r.rec) : '—'}
              </td>
              <td className="px-2 py-2 text-right text-[12px] text-slate-100 font-mono">
                {r.flux != null ? fmt(r.flux) : '—'}
              </td>
              <td className="px-2 py-2 text-right text-[12px] text-slate-100 font-mono">
                {r.sec != null ? fmt(r.sec) : '—'}
              </td>
              <td className="px-2 py-2 text-right text-[12px] text-slate-100 font-mono">
                {r.pin != null ? fmt(r.pin) : '—'}
              </td>
              <td className="px-2 py-2 text-right text-[12px] text-slate-100 font-mono">
                {r.pout != null ? fmt(r.pout) : '—'}
              </td>
              {hasDp ? (
                <td className="px-2 py-2 text-right text-[12px] text-slate-100 font-mono">
                  {r.dp != null ? fmt(r.dp) : '—'}
                </td>
              ) : null}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function FlowBuilderInner() {
  const navigate = useNavigate();
  const logic = useFlowLogic();

  const {
    rfRef,
    unitMode,
    scenarioName,
    setScenarioName,
    feed,
    setFeed,
    feedChemistry,
    setFeedChemistry,
    optAuto,
    setOptAuto,
    optMembrane,
    setOptMembrane,
    optSegments,
    setOptSegments,
    optPumpEff,
    setOptPumpEff,
    optErdEff,
    setOptErdEff,
    nodes,
    onNodesChange,
    edges,
    onEdgesChange,
    setEdges,
    loading,
    err,
    data,
    HRRO,
    editorOpen,
    setEditorOpen,
    optionsOpen,
    setOptionsOpen,
    toast,
    canUndo,
    canRedo,
    selEndpoint,
    selUnit,
    stageTypeHint,
    pushToast,
    undo,
    redo,
    onDragStartPalette,
    onDragOver,
    onDrop,
    onConnect,
    onNodeDragStop,
    onEdgesDelete,
    toggleUnits,
    onRun,
    saveLocal,
    loadLocal,
    saveToLibrary,
    resetAll,
    setNodes,
    setSelectedNodeId,
  } = logic;

  const isModalOpen = editorOpen || optionsOpen;
  const resultForViz = useMemo(() => data ?? HRRO, [data, HRRO]);

  const handleNodesChange = useCallback(
    (changes: NodeChange[]) => {
      const filtered = changes.filter((change) => {
        if (change.type !== 'remove') return true;

        const target = nodes.find((n) => n.id === change.id);
        const role = (target?.data as any)?.role;

        if (role === 'feed' || role === 'product') {
          pushToast('🚫 필수 노드(원수/생산수)는 삭제할 수 없습니다.');
          return false;
        }
        return true;
      });

      onNodesChange(filtered);
    },
    [nodes, onNodesChange, pushToast],
  );

  const openReportsPage = useCallback(() => {
    const r = resultForViz || {};
    const scenarioId = r?.scenario_id ?? r?.id ?? null;

    navigate('/reports', {
      state: {
        data: resultForViz,
        mode: 'SYSTEM',
        meta: {
          scenario_id: scenarioId,
          projectName: scenarioName || undefined,
          unitMode,
          source: 'FlowBuilderScreen',
          opened_at: new Date().toISOString(),
        },
      },
    });
  }, [navigate, resultForViz, scenarioName, unitMode]);

  return (
    <div className="flex flex-col w-full h-full bg-slate-950 text-slate-100 font-sans text-xs overflow-hidden">
      {/* Top Toolbar */}
      <div className="flex-none z-30 px-3 py-2 bg-slate-950 border-b border-slate-800">
        <TopBar
          onRun={onRun}
          onAutoLink={() => {
            autoLinkLinear(nodes, setEdges as SetEdgesFn);
            pushToast('자동 연결 완료');
          }}
          onFit={() => rfRef.current?.fitView?.({ padding: 0.2 })}
          onUndo={undo}
          canUndo={canUndo}
          onRedo={redo}
          canRedo={canRedo}
          onSave={saveLocal}
          onLoad={loadLocal}
          onReset={resetAll}
          running={loading}
        >
          <div className="flex items-center gap-2">
            <UnitsToggle mode={unitMode} onChange={toggleUnits} />

            <div className="h-4 w-px bg-slate-800 mx-1" />

            <div className="flex items-center gap-1.5">
              <input
                value={scenarioName}
                onChange={(e) => setScenarioName(e.target.value)}
                className="h-8 rounded border border-slate-700 bg-slate-900 px-2 text-xs w-40 text-slate-100 focus:border-sky-500 outline-none"
                placeholder="시나리오 이름"
              />
              <button
                onClick={saveToLibrary}
                className="h-8 rounded border border-slate-700 bg-slate-800 px-3 text-xs hover:bg-slate-700 text-slate-300"
              >
                저장
              </button>
            </div>

            <button
              onClick={() => setOptionsOpen(true)}
              className="h-8 px-3 rounded border border-slate-700 bg-slate-800 text-xs text-slate-300 hover:bg-slate-700 ml-1"
            >
              옵션
            </button>
          </div>
        </TopBar>
      </div>

      {/* Main Workspace */}
      <div className="flex-1 flex min-h-0 p-2 gap-2">
        {/* Flow Canvas */}
        <div className="flex-1 flex flex-col overflow-hidden rounded border border-slate-800 bg-slate-950 shadow-sm relative">
          <div className="flex-none px-3 min-h-[44px] py-1 border-b border-slate-800 bg-slate-900/50 flex items-center justify-between z-10">
            <div className="flex items-center gap-3">
              <span className="text-xs font-bold text-slate-300 flex items-center gap-1.5 tracking-wider">
                <span className="w-1.5 h-1.5 rounded-full bg-blue-500 shadow-[0_0_5px_rgba(59,130,246,0.5)]" />
                공정 흐름도
              </span>

              <div className="h-3 w-px bg-slate-700" />

              <div className="flex items-center gap-1">
                <PaletteItemBig
                  label="RO"
                  icon={<IconRO className="w-4 h-4" />}
                  onDragStart={(e) => onDragStartPalette('RO', e)}
                />
                <PaletteItemBig
                  label="HRRO"
                  icon={<IconHRRO className="w-4 h-4" />}
                  onDragStart={(e) => onDragStartPalette('HRRO', e)}
                />
                <PaletteItemBig
                  label="UF"
                  icon={<IconUF className="w-4 h-4" />}
                  onDragStart={(e) => onDragStartPalette('UF', e)}
                />
                <PaletteItemBig
                  label="NF"
                  icon={<IconNF className="w-4 h-4" />}
                  onDragStart={(e) => onDragStartPalette('NF', e)}
                />
                <PaletteItemBig
                  label="MF"
                  icon={<IconMF className="w-4 h-4" />}
                  onDragStart={(e) => onDragStartPalette('MF', e)}
                />
              </div>
            </div>
          </div>

          <div className="flex-1 relative bg-slate-950 min-h-0">
            <ReactFlow
              className="bg-slate-950 h-full w-full"
              nodeTypes={nodeTypes}
              nodes={nodes}
              edges={edges}
              onNodesChange={handleNodesChange}
              onEdgesChange={onEdgesChange}
              onConnect={onConnect}
              deleteKeyCode={isModalOpen ? null : (DELETE_KEYS as any)}
              onNodeClick={(_, node) => setSelectedNodeId(node.id)}
              onNodeDoubleClick={(_, node) => {
                setSelectedNodeId(node.id);
                setEditorOpen(true);
              }}
              onDrop={onDrop}
              onDragOver={onDragOver}
              onInit={(inst) => {
                rfRef.current = inst;
              }}
              onNodeDragStop={onNodeDragStop}
              onEdgesDelete={onEdgesDelete}
              onPaneClick={() => {
                setSelectedNodeId(null);
                setEditorOpen(false);
              }}
              fitView
              minZoom={0.1}
              maxZoom={2.0}
              proOptions={{ hideAttribution: true }}
            >
              <Background
                color="#1e293b"
                gap={20}
                size={1}
                className="opacity-30"
              />
              <Controls
                className="!bg-slate-900 !border-slate-700 !shadow-sm !text-slate-400 scale-90 origin-bottom-left"
                showInteractive={false}
              />
            </ReactFlow>
            {loading && <LoadingOverlay />}
          </div>
        </div>

        {/* Result Panel */}
        <ResultsPanel
          loading={loading}
          err={err}
          result={resultForViz}
          onOpenReport={openReportsPage}
        />
      </div>

      <Footer />

      <UnitInspectorModal
        isOpen={editorOpen}
        onClose={() => setEditorOpen(false)}
        selEndpoint={selEndpoint}
        selUnit={selUnit}
        feed={feed}
        setFeed={setFeed}
        feedChemistry={feedChemistry}
        setFeedChemistry={setFeedChemistry}
        unitMode={unitMode}
        setNodes={setNodes as SetNodesFn}
        setEdges={setEdges as SetEdgesFn}
        setSelectedNodeId={setSelectedNodeId}
      />

      <GlobalOptionsModal
        isOpen={optionsOpen}
        onClose={() => setOptionsOpen(false)}
        optAuto={optAuto}
        setOptAuto={setOptAuto}
        optMembrane={optMembrane}
        setOptMembrane={setOptMembrane}
        optSegments={optSegments}
        setOptSegments={setOptSegments}
        optPumpEff={optPumpEff}
        setOptPumpEff={setOptPumpEff}
        optErdEff={optErdEff}
        setOptErdEff={setOptErdEff}
        stageTypeHint={stageTypeHint}
      />

      {toast && (
        <div className="fixed bottom-12 right-6 z-[100] rounded bg-slate-800/95 border border-slate-600 text-slate-100 text-xs px-3 py-2 shadow-2xl flex items-center gap-2 animate-in fade-in slide-in-from-bottom-2">
          {toast}
        </div>
      )}
    </div>
  );
}

export default function FlowBuilderScreen() {
  return (
    <ReactFlowProvider>
      <ErrorBoundary>
        <FlowBuilderInner />
      </ErrorBoundary>
    </ReactFlowProvider>
  );
}
