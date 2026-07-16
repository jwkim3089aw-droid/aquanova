// ui/src/features/simulation/results/pdf/panels/UfDetailsPanel.tsx
import React from 'react';
import { fmt, pct } from '../utils';
import { UnitLabels } from '../types';

export function UfDetailsPanel({
  stage,
  systemKpi,
  feedFlow,
  permFlow,
  u,
}: {
  stage?: any;
  systemKpi?: any;
  feedFlow?: number;
  permFlow?: number;
  u: UnitLabels;
}) {
  if (!stage) return null;

  // 🟢 모듈 타입 동적 할당 (MF / UF)
  const moduleType = String(
    stage.module_type || stage.type || 'UF',
  ).toUpperCase();

  // 🟢 백엔드 데이터 매핑 (역산 솔버 최신 규격 완벽 반영)
  const recovery = stage.recovery_pct ?? systemKpi?.recovery_pct;
  const flux = stage.flux_lmh ?? systemKpi?.flux_lmh;
  const tmp = stage.tmp_bar ?? stage.ndp_bar ?? systemKpi?.ndp_bar;
  const sec = stage.sec_kwhm3 ?? systemKpi?.sec_kwhm3;

  // 🟦 원하시던 바로 그 촘촘한 WAVE 스타일 가로형 테이블 테마!
  const thClass =
    'py-1.5 px-3 text-[10px] font-bold text-slate-800 border border-slate-400 bg-slate-200 text-left tracking-wider w-1/6';
  const tdClass =
    'py-1.5 px-3 text-[11px] font-mono font-bold text-slate-900 border border-slate-300 bg-white tabular-nums w-1/6';

  return (
    <div className="w-full print:break-inside-avoid mb-6">
      <div className="text-[12px] font-bold text-slate-800 mb-2 pl-2 border-l-2 border-slate-800 uppercase tracking-wider">
        {moduleType} 스테이지 {stage.stage ?? 1} - 핵심 성능 지표 (Key
        Performance Indicators)
      </div>
      <table className="w-full border-collapse border-2 border-slate-500">
        <tbody>
          <tr>
            <th className={thClass}>유입 유량 (Feed Flow)</th>
            <td className={tdClass}>
              {fmt(feedFlow)} {u.flow}
            </td>

            <th className={thClass}>생산 유량 (Product Flow)</th>
            {/* 핵심 생산수 지표 딥 블루 하이라이트 */}
            <td className={`${tdClass} text-blue-800 bg-blue-50/50`}>
              {fmt(permFlow)} {u.flow}
            </td>

            <th className={thClass}>회수율 (Recovery)</th>
            <td className={`${tdClass} text-blue-800 bg-blue-50/50`}>
              {pct(recovery)}
            </td>
          </tr>
          <tr>
            <th className={thClass}>운전 플럭스 (Operating Flux)</th>
            <td className={tdClass}>
              {fmt(flux)} {u.flux}
            </td>

            <th className={thClass}>막간차압 (TMP)</th>
            <td className={tdClass}>
              {fmt(tmp)} {u.pressure}
            </td>

            <th className={thClass}>비에너지 (SEC)</th>
            <td className={tdClass}>{fmt(sec)} kWh/m³</td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}
