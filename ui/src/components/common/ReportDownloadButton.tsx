// ui/src/components/common/ReportDownloadButton.tsx
import React, { useCallback, useMemo, useState } from 'react';
import { FileDown, Loader2, AlertCircle } from 'lucide-react';

interface ReportDownloadButtonProps {
  scenarioId: string;
  disabled?: boolean;
  className?: string;
  outUnits?: 'display' | 'metric';
}

type UIStatus = 'idle' | 'loading' | 'error' | 'success';

export const ReportDownloadButton: React.FC<ReportDownloadButtonProps> = ({
  scenarioId,
  disabled = false,
  className = '',
  outUnits = 'display',
}) => {
  const [status, setStatus] = useState<UIStatus>('idle');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const isDisabled = useMemo(
    () => disabled || !scenarioId || status === 'loading',
    [disabled, scenarioId, status],
  );

  const handleDownload = useCallback(async () => {
    if (!scenarioId) return;

    try {
      setStatus('loading');
      setErrorMessage(null);

      // 1. 워커에 리포트 생성 작업(Job) 큐 등록
      const enqueueRes = await fetch(
        `/api/v1/reports/enqueue?out_units=${outUnits}`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ scenario_id: scenarioId }),
        },
      );

      if (!enqueueRes.ok) {
        const errorData = await enqueueRes.json().catch(() => ({}));
        throw new Error(
          errorData.detail || 'Failed to start report generation',
        );
      }

      const { job_id } = await enqueueRes.json();

      // 2. 작업이 완료될 때까지 Polling (2초 간격)
      let isReady = false;
      while (!isReady) {
        await new Promise((resolve) => setTimeout(resolve, 2000));

        const statusRes = await fetch(`/api/v1/reports/${job_id}`);
        if (!statusRes.ok) throw new Error('Failed to check report status');

        const statusData = await statusRes.json();

        if (statusData.status === 'succeeded') {
          isReady = true;
        } else if (statusData.status === 'failed') {
          throw new Error(
            statusData.error_message || 'Report generation failed in worker',
          );
        }
      }

      // 3. 완료된 PDF 다운로드 처리 (Blob)
      const downloadRes = await fetch(`/api/v1/reports/${job_id}/download`);
      if (!downloadRes.ok) throw new Error('Failed to download PDF');

      const blob = await downloadRes.blob();
      const downloadUrl = window.URL.createObjectURL(blob);

      const a = document.createElement('a');
      a.href = downloadUrl;
      a.download = `AquaNova_Report_${scenarioId.slice(0, 8)}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(downloadUrl);

      setStatus('success');

      // 3초 후 버튼 상태 초기화
      setTimeout(() => setStatus('idle'), 3000);
    } catch (err: any) {
      console.error('Report Generation Error:', err);
      setStatus('error');
      setErrorMessage(err.message || 'An unexpected error occurred.');
    }
  }, [scenarioId, outUnits]);

  return (
    <div className="flex flex-col items-end">
      <button
        onClick={handleDownload}
        disabled={isDisabled}
        className={`
          flex items-center justify-center gap-2 px-4 py-2 rounded-md font-medium text-sm transition-all
          min-w-[160px] shadow-sm
          ${status === 'error' ? 'bg-red-50 text-red-600 border border-red-200 hover:bg-red-100' : ''}
          ${status === 'success' ? 'bg-green-50 text-green-700 border border-green-200' : ''}
          ${status === 'idle' ? 'bg-[#0F4C81] text-white border border-transparent hover:bg-blue-900' : ''}
          ${status === 'loading' ? 'bg-slate-100 text-slate-500 border border-slate-300 cursor-wait' : ''}
          ${isDisabled && status !== 'loading' ? 'opacity-50 cursor-not-allowed' : ''}
          ${className}
        `}
      >
        {status === 'loading' && (
          <>
            <Loader2 className="w-4 h-4 animate-spin" />
            <span>Generating...</span>
          </>
        )}
        {status === 'success' && (
          <>
            <FileDown className="w-4 h-4" />
            <span>Downloaded!</span>
          </>
        )}
        {status === 'error' && (
          <>
            <AlertCircle className="w-4 h-4" />
            <span>Failed</span>
          </>
        )}
        {status === 'idle' && (
          <>
            <FileDown className="w-4 h-4" />
            <span>Download Report</span>
          </>
        )}
      </button>

      {/* 에러 메시지 표시 */}
      {status === 'error' && errorMessage && (
        <span className="text-xs text-red-500 mt-2 max-w-xs text-right break-words">
          {errorMessage}
        </span>
      )}
    </div>
  );
};
