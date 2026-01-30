// ui/src/components/common/ReportDownloadButton.tsx
import React, { useState } from 'react';
// ✅ [수정] 경로가 얕아졌으므로 ../ 개수가 줄어듭니다.
import {
  requestReportGeneration,
  getReportStatus,
  downloadReportBlob,
} from '../../api/simulation';

import { FileDown, Loader2, AlertCircle } from 'lucide-react';

interface ReportDownloadButtonProps {
  scenarioId: string;
  disabled?: boolean;
  className?: string;
}

export const ReportDownloadButton: React.FC<ReportDownloadButtonProps> = ({
  scenarioId,
  disabled = false,
  className = '',
}) => {
  const [status, setStatus] = useState<
    'idle' | 'requesting' | 'processing' | 'downloading' | 'error'
  >('idle');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const handleDownload = async () => {
    if (!scenarioId) return;

    try {
      setStatus('requesting');
      setErrorMessage(null);

      // 1. 리포트 생성 요청
      const jobId = await requestReportGeneration(scenarioId, 'display');

      setStatus('processing');

      // 2. 폴링
      const pollInterval = setInterval(async () => {
        try {
          const jobStatus = await getReportStatus(jobId);

          if (jobStatus.status === 'succeeded') {
            clearInterval(pollInterval);
            await downloadFile(jobId);
          } else if (jobStatus.status === 'failed') {
            clearInterval(pollInterval);
            setStatus('error');
            setErrorMessage(
              jobStatus.error_message || 'Report generation failed',
            );
          }
        } catch (e) {
          clearInterval(pollInterval);
          setStatus('error');
          setErrorMessage('Network error checking status');
        }
      }, 1000);
    } catch (error) {
      console.error(error);
      setStatus('error');
      setErrorMessage('Failed to start report job');
    }
  };

  const downloadFile = async (jobId: string) => {
    try {
      setStatus('downloading');
      const blob = await downloadReportBlob(jobId);

      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      const dateStr = new Date().toISOString().slice(0, 10);
      link.setAttribute('download', `AquaNova_Report_${dateStr}.pdf`);
      document.body.appendChild(link);
      link.click();

      link.remove();
      window.URL.revokeObjectURL(url);

      setStatus('idle');
    } catch (error) {
      console.error(error);
      setStatus('error');
      setErrorMessage('Download failed');
    }
  };

  return (
    <div className="flex flex-col items-end">
      <button
        onClick={handleDownload}
        disabled={disabled || (status !== 'idle' && status !== 'error')}
        className={`
          flex items-center gap-2 px-4 py-2 rounded-md font-medium text-sm transition-colors
          ${
            status === 'error'
              ? 'bg-red-50 text-red-600 border border-red-200 hover:bg-red-100'
              : 'bg-white text-slate-700 border border-slate-300 hover:bg-slate-50 shadow-sm'
          }
          ${disabled || (status !== 'idle' && status !== 'error') ? 'opacity-50 cursor-not-allowed' : ''}
          ${className}
        `}
      >
        {status === 'idle' && (
          <>
            <FileDown className="w-4 h-4" />
            <span>Download PDF</span>
          </>
        )}
        {(status === 'requesting' || status === 'processing') && (
          <>
            <Loader2 className="w-4 h-4 animate-spin text-blue-500" />
            <span>Generating...</span>
          </>
        )}
        {status === 'downloading' && (
          <>
            <Loader2 className="w-4 h-4 animate-spin text-green-500" />
            <span>Downloading...</span>
          </>
        )}
        {status === 'error' && (
          <>
            <AlertCircle className="w-4 h-4" />
            <span>Retry Download</span>
          </>
        )}
      </button>

      {status === 'error' && errorMessage && (
        <span className="text-xs text-red-500 mt-1">{errorMessage}</span>
      )}
    </div>
  );
};
