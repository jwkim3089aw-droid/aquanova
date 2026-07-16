// ui/src/features/simulation/results/pdf/panels/HRROCoreStatusTable.tsx
import React from 'react';
import { fmt } from '../utils';
import { UnitLabels } from '../types';

export function HRROCoreStatusTable({
  stage,
  u,
}: {
  stage: any;
  u: UnitLabels;
}) {
  if (!stage) return null;

  // 🟢 JSON 구조에 맞춘 정확한 다중 키 매핑 (엔진의 최신 물리 기호 우선 적용)
  const targetFlux = stage.design_flux_lmh ?? stage.target_flux_lmh;
  const achievedFlux = stage.flux_lmh ?? stage.jw_avg_lmh;

  const pIn = stage.chemistry?.model?.p_in_bar_max ?? stage.p_in_bar;
  const pOut = stage.p_out_bar;
  const dp =
    stage.chemistry?.model?.dp_total_bar ??
    (pIn != null && pOut != null ? pIn - pOut : null);
  const ndp = stage.ndp_bar;

  const sec = stage.sec_kwhm3 ?? stage.sec_kwh_m3 ?? stage.SEC;
  const pumpEff =
    stage.pump_eff ??
    stage.pump_efficiency ??
    stage.chemistry?.physics_parameters?.pump_eff ??
    80;

  // 🟦 원하시던 바로 그 촘촘한 WAVE 스타일 가로형 테이블 테마!
  const thClass =
    'py-1.5 px-3 text-[10px] font-bold text-slate-800 border border-slate-400 bg-slate-200 text-left tracking-wider w-1/6';
  const tdClass =
    'py-1.5 px-3 text-[11px] font-mono font-bold text-slate-900 border border-slate-300 bg-white tabular-nums w-1/6';

  return (
    <div className="w-full print:break-inside-avoid mb-6">
      <div className="text-[12px] font-bold text-slate-800 mb-2 pl-2 border-l-2 border-slate-800 uppercase tracking-wider">
        HRRO 스테이지 {stage.stage ?? ''} - 핵심 성능 지표 (Key Performance
        Indicators)
      </div>
      <table className="w-full border-collapse border-2 border-slate-500">
        <tbody>
          <tr>
            <th className={thClass}>목표 플럭스 (Target Flux)</th>
            <td className={tdClass}>
              {fmt(targetFlux)} {u.flux}
            </td>

            <th className={thClass}>달성 플럭스 (Achieved Flux)</th>
            {/* 핵심 지표 하이라이트 */}
            <td className={`${tdClass} text-blue-800 bg-blue-50/50`}>
              {fmt(achievedFlux)} {u.flux}
            </td>

            <th className={thClass}>펌프 효율 (Pump Eff.)</th>
            <td className={tdClass}>{fmt(pumpEff)} %</td>
          </tr>
          <tr>
            <th className={thClass}>최고 인가 압력 (Max Inlet Pressure)</th>
            {/* HRRO는 인가 압력이 중요하므로 하이라이트 */}
            <td className={`${tdClass} text-blue-800 bg-blue-50/50`}>
              {fmt(pIn)} {u.pressure}
            </td>

            <th className={thClass}>모듈 차압 (ΔP)</th>
            <td className={tdClass}>
              {fmt(dp)} {u.pressure}
            </td>

            <th className={thClass}>순추진압력 (NDP)</th>
            <td className={tdClass}>
              {fmt(ndp)} {u.pressure}
            </td>
          </tr>
          <tr>
            <th className={thClass}>비에너지 (SEC)</th>
            <td className={tdClass} colSpan={5}>
              {fmt(sec)} kWh/m³
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}
