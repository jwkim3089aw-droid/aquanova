// ui/src/components/common/DetailedResultModal/tabs/AuditTab.tsx
import React from 'react';
import {
  ClipboardCheck,
  CheckCircle2,
  ShieldAlert,
  AlertTriangle,
} from 'lucide-react';
import { fmt } from '../../../../features/simulation/model/types';
import { STYLES } from '../constants';

export function AuditTab({
  isSystemView,
  currentData,
  isHRRO,
}: {
  isSystemView: boolean;
  currentData: any;
  isHRRO: boolean;
}) {
  // 위반(경고) 사항 리스트 추출
  const violations = currentData.violations || [];
  const profile = currentData.element_profile || [];
  const cycle = currentData.chemistry?.ccro_cycle || {};
  const model = currentData.chemistry?.model || {};
  const isSmartPF =
    cycle.pf_mode === 'smart_partial_drain' ||
    cycle.pf_mode === 'field_optimized_low_fr' ||
    model.smart_partial_drain_enabled === true;

  // 상태별 컬러와 아이콘 결정
  const hasViolations = violations.length > 0;
  const statusColor = hasViolations ? 'text-rose-400' : 'text-emerald-400';
  const statusBorder = hasViolations ? 'border-rose-800' : 'border-emerald-800';
  const statusBg = hasViolations ? 'bg-rose-950/20' : 'bg-emerald-950/20';

  return (
    <div className="p-8 max-w-[1200px] mx-auto animate-in fade-in duration-0">
      <div className="mb-6 flex items-end justify-between border-b border-slate-800 pb-4">
        <div>
          <h3 className="text-sm font-bold text-slate-300 uppercase tracking-widest flex items-center gap-2">
            <ClipboardCheck className="w-4 h-4 text-slate-500" /> 설계 진단 및
            경고 (Design Audit & Guidelines)
          </h3>
          <p className="text-xs font-mono text-slate-500 mt-2">
            {isSystemView
              ? '시스템 전체의 설계 한계치 및 가이드라인 준수 여부를 종합적으로 평가합니다.'
              : '해당 스테이지의 멤브레인 수력학적 한계(Hydraulic limits) 및 경고 사항을 점검합니다.'}
          </p>
        </div>
      </div>

      <div className="space-y-6">
        {/* 1. 종합 상태 패널 */}
        <div
          className={`p-6 border rounded-sm flex items-start gap-4 ${statusBorder} ${statusBg}`}
        >
          {hasViolations ? (
            <ShieldAlert className="w-8 h-8 text-rose-500 flex-shrink-0 mt-1" />
          ) : (
            <CheckCircle2 className="w-8 h-8 text-emerald-500 flex-shrink-0 mt-1" />
          )}

          <div className="flex-1">
            <h4
              className={`text-sm font-bold uppercase tracking-wider mb-2 ${statusColor}`}
            >
              {hasViolations
                ? '설계 지침 위반 감지 (Guideline Violations Detected)'
                : '설계 기준 충족 (All Guidelines Met)'}
            </h4>

            {hasViolations ? (
              <ul className="space-y-2 mt-4">
                {violations.map((msg: string, idx: number) => (
                  <li
                    key={idx}
                    className="text-sm text-rose-200 bg-rose-950/40 p-3 border border-rose-900/50 rounded-sm flex gap-3"
                  >
                    <span className="font-mono text-rose-500 font-bold">
                      [{idx + 1}]
                    </span>{' '}
                    {msg}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-slate-400">
                현재 설계는 제조사의 권장 한계치(플럭스, 유량, 압력 등) 내에서
                안정적으로 작동할 것으로 예측됩니다.
              </p>
            )}
          </div>
        </div>

        {/* V83. HRRO Smart PF / Adaptive Recovery 결과 패널 */}
        {!isSystemView && isHRRO && (Object.keys(cycle).length > 0 || Object.keys(model).length > 0) && (
          <div className="bg-slate-900 border border-indigo-900/50 rounded-sm overflow-hidden shadow-md">
            <div className="bg-slate-800 px-6 py-4 border-b border-slate-700 flex items-center justify-between">
              <div>
                <h4 className="font-bold text-slate-100 text-sm">
                  HRRO PF 제어 / Adaptive Recovery
                </h4>
                <p className="text-[11px] text-slate-500 mt-1">
                  V82/V83 smart_partial_drain_pf, P-3 연동, 부분 배출 PID, 조기 PF 전환 진단값입니다.
                </p>
              </div>
              <span
                className={`text-[10px] px-2 py-1 rounded border font-bold ${
                  isSmartPF
                    ? 'bg-indigo-950/50 text-indigo-300 border-indigo-700'
                    : 'bg-slate-950/60 text-slate-400 border-slate-700'
                }`}
              >
                {cycle.pf_mode || 'wave_true_plug_flow'}
              </span>
            </div>

            <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 p-5">
              <div className="p-3 rounded border border-slate-700 bg-slate-950/50">
                <div className="text-[10px] text-slate-500 uppercase font-bold">외부 배출 setpoint</div>
                <div className="text-lg font-mono font-bold text-cyan-300">
                  {fmt(cycle.external_drain_setpoint_m3h_per_pv ?? cycle.pf_external_drain_flow_m3h_per_pv)}
                  <span className="text-[10px] text-slate-500 ml-1">m³/h</span>
                </div>
              </div>
              <div className="p-3 rounded border border-slate-700 bg-slate-950/50">
                <div className="text-[10px] text-slate-500 uppercase font-bold">P-3 recycle 요구량</div>
                <div className="text-lg font-mono font-bold text-indigo-300">
                  {fmt(cycle.pf_p3_recycle_flow_m3h_per_pv)}
                  <span className="text-[10px] text-slate-500 ml-1">m³/h</span>
                </div>
              </div>
              <div className="p-3 rounded border border-slate-700 bg-slate-950/50">
                <div className="text-[10px] text-slate-500 uppercase font-bold">막 유입 총유량</div>
                <div className="text-lg font-mono font-bold text-emerald-300">
                  {fmt(cycle.pf_membrane_total_feed_m3h_per_pv)}
                  <span className="text-[10px] text-slate-500 ml-1">m³/h</span>
                </div>
              </div>
              <div className="p-3 rounded border border-slate-700 bg-slate-950/50">
                <div className="text-[10px] text-slate-500 uppercase font-bold">실제/목표 회수율</div>
                <div className="text-lg font-mono font-bold text-slate-100">
                  {fmt(model.actual_cycle_recovery_pct ?? currentData.recovery_pct)}
                  <span className="text-[10px] text-slate-500 mx-1">/</span>
                  {fmt(model.requested_target_recovery_pct)}
                  <span className="text-[10px] text-slate-500 ml-1">%</span>
                </div>
              </div>
            </div>

            <div className="px-5 pb-5 grid grid-cols-1 lg:grid-cols-2 gap-3">
              <div
                className={`p-3 rounded border text-xs ${
                  cycle.crossflow_ok === false || cycle.p3_recycle_capacity_ok === false
                    ? 'border-rose-800 bg-rose-950/30 text-rose-200'
                    : 'border-emerald-800 bg-emerald-950/20 text-emerald-200'
                }`}
              >
                <div className="font-bold mb-1">Crossflow / P-3 용량 판정</div>
                <div className="text-[11px] opacity-90">
                  crossflow_ok={String(cycle.crossflow_ok ?? 'n/a')} · p3_capacity_ok={String(cycle.p3_recycle_capacity_ok ?? 'n/a')}
                </div>
              </div>
              <div
                className={`p-3 rounded border text-xs ${
                  model.recovery_stop_reason && model.recovery_stop_reason !== 'target_recovery_reached'
                    ? 'border-amber-800 bg-amber-950/30 text-amber-200'
                    : 'border-slate-700 bg-slate-950/40 text-slate-300'
                }`}
              >
                <div className="font-bold mb-1">Adaptive Recovery stop reason</div>
                <div className="text-[11px] opacity-90">
                  {model.recovery_stop_reason || 'target_recovery_reached'}
                  {model.brine_conductivity_limit_mgL ? ` · limit ${fmt(model.brine_conductivity_limit_mgL)} mg/L` : ''}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* 2. 엘리먼트 수력학 데이터 (스테이지 뷰 & 프로파일 데이터가 있을 때만) */}
        {!isSystemView && profile.length > 0 && (
          <div className="bg-slate-900 border border-slate-700 rounded-sm overflow-hidden shadow-md mt-8">
            <div className="bg-slate-800 px-6 py-4 border-b border-slate-700 flex items-center justify-between">
              <h4 className="font-bold text-slate-100 text-sm">
                베셀 내부 수력학 분포 (Vessel Hydraulics)
              </h4>
              <span className="text-[10px] bg-slate-700 px-2 py-1 rounded text-slate-300 font-mono">
                {profile.length} Elements
              </span>
            </div>

            <table className="w-full text-sm">
              <thead>
                <tr className="bg-slate-900/50">
                  <th className={`${STYLES.TH} text-center`}>
                    위치 (Position)
                  </th>
                  <th className={`${STYLES.TH} text-right`}>
                    생산 플럭스 (Flux, LMH)
                  </th>
                  <th className={`${STYLES.TH} text-right`}>
                    농축수 유량 (Conc Flow, m³/h)
                  </th>
                  <th className={`${STYLES.TH} text-right`}>
                    막간차압 (TMP, bar)
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {profile.map((el: any, i: number) => {
                  // 선두(Lead) 막은 플럭스가 높아서 위험, 후미(Tail) 막은 유량이 낮아서 위험할 수 있음
                  const isLead = i === 0;
                  const isTail = i === profile.length - 1;

                  return (
                    <tr
                      key={i}
                      className="hover:bg-slate-800/30 transition-colors"
                    >
                      <td className={`${STYLES.TD_L} text-center`}>
                        <div className="flex items-center justify-center gap-2 font-mono">
                          <span className="text-slate-500">
                            #{el.el || i + 1}
                          </span>
                          {isLead && (
                            <span className="text-[9px] bg-blue-900/50 text-blue-300 px-1 rounded border border-blue-800">
                              LEAD
                            </span>
                          )}
                          {isTail && (
                            <span className="text-[9px] bg-orange-900/50 text-orange-300 px-1 rounded border border-orange-800">
                              TAIL
                            </span>
                          )}
                        </div>
                      </td>
                      <td
                        className={`${STYLES.TD} text-right font-mono text-slate-200`}
                      >
                        {fmt(el.flux_lmh)}
                      </td>
                      <td
                        className={`${STYLES.TD} text-right font-mono text-slate-200`}
                      >
                        {fmt(el.flow_c_m3h)}{' '}
                        {/* 농축수 유량 필드가 없다면 0이 표시될 수 있음 */}
                      </td>
                      <td
                        className={`${STYLES.TD} text-right font-mono text-slate-200`}
                      >
                        {fmt(el.tmp_bar || el.pressure_bar)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            <div className="p-4 bg-slate-950 border-t border-slate-800 text-[11px] text-slate-500 font-mono">
              * Lead Element는 파울링 위험이 가장 높으며, Tail Element는
              스케일링 위험이 가장 높습니다.
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
