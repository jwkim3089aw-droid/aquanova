// ui/src/features/simulation/results/pdf/panels/SystemWarningsPanel.tsx
import React from 'react';
import { safeArr, safeObj } from '../utils';

// 🛑 [에러 해결 방어 코드] 객체 형태({min, max} 등)를 안전하게 문자열로 변환
function formatWarningValue(val: any): string {
  if (val == null || val === '-') return '-';
  if (typeof val === 'number') return val.toFixed(2);
  if (typeof val === 'object') {
    // 백엔드에서 { min: 0, max: 10 } 형태로 내려줄 경우
    if ('min' in val && 'max' in val) return `${val.min} ~ ${val.max}`;
    if ('max' in val) return `Max ${val.max}`;
    if ('min' in val) return `Min ${val.min}`;
    return JSON.stringify(val); // 그 외 알 수 없는 객체일 경우 강제 문자열 변환
  }
  return String(val);
}

// 데이터 파싱 함수 (한국어 적용)
function collectWarnings(stages: any[], globalWarnings?: any[]) {
  const out: any[] = [];

  // 1. 글로벌 경고 처리
  if (globalWarnings && Array.isArray(globalWarnings)) {
    globalWarnings.forEach((gw) => {
      if (typeof gw === 'string') {
        out.push({
          stage: '시스템 공통',
          type: 'Global',
          message: gw,
          value: '-',
          limit: '-',
          unit: '',
        });
      } else if (gw && typeof gw === 'object') {
        out.push({
          stage: '시스템 공통',
          type: 'Global',
          message: String(gw.message ?? gw.msg ?? '-'),
          value: gw.value ?? '-',
          limit: gw.limit ?? '-',
          unit: gw.unit ?? '',
        });
      }
    });
  }

  // 2. 스테이지별 Violation 파싱
  if (stages && Array.isArray(stages)) {
    stages.forEach((s, i) => {
      const stageNo = s?.stage ?? i + 1;
      const moduleType = String(
        s?.module_type ?? s?.type ?? s?.membrane_model ?? 'RO',
      ).toUpperCase();
      const chem = safeObj(s?.chemistry);
      const vlist = safeArr(chem?.violations ?? []);

      vlist.forEach((v) => {
        out.push({
          stage: `스테이지 ${stageNo}`,
          type: moduleType,
          message: String(v?.message ?? v?.msg ?? v?.key ?? '-'),
          value: v?.value ?? '-',
          limit: v?.limit ?? '-',
          unit: v?.unit ?? '',
        });
      });
    });
  }

  return out;
}

export function SystemWarningsPanel({
  stages = [],
  globalWarnings = [],
}: {
  stages?: any[];
  globalWarnings?: any[];
}) {
  const rows = collectWarnings(stages, globalWarnings);
  const maxRows = 30;
  const slice = rows.slice(0, maxRows);

  // 🛑 경고가 없을 때: 건조하고 명확한 한국어 안내
  if (!slice.length) {
    return (
      <div className="w-full print:break-inside-avoid">
        <table className="w-full border-collapse border-2 border-slate-500">
          <tbody>
            <tr>
              <td className="py-2 px-3 w-28 text-center border border-slate-300 bg-slate-100 text-[11px] font-extrabold text-slate-600 tracking-widest align-middle">
                경고 없음
              </td>
              <td className="py-2 px-4 border border-slate-300 text-[11px] font-semibold text-slate-800 bg-white align-middle">
                감지된 시스템 경고가 없습니다. 시스템이 설계 지침 내에서
                정상적으로 운전 중입니다.
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    );
  }

  // WAVE 스타일 테이블 클래스 정의
  const thClass =
    'py-1.5 px-3 text-[10px] font-bold text-slate-800 border border-slate-400 bg-slate-200 text-center tracking-wider';
  const tdClass =
    'py-1.5 px-3 text-[11px] text-slate-900 border border-slate-300 bg-white text-center tabular-nums';
  const msgClass =
    'py-1.5 px-3 text-[11px] font-semibold text-slate-800 border border-slate-300 bg-white text-left';

  // ⚠️ 경고가 있을 때: 고밀도 엔지니어링 표
  return (
    <div className="w-full print:break-inside-avoid">
      <div className="flex items-center justify-between mb-2 pl-2 border-l-2 border-rose-800">
        <div className="text-[12px] font-bold text-slate-800 tracking-wider">
          시스템 설계 지침 위반 내역
        </div>
        {rows.length > maxRows && (
          <div className="text-[10px] text-slate-500 font-medium">
            (최대 {maxRows}개 표시 중)
          </div>
        )}
      </div>

      <table className="w-full border-collapse border-2 border-slate-500">
        <thead>
          <tr>
            <th className={thClass}>해당 구간</th>
            <th className={thClass}>공정 타입</th>
            <th className={thClass} style={{ textAlign: 'left' }}>
              경고 메시지
            </th>
            <th className={thClass}>현재값</th>
            <th className={thClass}>제한값 (Limit)</th>
          </tr>
        </thead>
        <tbody>
          {slice.map((r, i) => {
            // 🛑 여기서 에러를 유발하던 객체를 안전하게 문자열로 변환하여 렌더링
            const displayVal = formatWarningValue(r.value);
            const displayLim = formatWarningValue(r.limit);
            const unitText = r.unit && r.unit !== '-' ? ` ${r.unit}` : '';

            return (
              <tr key={i} className="hover:bg-rose-50/30">
                <td
                  className={`${tdClass} font-bold text-slate-700 bg-slate-50`}
                >
                  {r.stage}
                </td>
                <td className={tdClass}>{r.type}</td>
                <td className={`${msgClass} text-rose-800`}>{r.message}</td>
                <td className={tdClass}>
                  {displayVal !== '-' ? `${displayVal}${unitText}` : '-'}
                </td>
                <td className={`${tdClass} text-slate-500`}>
                  {displayLim !== '-' ? `${displayLim}${unitText}` : '-'}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
