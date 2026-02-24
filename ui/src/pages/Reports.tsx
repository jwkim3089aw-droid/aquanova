// ui/src/pages/Reports.tsx
import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import {
  Download,
  Printer,
  ZoomIn,
  ZoomOut,
  ArrowLeft,
  AlertCircle,
  FileText,
  RefreshCcw,
  ClipboardCopy,
  CheckCircle2,
  LayoutList,
} from 'lucide-react';

import { usePdfExport } from '../features/simulation/results/pdf/usePdfExport';
import { ReportTemplate } from '../features/simulation/results/pdf/ReportTemplate';

type ViewMode = 'SYSTEM' | 'STAGE';

function safeMode(v: any): ViewMode {
  return v === 'STAGE' ? 'STAGE' : 'SYSTEM';
}

function parseMaybeJson(v: any) {
  if (v == null) return null;
  if (typeof v === 'string') {
    try {
      return JSON.parse(v);
    } catch {
      return v;
    }
  }
  return v;
}

function pickFirstObject(...candidates: any[]) {
  for (const c of candidates) {
    const v = parseMaybeJson(c);
    if (v && typeof v === 'object') return v;
  }
  return null;
}

function apiBase() {
  const v = (import.meta as any)?.env?.VITE_API_URL;
  if (!v) return '';
  return String(v).replace(/\/+$/, '');
}

async function fetchJson(url: string, init?: RequestInit) {
  const res = await fetch(url, {
    credentials: 'include',
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers || {}),
    },
  });

  const text = await res.text();
  let data: any = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = text;
  }

  return { res, data };
}

async function copyTextToClipboard(text: string) {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text);
    return;
  }
  const ta = document.createElement('textarea');
  ta.value = text;
  ta.style.position = 'fixed';
  ta.style.left = '-9999px';
  ta.style.top = '0';
  document.body.appendChild(ta);
  ta.focus();
  ta.select();
  const ok = document.execCommand('copy');
  document.body.removeChild(ta);
  if (!ok) throw new Error('copy failed');
}

const A4_W_PX = 794;
const A4_MIN_H_PX = 1123;

