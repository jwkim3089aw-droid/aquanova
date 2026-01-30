// ui\src\pages\Reports.tsx
import React, { useState, useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import {
  Download,
  Printer,
  ZoomIn,
  ZoomOut,
  FileText,
  ArrowLeft,
  AlertCircle,
  ClipboardCopy,
} from 'lucide-react';
import { usePdfExport } from '../features/simulation/results/pdf/usePdfExport';
import { ReportTemplate } from '../features/simulation/results/pdf/ReportTemplate';

export default function Reports() {
  const location = useLocation();
  const navigate = useNavigate();
  const { exportToPdf, isExporting } = usePdfExport();

  const receivedData = location.state?.data;
  const viewMode = location.state?.mode || 'SYSTEM';
  const meta = location.state?.meta;

  const [zoom, setZoom] = useState(0.9);
  const [reportTitle, setReportTitle] = useState(
    meta?.projectName || 'System Projection Report',
  );

  // ✅ JSON 패널 토글 + textarea ref
  const [showJson, setShowJson] = useState(false);
  const jsonRef = React.useRef<HTMLTextAreaElement | null>(null);

  if (!receivedData) {
    return (
      <div className="flex h-screen items-center justify-center bg-zinc-100 flex-col gap-4">
        <AlertCircle className="w-12 h-12 text-zinc-400" />
        <p className="text-zinc-600 font-medium">No simulation data found.</p>
        <button
          onClick={() => navigate('/')}
          className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 text-sm font-bold"
        >
          Go to Simulation
        </button>
      </div>
    );
  }

  // ✅ ReportTemplate에 실제로 들어갈 data (타이틀/메타 주입)
  const reportData = React.useMemo(() => {
    if (!receivedData) return receivedData;

    // ✅ elementProfile 키 정규화 (snake_case / camelCase 모두 지원)
    const normalizedElementProfile =
      (receivedData as any)?.elementProfile ??
      (receivedData as any)?.element_profile ??
      (receivedData as any)?.element_profile_points ??
      (receivedData as any)?.elementProfilePoints ??
      (receivedData as any)?.stage_metrics?.[0]?.element_profile ??
      (receivedData as any)?.stage_metrics?.[0]?.elementProfile ??
      [];

    return {
      ...receivedData,
      customTitle: reportTitle,
      elementProfile: normalizedElementProfile, // ✅ 항상 존재하도록 주입
      id:
        receivedData.id ??
        meta?.caseId ??
        meta?.id ??
        (receivedData as any).case_id ??
        (receivedData as any).run_id,
      createdAtISO:
        (receivedData as any).createdAtISO ??
        meta?.createdAtISO ??
        meta?.created_at ??
        (receivedData as any).created_at,
    };
  }, [receivedData, reportTitle, meta]);

  // ✅ JSON 문자열(복사용)
  const reportJsonText = React.useMemo(
    () => JSON.stringify(reportData, null, 2),
    [reportData],
  );

  // ✅ 1회만 콘솔 로그 (보험)
  const didLogRef = React.useRef(false);
  useEffect(() => {
    if (!reportData || didLogRef.current) return;
    didLogRef.current = true;

    console.log('REPORT_DATA', reportData);

    console.log(
      'ELEMENT_PROFILE(camel)',
      (reportData as any).elementProfile || [],
    );

    console.log(
      'ELEMENT_PROFILE(snake)',
      (reportData as any).element_profile || [],
    );
  }, [reportData]);

  // 줌 핸들러
  const handleZoom = (delta: number) =>
    setZoom((p) => Math.max(0.5, Math.min(p + delta, 1.5)));

  // ✅ (가장 잘 먹는) 복사: textarea 선택 + execCommand
  const copyViaTextarea = () => {
    setShowJson(true);
    // 다음 tick에 textarea 선택
    setTimeout(() => {
      const el = jsonRef.current;
      if (!el) return;
      el.focus();
      el.select();
      try {
        const ok = document.execCommand('copy');
        if (ok) {
          alert('Copied! (Ctrl+V로 붙여넣기)');
        } else {
          alert('자동 복사 실패. Ctrl+A → Ctrl+C로 복사하세요.');
        }
      } catch {
        alert('자동 복사 실패. Ctrl+A → Ctrl+C로 복사하세요.');
      }
    }, 50);
  };

  // ✅ 다운로드 fallback
  const downloadJson = () => {
    try {
      const blob = new Blob([reportJsonText], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${reportData?.id || 'report'}.json`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch {
      alert('다운로드 실패. JSON 패널에서 직접 복사하세요.');
      setShowJson(true);
    }
  };

  return (
    <div className="flex h-screen bg-[#525659] font-sans text-slate-900 overflow-hidden print:bg-white print:h-auto print:overflow-visible">
      {/* LEFT SIDEBAR */}
      <div className="w-64 bg-white border-r border-slate-300 flex flex-col z-20 print:hidden shadow-xl">
        <div className="h-14 flex items-center px-4 border-b border-slate-200 bg-slate-50 gap-2">
          <button
            onClick={() => navigate(-1)}
            className="p-1 hover:bg-slate-200 rounded text-slate-500"
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

          {/* ✅ JSON 패널 (사이드바에 고정) */}
          <div className="mt-4">
            <button
              onClick={() => setShowJson((v) => !v)}
              className="w-full flex items-center justify-between px-3 py-2 rounded bg-slate-50 text-slate-700 text-xs font-bold border border-slate-200 hover:bg-slate-100"
            >
              <span className="flex items-center gap-2">
                <FileText className="w-4 h-4" /> Report JSON
              </span>
              <span className="text-[10px] text-slate-400">
                {showJson ? 'Hide' : 'Show'}
              </span>
            </button>

            {showJson ? (
              <div className="mt-2">
                <div className="flex gap-2">
                  <button
                    onClick={copyViaTextarea}
                    className="flex-1 flex items-center justify-center gap-2 px-2 py-2 bg-blue-600 hover:bg-blue-700 text-white text-[11px] font-bold rounded"
                  >
                    <ClipboardCopy className="w-4 h-4" />
                    Copy
                  </button>
                  <button
                    onClick={downloadJson}
                    className="flex-1 flex items-center justify-center gap-2 px-2 py-2 bg-slate-700 hover:bg-slate-800 text-white text-[11px] font-bold rounded"
                  >
                    <Download className="w-4 h-4" />
                    Download
                  </button>
                </div>

                <textarea
                  ref={jsonRef}
                  value={reportJsonText}
                  readOnly
                  className="mt-2 w-full h-56 text-[10px] font-mono p-2 rounded border border-slate-200 bg-white text-slate-700"
                />
                <div className="mt-1 text-[10px] text-slate-500 leading-snug">
                  자동 복사가 안 되면 <b>Ctrl+A → Ctrl+C</b>로 직접 복사하세요.
                </div>
              </div>
            ) : null}
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
          </div>

          <div className="flex items-center gap-3">
            <div className="flex items-center bg-zinc-100 rounded p-1">
              <button onClick={() => handleZoom(-0.1)}>
                <ZoomOut className="w-4 h-4 text-zinc-600 mx-2" />
              </button>
              <span className="text-xs font-mono w-8 text-center">
                {Math.round(zoom * 100)}%
              </span>
              <button onClick={() => handleZoom(0.1)}>
                <ZoomIn className="w-4 h-4 text-zinc-600 mx-2" />
              </button>
            </div>

            <button
              onClick={copyViaTextarea}
              className="flex items-center gap-2 px-3 py-2 text-xs font-bold text-slate-700 hover:bg-slate-100 rounded border border-transparent hover:border-slate-300 transition-all"
              title="클립보드 권한 없이도 복사됩니다. (실패 시 JSON 패널에서 Ctrl+A → Ctrl+C)"
            >
              <FileText className="w-4 h-4" /> Copy JSON
            </button>

            <button
              onClick={() => window.print()}
              className="flex items-center gap-2 px-3 py-2 text-xs font-bold text-slate-700 hover:bg-slate-100 rounded border border-transparent hover:border-slate-300 transition-all"
            >
              <Printer className="w-4 h-4" /> Print
            </button>

            <button
              onClick={() =>
                exportToPdf('report-viewer-content', 'AquaNova_Report.pdf')
              }
              disabled={isExporting}
              className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold rounded shadow-md transition-all active:scale-95 disabled:opacity-50"
            >
              {isExporting ? 'Generating...' : 'Download PDF'}
              <Download className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* A4 VIEWER */}
        <div className="flex-1 overflow-auto bg-[#525659] p-8 flex justify-center items-start print:p-0 print:m-0">
          <div
            style={{
              transform: `scale(${zoom})`,
              transformOrigin: 'top center',
              marginBottom: '100px',
            }}
            className="transition-transform duration-200 ease-out print:transform-none flex flex-col gap-8"
          >
            {/* ✅ wrapper에 폭 힌트(선택) : ReportTemplate 내부에도 w-[210mm]가 있지만, 바깥에도 주면 측정 안정성↑ */}
            <div id="report-viewer-content" className="w-[210mm]">
              <ReportTemplate
                data={reportData}
                mode={viewMode}
                elementProfile={(reportData as any)?.elementProfile}
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
