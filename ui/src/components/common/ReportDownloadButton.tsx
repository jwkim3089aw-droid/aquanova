// ui/src/components/common/ReportDownloadButton.tsx
import React, { useCallback, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { FileDown, ArrowRight, AlertCircle } from 'lucide-react';

interface ReportDownloadButtonProps {
  scenarioId: string;
  disabled?: boolean;
  className?: string;
  outUnits?: 'display' | 'metric';
}

type UIStatus = 'idle' | 'warn' | 'error';

export const ReportDownloadButton: React.FC<ReportDownloadButtonProps> = ({
  scenarioId,
  disabled = false,
  className = '',
  outUnits = 'display',
}) => {
  const navigate = useNavigate();

  // deprecated 안내를 위한 간단 상태
  const [status, setStatus] = useState<UIStatus>('idle');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const isDisabled = useMemo(
    () => disabled || !scenarioId,
    [disabled, scenarioId],
  );

  const handleClick = useCallback(() => {
    try {
      setErrorMessage(null);

      if (!scenarioId) {
        setStatus('error');
        setErrorMessage('scenarioId가 없습니다. 먼저 시뮬레이션을 실행하세요.');
        return;
      }

      // 서버 PDF는 비활성(보류) → UI Detailed Report로 유도
      setStatus('warn');

      navigate('/reports', {
        state: {
          // Reports.tsx가 state.data를 받으면 즉시 렌더링,
          // data가 없으면 scenario 기반으로 로딩/안내하도록 유도
          data: null,
          mode: 'SYSTEM',
          meta: {
            scenario_id: scenarioId,
            out_units: outUnits,
            opened_by: 'ReportDownloadButton(deprecated)',
            message:
              "Server PDF is disabled. Use 'Detailed Report' and client-side PDF export.",
            opened_at: new Date().toISOString(),
          },
        },
      });
    } catch (e: any) {
      setStatus('error');
      setErrorMessage(e?.message || 'Failed to open Detailed Report');
    }
  }, [navigate, outUnits, scenarioId]);

  // 버튼 문구/스타일: “서버 PDF” 대신 “Detailed Report로 이동”
  const label = useMemo(() => {
    if (status === 'error') return 'Open Detailed Report';
    if (status === 'warn') return 'Opening Detailed Report...';
    return 'Detailed Report';
  }, [status]);

  return (
    <div className="flex flex-col items-end">
      <button
        onClick={handleClick}
        disabled={isDisabled}
        className={`
          flex items-center gap-2 px-4 py-2 rounded-md font-medium text-sm transition-colors
          ${
            status === 'error'
              ? 'bg-red-50 text-red-600 border border-red-200 hover:bg-red-100'
              : 'bg-white text-slate-700 border border-slate-300 hover:bg-slate-50 shadow-sm'
          }
          ${isDisabled ? 'opacity-50 cursor-not-allowed' : ''}
          ${className}
        `}
        title="Server-side PDF is disabled. Open Detailed Report and export PDF in the browser."
      >
        {status === 'error' ? (
          <>
            <AlertCircle className="w-4 h-4" />
            <span>{label}</span>
          </>
        ) : (
          <>
            {/* 기존 Download 느낌 유지: FileDown + 이동 아이콘 */}
            <FileDown className="w-4 h-4" />
            <span>{label}</span>
            <ArrowRight className="w-4 h-4 opacity-60" />
          </>
        )}
      </button>

      {/* deprecated 안내: 한 번이라도 클릭하면 경고 문구 표시 */}
      {status === 'warn' && (
        <span className="text-[11px] text-amber-600 mt-1">
          Server PDF is disabled. Export PDF inside Detailed Report.
        </span>
      )}

      {status === 'error' && errorMessage && (
        <span className="text-xs text-red-500 mt-1">{errorMessage}</span>
      )}
    </div>
  );
};