export default function Reports() {
  const location = useLocation();
  const navigate = useNavigate();
  const { exportToPdf, isExporting } = usePdfExport();

  const viewMode: ViewMode = safeMode((location.state as any)?.mode);
  const meta = (location.state as any)?.meta ?? {};

  const receivedDataFromState = (location.state as any)?.data ?? null;
  const [receivedData, setReceivedData] = useState<any>(receivedDataFromState);

  const scenarioId: string | null = meta?.scenario_id
    ? String(meta.scenario_id)
    : null;

  const [isLoading, setIsLoading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [zoom, setZoom] = useState(1.0);
  const [compact, setCompact] = useState(true);

  const [reportTitle, setReportTitle] = useState(
    meta?.projectName || 'System Projection Report',
  );

  const [copyState, setCopyState] = useState<
    'idle' | 'copying' | 'copied' | 'error'
  >('idle');

  const didLogRef = useRef(false);

  const reportData = useMemo(() => {
    if (!receivedData) return null;
    const d: any = receivedData ?? {};

    const normalizedElementProfile =
      d?.elementProfile ??
      d?.element_profile ??
      d?.element_profile_points ??
      d?.elementProfilePoints ??
      d?.stage_metrics?.[0]?.element_profile ??
      d?.stage_metrics?.[0]?.elementProfile ??
      [];

    const id =
      d?.id ??
      meta?.caseId ??
      meta?.id ??
      d?.case_id ??
      d?.run_id ??
      d?.scenario_id ??
      scenarioId;

    const createdAtISO =
      d?.createdAtISO ??
      meta?.createdAtISO ??
      meta?.created_at ??
      d?.created_at;

    return {
      ...d,
      customTitle: reportTitle,
      elementProfile: normalizedElementProfile,
      id,
      createdAtISO,
    };
  }, [receivedData, reportTitle, meta, scenarioId]);

  useEffect(() => {
    if (!reportData || didLogRef.current) return;
    didLogRef.current = true;
    console.log('REPORT_DATA', reportData);
  }, [reportData]);

  const handleZoom = (delta: number) =>
    setZoom((p) => Math.max(0.6, Math.min(p + delta, 1.6)));

  const handleCopy = async () => {
    try {
      setCopyState('copying');
      const el = document.getElementById('report-viewer-content');
      const text = (el?.innerText || '').trim();
      if (!text) throw new Error('empty');
      await copyTextToClipboard(text);
      setCopyState('copied');
      window.setTimeout(() => setCopyState('idle'), 900);
    } catch (e) {
      console.error(e);
      setCopyState('error');
      window.setTimeout(() => setCopyState('idle'), 900);
      alert('복사 실패. 브라우저 권한/보안 설정을 확인하세요.');
    }
  };

  useEffect(() => {
    if (receivedDataFromState) return;
    if (!scenarioId) return;

    let cancelled = false;

    const run = async () => {
      setIsLoading(true);
      setLoadError(null);

      try {
        const base = apiBase();

        const scenarioUrls = [
          `${base}/api/v1/scenarios/${scenarioId}`,
          `${base}/api/v1/scenario/${scenarioId}`,
          `${base}/api/v1/simulation/scenarios/${scenarioId}`,
        ];

        let scenarioObj: any = null;
        let lastStatus: number | null = null;

        for (const u of scenarioUrls) {
          const { res, data } = await fetchJson(u, { method: 'GET' });
          lastStatus = res.status;

          if (res.ok) {
            scenarioObj = data;
            break;
          }

          if ([404, 405].includes(res.status)) continue;

          if ([401, 403].includes(res.status)) {
            throw new Error(
              '인증이 필요합니다. 로그인/쿠키 상태를 확인하세요.',
            );
          }
        }

        if (!scenarioObj) {
          throw new Error(
            `Scenario 로드 실패 (${scenarioId}). Last status: ${lastStatus ?? 'unknown'}`,
          );
        }

        const scenarioResult =
          pickFirstObject(
            scenarioObj?.result_json,
            scenarioObj?.result,
            scenarioObj?.output_json,
            scenarioObj?.output,
            scenarioObj?.simulation_result,
            scenarioObj?.data,
          ) ?? null;

        const maybeTitle =
          scenarioObj?.name ||
          scenarioObj?.scenario_name ||
          scenarioObj?.scenarioName ||
          meta?.projectName;

        if (!cancelled && maybeTitle) setReportTitle(String(maybeTitle));

        if (scenarioResult && typeof scenarioResult === 'object') {
          if (!cancelled) setReceivedData(scenarioResult);
          return;
        }

        const inputPayload =
          pickFirstObject(
            scenarioObj?.input_json,
            scenarioObj?.input,
            scenarioObj?.payload,
          ) ?? null;

        if (!inputPayload) {
          throw new Error(
            'Scenario는 로드되었지만 result_json/output_json도 없고 input_json도 없습니다.',
          );
        }

        const runUrl = `${base}/api/v1/simulation/run`;
        const { res: runRes, data: runData } = await fetchJson(runUrl, {
          method: 'POST',
          body: JSON.stringify(inputPayload),
        });

        if (!runRes.ok) {
          const msg =
            typeof runData === 'string'
              ? runData
              : runData?.detail || runData?.message || JSON.stringify(runData);
          throw new Error(`Simulation re-run failed: ${msg}`);
        }

        if (!cancelled) setReceivedData(runData);
      } catch (e: any) {
        if (!cancelled) {
          setLoadError(
            e?.message || 'scenario_id로 리포트를 불러오지 못했습니다.',
          );
        }
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    };

    run();
    return () => {
      cancelled = true;
    };
  }, [scenarioId, receivedDataFromState, meta?.projectName]);

  if (!reportData && !scenarioId) {
    return (
      <div className="flex h-screen items-center justify-center bg-zinc-100 flex-col gap-4">
        <AlertCircle className="w-12 h-12 text-zinc-400" />
        <p className="text-zinc-600 font-medium">No report data found.</p>
        <button
          onClick={() => navigate('/')}
          className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 text-sm font-bold"
        >
          Go to Simulation
        </button>
      </div>
    );
  }

  if (!reportData && scenarioId) {
    return (
      <div className="flex h-screen items-center justify-center bg-zinc-100 flex-col gap-4 px-6">
        <div className="p-4 rounded-full bg-white border border-slate-200 shadow-sm">
          <FileText className="w-8 h-8 text-slate-400" />
        </div>

        <div className="text-center max-w-xl">
          <p className="text-slate-800 font-bold text-lg">Detailed Report</p>
          <p className="text-slate-600 text-sm mt-2 leading-relaxed">
            scenario_id로 리포트 데이터를 불러오는 중입니다.
          </p>
          <div className="mt-2 text-xs text-slate-500">
            scenario_id: <span className="font-mono">{scenarioId}</span>
          </div>

          {isLoading ? (
            <div className="mt-4 text-sm text-slate-600">Loading...</div>
          ) : null}

          {loadError ? (
            <div className="mt-4 text-sm text-rose-600">{loadError}</div>
          ) : null}
        </div>

        <div className="flex gap-2">
          <button
            onClick={() => navigate(-1)}
            className="px-4 py-2 bg-white border border-slate-300 text-slate-700 rounded hover:bg-slate-50 text-sm font-bold"
          >
            Back
          </button>

          <button
            onClick={() => navigate(0)}
            className="px-4 py-2 bg-slate-800 text-white rounded hover:bg-slate-900 text-sm font-bold flex items-center gap-2"
            disabled={isLoading}
          >
            <RefreshCcw className="w-4 h-4" />
            Retry
          </button>

          <button
            onClick={() => navigate('/')}
            className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 text-sm font-bold"
          >
            Go to Simulation
          </button>
        </div>
      </div>
    );
  }

  const paperW = Math.round(A4_W_PX * zoom);
  const paperMinH = Math.round(A4_MIN_H_PX * zoom);

  return (
    <div className="flex h-screen bg-[#525659] font-sans text-slate-900 overflow-hidden print:bg-white print:h-auto print:overflow-visible">
      {/* ✅ 추가/수정: Print 최적화 CSS */}
      <style>{`
        #report-viewer-content.compact pre {
          max-height: 220px;
          overflow: auto;
          border: 1px solid #e2e8f0;
          background: #f8fafc;
          border-radius: 10px;
          padding: 12px;
        }
        #report-viewer-content.compact pre:before {
          content: "RAW DEBUG (collapsed)";
          display: block;
          font-weight: 700;
          font-size: 11px;
          color: #64748b;
          margin-bottom: 8px;
        }
        #report-viewer-content table {
          width: 100%;
          border-collapse: collapse;
        }
        #report-viewer-content th, #report-viewer-content td {
          word-break: break-word;
        }
        .paper {
          background: #fff;
          border-radius: 12px;
          box-shadow: 0 18px 60px rgba(0,0,0,0.22);
          border: 1px solid rgba(15, 23, 42, 0.12);
        }

        /* ✅ 핵심: 인쇄 전용 CSS (Zoom 무시, 배경색 강제, 여백 제어) */
        @media print {
          @page {
            size: A4 portrait;
            margin: 0;
          }
          body {
            margin: 0;
            -webkit-print-color-adjust: exact !important;
            print-color-adjust: exact !important;
          }
          .paper {
            box-shadow: none !important;
            border: none !important;
            border-radius: 0 !important;
          }

          /* 요소 분할 방지 */
          table, tr, td, th, img, svg, canvas, pre, .section-wrapper {
            page-break-inside: avoid;
            break-inside: avoid;
          }
          h1, h2, h3, h4, h5 {
            page-break-after: avoid;
            break-after: avoid;
          }

          /* Zoom 인라인 스타일 강제 무력화 */
          #report-viewer-content {
            transform: none !important;
            width: 100% !important;
            min-height: auto !important;
            margin: 0 !important;
          }
        }
      `}</style>

      {/* LEFT SIDEBAR */}
      <div className="w-64 bg-white border-r border-slate-300 flex flex-col z-20 print:hidden shadow-xl">
        <div className="h-14 flex items-center px-4 border-b border-slate-200 bg-slate-50 gap-2">
          <button
            onClick={() => navigate(-1)}
            className="p-1 hover:bg-slate-200 rounded text-slate-500"
            title="Back"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
          <span className="font-bold text-slate-700 text-sm">
            Back to Builder
          </span>
        </div>

        <div className="p-4">
          <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-2">
            Structure
          </div>
          <div className="space-y-1">
            <button className="w-full text-left px-3 py-2 rounded bg-blue-50 text-blue-700 text-xs font-bold border border-blue-100">
              1. Main Report
            </button>
          </div>
          <div className="mt-4 text-[11px] text-slate-500 leading-relaxed">
            • PDF는 화면 렌더링 기반으로 생성됩니다.
            <br />• Copy는 리포트의 <b>텍스트</b>만 복사합니다(차트 제외).
          </div>
        </div>
      </div>

      {/* MAIN CONTENT */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* TOP TOOLBAR */}
        <div className="h-14 bg-white border-b border-zinc-300 px-6 flex items-center justify-between shadow-sm z-10 print:hidden">
          <div className="flex items-center gap-3">
            <input
              value={reportTitle}
              onChange={(e) => setReportTitle(e.target.value)}
              className="text-lg font-bold text-slate-800 bg-transparent hover:bg-slate-100 focus:bg-white focus:ring-2 focus:ring-blue-500 rounded px-2 py-1 outline-none transition-all w-80"
            />
            <div className="hidden md:flex items-center gap-2 text-xs text-slate-500">
              {scenarioId ? (
                <span className="font-mono">scenario_id: {scenarioId}</span>
              ) : null}
            </div>
          </div>

          <div className="flex items-center gap-3">
            <div className="flex items-center bg-zinc-100 rounded p-1">
              <button onClick={() => handleZoom(-0.1)} title="Zoom out">
                <ZoomOut className="w-4 h-4 text-zinc-600 mx-2" />
              </button>
              <span className="text-xs font-mono w-10 text-center">
                {Math.round(zoom * 100)}%
              </span>
              <button onClick={() => handleZoom(0.1)} title="Zoom in">
                <ZoomIn className="w-4 h-4 text-zinc-600 mx-2" />
              </button>
            </div>

            <button
              onClick={() => setCompact((v) => !v)}
              className={`flex items-center gap-2 px-3 py-2 text-xs font-bold rounded border transition-all
                ${
                  compact
                    ? 'bg-slate-900 text-white border-slate-900 hover:bg-black'
                    : 'bg-white text-slate-700 border-slate-200 hover:bg-slate-100'
                }`}
              title="Compact mode (RAW debug blocks collapsed)"
            >
              <LayoutList className="w-4 h-4" />
              {compact ? 'Compact' : 'Full'}
            </button>

            <button
              onClick={handleCopy}
              className={`flex items-center gap-2 px-3 py-2 text-xs font-bold rounded border transition-all
                ${
                  copyState === 'copied'
                    ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                    : copyState === 'copying'
                      ? 'bg-slate-100 text-slate-700 border-slate-200'
                      : 'bg-white text-slate-700 border-slate-200 hover:bg-slate-100'
                }`}
              title="Copy report text"
            >
              {copyState === 'copied' ? (
                <CheckCircle2 className="w-4 h-4" />
              ) : (
                <ClipboardCopy className="w-4 h-4" />
              )}
              {copyState === 'copied'
                ? 'Copied'
                : copyState === 'copying'
                  ? 'Copying...'
                  : 'Copy'}
            </button>

            <button
              onClick={() => window.print()}
              className="flex items-center gap-2 px-3 py-2 text-xs font-bold text-slate-700 hover:bg-slate-100 rounded border border-transparent hover:border-slate-300 transition-all"
              title="Print"
            >
              <Printer className="w-4 h-4" /> Print
            </button>

            <button
              onClick={() =>
                exportToPdf('report-viewer-content', 'AquaNova_Report.pdf')
              }
              disabled={isExporting}
              className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold rounded shadow-md transition-all active:scale-95 disabled:opacity-50"
              title="Download PDF"
            >
              {isExporting ? 'Generating...' : 'Download PDF'}
              <Download className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* VIEWER */}
        <div className="flex-1 overflow-auto bg-[#525659] p-8 print:p-0 print:m-0">
          <div className="min-w-max flex justify-center">
            <div style={{ width: paperW, minHeight: paperMinH }}>
              <div className="paper">
                <div
                  id="report-viewer-content"
                  className={`${compact ? 'compact' : ''} flex flex-col gap-8`}
                  style={{
                    width: A4_W_PX,
                    minHeight: A4_MIN_H_PX,
                    transform: `scale(${zoom})`,
                    transformOrigin: 'top left',
                  }}
                >
                  <div className="print:w-[210mm] print:min-h-[297mm]">
                    <ReportTemplate
                      data={reportData}
                      mode={viewMode}
                      elementProfile={(reportData as any)?.elementProfile}
                    />
                  </div>
                </div>
              </div>
              <div className="h-12 print:hidden" />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
