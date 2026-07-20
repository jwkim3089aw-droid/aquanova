// ui/src/features/simulation/editors/UnitForms/HRROEditor.tsx

import React from 'react';
import { Field, Input } from '../../components/Common';
import MembraneSelect from '../../components/MembraneSelect';
import { UnitData, HRROConfig } from '../../model/types';
import {
  GROUP_CLS,
  HEADER_CLS,
  INPUT_CLS,
  READONLY_CLS,
  mapMembraneChange,
} from './utils';
import { PumpSection } from './PumpSection';

export function HRROEditor({
  node,
  feed,
  onChange,
}: {
  node: UnitData | undefined;
  feed?: any;
  onChange: (cfg: HRROConfig) => void;
}) {
  if (!node || node.kind !== 'HRRO')
    return (
      <div className="text-red-400 text-xs p-4">
        유효하지 않은 데이터입니다. (Invalid Data)
      </div>
    );

  const raw = (node.cfg as HRROConfig | undefined) ?? {};

  const cfg: HRROConfig = {
    elements: 50,
    vessel_count: 10,
    elements_per_vessel: 5,
    flow_factor: 0.85,
    burst_pressure_limit_bar: 83.0,
    p_set_bar: 38.5,
    recirc_flow_m3h: 0,
    bleed_m3h: 0,
    loop_volume_m3: 1.36,
    timestep_s: 5,
    max_minutes: 60,
    stop_recovery_pct: 90,
    pf_feed_ratio_pct: 150,
    pf_recovery_pct: 20,
    pf_mode: 'smart_partial_drain',
    brine_valve_mode: 'full_open',
    p3_recycle_capacity_m3h_per_pv: 4.54,
    pf_cp_assist_enabled: false,
    pf_cp_assist_flow_m3h_per_pv: 0.0,
    adaptive_recovery_enabled: false,
    brine_conductivity_limit_mgL: undefined,
    brine_tds_limit_mgL: undefined,
    hpp_safe_pressure_limit_bar: undefined,
    hpp_sizing_mode: 'base',
    hpp_count: 1,
    p3_generated_head_bar: 0.6,
    p3_casing_pressure_rating_bar: 12.0,
    temp_mode: 'Design',
    bypass_flow_m3h: 0.0,
    pre_stage_dp_bar: 0.31,
    permeate_back_pressure_bar: 0.0,
    ...raw,
  };

  const patch = (p: Partial<HRROConfig>) => onChange({ ...cfg, ...p });

  const feedFlow = cfg.feed_flow_m3h || 100;
  const recovery = cfg.stop_recovery_pct ?? 90;
  const permeateFlow = feedFlow * (recovery / 100);

  const currentArea = cfg.custom_area_m2 ?? cfg.membrane_area_m2 ?? 40.9;
  const totalArea = currentArea * (cfg.elements || 50);
  const flux = totalArea > 0 ? (permeateFlow * 1000) / totalArea : 0;

  const pfMode = cfg.pf_mode ?? 'smart_partial_drain';
  const pfFeedRatio = (cfg.pf_feed_ratio_pct ?? 120) / 100;
  const pfFeedFlow = permeateFlow * pfFeedRatio;
  const minConcentrateFlow =
    cfg.cc_recycle_m3h_per_pv ?? cfg.p3_recycle_capacity_m3h_per_pv ?? 0;
  const membraneTotalFeed = permeateFlow + minConcentrateFlow;
  const smartDrainSetpoint = Math.max(0, pfFeedFlow - permeateFlow);
  const smartP3Recycle = Math.max(0, membraneTotalFeed - pfFeedFlow);
  const smartCrossflowOk =
    pfMode === 'wave_true_plug_flow'
      ? pfFeedFlow >= membraneTotalFeed
      : (cfg.p3_recycle_capacity_m3h_per_pv ?? 0) + 1e-9 >= smartP3Recycle;

  const handleHardwareChange = (
    field: 'vessel_count' | 'elements_per_vessel',
    value: number,
  ) => {
    const newVal = Math.max(1, value);
    const otherVal =
      field === 'vessel_count'
        ? cfg.elements_per_vessel || 5
        : cfg.vessel_count || 10;
    patch({ [field]: newVal, elements: newVal * otherVal });
  };

  const getLinkedTemp = () => {
    if (!feed) return null;
    if (cfg.temp_mode === 'Minimum')
      return feed.temp_min_C ?? feed.temperature_C;
    if (cfg.temp_mode === 'Maximum')
      return feed.temp_max_C ?? feed.temperature_C;
    return feed.temperature_C;
  };
  const linkedTemp = getLinkedTemp();

  return (
    <div
      className="flex flex-col h-full text-slate-100 p-1 overflow-hidden"
      onKeyDown={(e) => e.stopPropagation()}
    >
      {/* 🛑 상단 요약 대시보드 (KPI) */}
      <div className="grid grid-cols-4 gap-2 p-2 bg-slate-900 border border-slate-700 rounded-lg shadow-inner shrink-0 mb-2">
        <div className="flex flex-col items-center border-r border-slate-700">
          <span className="text-[10px] text-slate-400 font-bold mb-0.5 uppercase tracking-wide">
            유입수 (Feed Flow)
          </span>
          <span className="font-mono text-base font-bold text-slate-100">
            {feedFlow.toFixed(1)}{' '}
            <small className="text-[9px] font-normal text-slate-500">
              m³/h
            </small>
          </span>
        </div>
        <div className="flex flex-col items-center border-r border-slate-700">
          <span className="text-[10px] text-emerald-400 font-bold mb-0.5 uppercase tracking-wide">
            목표 회수율 (Recovery)
          </span>
          <span className="font-mono text-base font-bold text-emerald-400">
            {cfg.stop_recovery_pct}{' '}
            <small className="text-[9px] font-normal text-emerald-600/70">
              %
            </small>
          </span>
        </div>
        <div className="flex flex-col items-center border-r border-slate-700">
          <span className="text-[10px] text-blue-400 font-bold mb-0.5 uppercase tracking-wide">
            예상 생산수 (Permeate)
          </span>
          <span className="font-mono text-base font-bold text-blue-300">
            {permeateFlow.toFixed(1)}{' '}
            <small className="text-[9px] font-normal text-blue-500/70">
              m³/h
            </small>
          </span>
        </div>
        <div className="flex flex-col items-center">
          <span className="text-[10px] text-slate-400 font-bold mb-0.5 uppercase tracking-wide">
            총 막 면적 (Total Area)
          </span>
          <span className="font-mono text-base font-bold text-slate-300">
            {totalArea.toFixed(1)}{' '}
            <small className="text-[9px] font-normal text-slate-500">m²</small>
          </span>
        </div>
      </div>

      <div className="flex-1 grid grid-cols-12 gap-3 overflow-hidden">
        {/* ========================================================= */}
        {/* 좌측 패널 (Left Column) */}
        {/* ========================================================= */}
        <div className="col-span-6 flex flex-col gap-2 h-full min-h-0 overflow-y-auto custom-scrollbar pr-1 pb-4">
          <div className="shrink-0">
            <div className="px-3 py-2 bg-slate-800/90 border border-slate-700 rounded-t-md text-[11px] font-bold text-slate-200 tracking-wide">
              멤브레인 모델 (Membrane Type: {node.kind})
            </div>
            <div className="p-3 border-x border-b border-slate-700 bg-slate-900/60 rounded-b-md">
              <MembraneSelect
                unitType="HRRO"
                mode={cfg.membrane_mode}
                model={cfg.membrane_model}
                area={cfg.custom_area_m2 ?? cfg.membrane_area_m2}
                A={cfg.custom_A_lmh_bar ?? cfg.membrane_A_lmh_bar}
                B={cfg.custom_B_lmh ?? cfg.membrane_B_lmh}
                rej={
                  cfg.custom_salt_rejection_pct ??
                  cfg.membrane_salt_rejection_pct
                }
                onChange={(updates) => patch(mapMembraneChange(updates))}
              />
            </div>
          </div>

          <div className={`${GROUP_CLS} shrink-0 !mb-0`}>
            <h4 className={HEADER_CLS}>📏 모듈 배열 (Array Configuration)</h4>
            <div className="grid grid-cols-3 gap-2">
              <Field label="베셀 수 (Vessels)">
                <Input
                  className={INPUT_CLS}
                  type="number"
                  min={1}
                  value={cfg.vessel_count}
                  onChange={(e) =>
                    handleHardwareChange(
                      'vessel_count',
                      parseInt(e.target.value),
                    )
                  }
                />
              </Field>
              <Field label="베셀당 엘리먼트">
                <Input
                  className={INPUT_CLS}
                  type="number"
                  min={1}
                  max={8}
                  value={cfg.elements_per_vessel}
                  onChange={(e) =>
                    handleHardwareChange(
                      'elements_per_vessel',
                      parseInt(e.target.value),
                    )
                  }
                />
              </Field>
              <Field label="총 엘리먼트 (Total)">
                <div
                  className={`${READONLY_CLS} text-slate-300 w-full justify-center bg-slate-800/50`}
                >
                  {cfg.elements}{' '}
                  <span className="text-[10px] text-slate-500 ml-1">
                    개(EA)
                  </span>
                </div>
              </Field>
            </div>
          </div>

          <div
            className={`${GROUP_CLS} shrink-0 !mb-0 border-blue-900/40 bg-blue-900/10`}
          >
            <h4 className={`${HEADER_CLS} border-blue-900/30 text-blue-400`}>
              🌊 운전 설정 및 유량 (Operation & Flow)
            </h4>
            <div className="flex flex-col gap-2">
              <Field label="목표 회수율 (Target Recovery, %)">
                <div className="flex items-center gap-1.5">
                  <Input
                    className={`${INPUT_CLS} text-emerald-400 font-bold`}
                    type="number"
                    max={99.9}
                    value={cfg.stop_recovery_pct}
                    onChange={(e) =>
                      patch({ stop_recovery_pct: Number(e.target.value) })
                    }
                  />
                  <span className="text-[10px] text-slate-500 w-6">%</span>
                </div>
              </Field>

              <Field label="유량 감소 계수 (Flow Factor)">
                <Input
                  className={INPUT_CLS}
                  type="number"
                  step={0.05}
                  min={0.1}
                  value={cfg.flow_factor}
                  onChange={(e) =>
                    patch({ flow_factor: parseFloat(e.target.value) })
                  }
                />
              </Field>

              <div className="grid grid-cols-2 gap-3 mt-1">
                <Field label="농축수 순환 (Recycle)">
                  <div className="flex items-center gap-1.5">
                    <Input
                      className={INPUT_CLS}
                      type="number"
                      step={0.1}
                      value={cfg.recirc_flow_m3h}
                      onChange={(e) =>
                        patch({ recirc_flow_m3h: Number(e.target.value) })
                      }
                    />
                    <span className="text-[10px] text-slate-500 w-6">m³/h</span>
                  </div>
                </Field>
                <Field label="바이패스 (Bypass)">
                  <div className="flex items-center gap-1.5">
                    <Input
                      className={INPUT_CLS}
                      type="number"
                      step={0.1}
                      value={cfg.bypass_flow_m3h}
                      onChange={(e) =>
                        patch({ bypass_flow_m3h: Number(e.target.value) })
                      }
                    />
                    <span className="text-[10px] text-slate-500 w-6">m³/h</span>
                  </div>
                </Field>
              </div>
            </div>
          </div>
        </div>

        {/* ========================================================= */}
        {/* 우측 패널 (Right Column) */}
        {/* ========================================================= */}
        <div className="col-span-6 flex flex-col gap-2 h-full min-h-0 overflow-y-auto custom-scrollbar pr-1 pb-4">
          <PumpSection cfg={cfg} onChange={patch} defaultPressure={38.5} />

          <div className={`${GROUP_CLS} shrink-0 !mb-0`}>
            <h4 className={HEADER_CLS}>
              💧 수리학적 압력 및 온도 (Hydraulics)
            </h4>
            <div className="flex flex-col gap-2">
              <div className="flex flex-col gap-1">
                <span className="text-[10px] font-bold text-slate-400 tracking-wide">
                  수온 기준 (Temperature Mode)
                </span>
                <div className="flex gap-1.5">
                  <select
                    className="w-[45%] h-7 bg-slate-950 border border-slate-700 rounded px-1.5 text-[11px] text-slate-200 focus:border-blue-500"
                    value={cfg.temp_mode}
                    onChange={(e) =>
                      patch({ temp_mode: e.target.value as any })
                    }
                  >
                    <option value="Minimum">최소 (Min)</option>
                    <option value="Design">설계 (Des)</option>
                    <option value="Maximum">최대 (Max)</option>
                  </select>
                  <div className="h-7 flex-1 bg-slate-900/80 border border-slate-700 rounded px-2 flex items-center justify-center text-[11px] font-mono font-bold text-amber-300 shadow-inner">
                    {linkedTemp != null ? `${linkedTemp} °C` : '-'}
                  </div>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3 mt-1">
                <Field label="생산수 배압 (Permeate Back P)">
                  <div className="flex items-center gap-1.5">
                    <Input
                      className={INPUT_CLS}
                      type="number"
                      step={0.1}
                      value={cfg.permeate_back_pressure_bar}
                      onChange={(e) =>
                        patch({
                          permeate_back_pressure_bar: Number(e.target.value),
                        })
                      }
                    />
                    <span className="text-[10px] text-slate-500 w-6">bar</span>
                  </div>
                </Field>
                <Field label="배관 차압 (Pre-stage ΔP)">
                  <div className="flex items-center gap-1.5">
                    <Input
                      className={INPUT_CLS}
                      type="number"
                      step={0.1}
                      value={cfg.pre_stage_dp_bar}
                      onChange={(e) =>
                        patch({ pre_stage_dp_bar: Number(e.target.value) })
                      }
                    />
                    <span className="text-[10px] text-slate-500 w-6">bar</span>
                  </div>
                </Field>
              </div>
            </div>
          </div>

          {/* HRRO 고급 설정 (CCRO & Limits) */}
          <div className="grid grid-cols-2 gap-2 flex-1 min-h-0">
            <div className="flex flex-col p-3 border border-indigo-900/40 bg-indigo-900/10 rounded-lg">
              <h4 className="text-indigo-400 font-bold mb-3 text-[10px] uppercase border-b border-indigo-900/30 pb-1">
                🔄 PF 운전 / P-3 연동
              </h4>
              <div className="flex flex-col gap-3">
                <div
                  data-testid="hrro-pf-operation-summary"
                  className="rounded border border-indigo-800/50 bg-slate-950/50 px-3 py-2"
                >
                  <div className="text-[9px] font-bold uppercase tracking-wide text-slate-500">
                    PF 운전 방식
                  </div>

                  <div className="mt-1 text-[11px] font-bold text-indigo-200">
                    {pfMode === 'wave_true_plug_flow'
                      ? '고유량 PF 운전'
                      : pfMode === 'field_optimized_low_fr'
                        ? '저유량 PF 운전'
                        : '자동 PF 운전'}
                  </div>

                  <div className="mt-1 text-[9px] leading-relaxed text-slate-500">
                    {pfMode === 'wave_true_plug_flow'
                      ? 'PF 공급 유량으로 막 유속을 확보하는 운전입니다.'
                      : pfMode === 'field_optimized_low_fr'
                        ? '낮은 PF 공급 유량과 P-3 재순환을 함께 사용하는 운전입니다.'
                        : 'P-3 재순환과 농축수 배출을 운전 조건에 맞춰 자동 조절합니다.'}
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-2">
                  <Field label="PF Feed Ratio (FR, %)">
                    <div className="flex items-center gap-1.5">
                      <Input
                        className={INPUT_CLS}
                        type="number"
                        value={cfg.pf_feed_ratio_pct}
                        onChange={(e) =>
                          patch({ pf_feed_ratio_pct: Number(e.target.value) })
                        }
                      />
                      <span className="text-[9px] text-slate-500 w-6">%</span>
                    </div>
                  </Field>
                  <Field label="PF Recovery (%)">
                    <div className="flex items-center gap-1.5">
                      <Input
                        className={INPUT_CLS}
                        type="number"
                        value={cfg.pf_recovery_pct}
                        onChange={(e) =>
                          patch({ pf_recovery_pct: Number(e.target.value) })
                        }
                      />
                      <span className="text-[9px] text-slate-500 w-6">%</span>
                    </div>
                  </Field>
                </div>

                <div className="grid grid-cols-2 gap-2">
                  <Field label="P-3 재순환 용량">
                    <div className="flex items-center gap-1.5">
                      <Input
                        className={INPUT_CLS}
                        type="number"
                        step={0.01}
                        value={cfg.p3_recycle_capacity_m3h_per_pv}
                        onChange={(e) =>
                          patch({
                            p3_recycle_capacity_m3h_per_pv: Number(e.target.value),
                          } as any)
                        }
                      />
                      <span className="text-[9px] text-slate-500 w-10">m³/h</span>
                    </div>
                  </Field>
                  <Field label="CC 최소 농축수 유량">
                    <div className="flex items-center gap-1.5">
                      <Input
                        className={INPUT_CLS}
                        type="number"
                        step={0.01}
                        value={cfg.cc_recycle_m3h_per_pv}
                        onChange={(e) =>
                          patch({ cc_recycle_m3h_per_pv: Number(e.target.value) })
                        }
                      />
                      <span className="text-[9px] text-slate-500 w-10">m³/h</span>
                    </div>
                  </Field>
                </div>

                <div className="rounded-md border border-slate-700/70 bg-slate-950/60 p-2 space-y-1.5 text-[10px]">
                  <div className="flex items-center justify-between">
                    <span className="text-slate-400">PF feed = Product × FR</span>
                    <span className="font-mono text-slate-200">{pfFeedFlow.toFixed(3)} m³/h</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-slate-400">외부 배출 setpoint</span>
                    <span className="font-mono text-cyan-300">{smartDrainSetpoint.toFixed(3)} m³/h</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-slate-400">필요 P-3 recycle</span>
                    <span className="font-mono text-indigo-300">{smartP3Recycle.toFixed(3)} m³/h</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-slate-400">막 유입 총유량</span>
                    <span className="font-mono text-emerald-300">{membraneTotalFeed.toFixed(3)} m³/h</span>
                  </div>
                  <div
                    className={`mt-2 rounded border px-2 py-1 font-bold ${
                      smartCrossflowOk
                        ? 'border-emerald-800 bg-emerald-950/30 text-emerald-300'
                        : 'border-rose-800 bg-rose-950/30 text-rose-300'
                    }`}
                  >
                    {smartCrossflowOk
                      ? 'Crossflow OK: 현재 PF/P-3 설정으로 막 유속 조건 충족 가능'
                      : 'Crossflow 부족: FR 또는 P-3 용량을 올려야 함'}
                  </div>
                </div>

                <div className="text-[10px] text-slate-500 leading-relaxed">
                  현재 PF 운전은 P-3 재순환과 농축수 배출을 함께 계산합니다.
                  배출량과 재순환 용량은 막 유속 및 질량수지 조건에 따라 자동 판정됩니다.
                </div>
              </div>
            </div>

            <div className="flex flex-col p-3 border border-rose-900/30 bg-rose-900/10 rounded-lg">
              <h4 className="text-rose-400 font-bold mb-3 text-[10px] uppercase border-b border-rose-900/30 pb-1">
                🛡️ Adaptive Recovery / Pump Limits
              </h4>
              <div className="flex flex-col gap-3">
                <label className="flex items-center gap-2 rounded border border-slate-700 bg-slate-950/50 px-2 py-2 text-[11px] text-slate-200">
                  <input
                    type="checkbox"
                    checked={Boolean(cfg.adaptive_recovery_enabled)}
                    onChange={(e) =>
                      patch({ adaptive_recovery_enabled: e.target.checked } as any)
                    }
                  />
                  원수 악화 시 목표 회수율 고정 대신 농축수 한계 기준으로 PF 조기 전환
                </label>

                <div className="grid grid-cols-2 gap-2">
                  <Field label="Brine Conductivity/TDS limit">
                    <div className="flex items-center gap-1.5">
                      <Input
                        className={INPUT_CLS}
                        type="number"
                        step={10}
                        value={cfg.brine_conductivity_limit_mgL}
                        onChange={(e) =>
                          patch({
                            brine_conductivity_limit_mgL:
                              e.target.value === '' ? undefined : Number(e.target.value),
                          } as any)
                        }
                      />
                      <span className="text-[9px] text-slate-500 w-10">mg/L</span>
                    </div>
                  </Field>
                  <Field label="HPP 안전 압력 한계">
                    <div className="flex items-center gap-1.5">
                      <Input
                        className={INPUT_CLS}
                        type="number"
                        step={0.1}
                        value={cfg.hpp_safe_pressure_limit_bar}
                        onChange={(e) =>
                          patch({
                            hpp_safe_pressure_limit_bar:
                              e.target.value === '' ? undefined : Number(e.target.value),
                          } as any)
                        }
                      />
                      <span className="text-[9px] text-slate-500 w-6">bar</span>
                    </div>
                  </Field>
                </div>

                <div className="grid grid-cols-2 gap-2">
                  <Field label="HPP sizing mode">
                    <select
                      className="h-7 text-xs bg-slate-950 border border-slate-700 rounded px-2 outline-none text-slate-100 focus:border-blue-500"
                      value={cfg.hpp_sizing_mode ?? 'base'}
                      onChange={(e) => patch({ hpp_sizing_mode: e.target.value as any })}
                    >
                      <option value="base">Base · 정상 원수</option>
                      <option value="step1">Step 1 · 고부하/악화 원수</option>
                      <option value="step2">Step 2 · 최고농축/최악 조건</option>
                    </select>
                  </Field>
                  <Field label="HPP 대수">
                    <Input
                      className={INPUT_CLS}
                      type="number"
                      min={1}
                      value={cfg.hpp_count ?? 1}
                      onChange={(e) => patch({ hpp_count: Number(e.target.value) } as any)}
                    />
                  </Field>
                </div>

                <div className="grid grid-cols-2 gap-2">
                  <Field label="P-3 생성 양정">
                    <div className="flex items-center gap-1.5">
                      <Input
                        className={INPUT_CLS}
                        type="number"
                        step={0.1}
                        value={cfg.p3_generated_head_bar}
                        onChange={(e) =>
                          patch({ p3_generated_head_bar: Number(e.target.value) } as any)
                        }
                      />
                      <span className="text-[9px] text-slate-500 w-6">bar</span>
                    </div>
                  </Field>
                  <Field label="P-3 케이싱 내압">
                    <div className="flex items-center gap-1.5">
                      <Input
                        className={`${INPUT_CLS} text-rose-300 font-bold bg-rose-950/40 border-rose-800/50`}
                        type="number"
                        step={0.1}
                        value={cfg.p3_casing_pressure_rating_bar}
                        onChange={(e) =>
                          patch({
                            p3_casing_pressure_rating_bar: Number(e.target.value),
                          } as any)
                        }
                      />
                      <span className="text-[9px] text-slate-500 w-6">bar</span>
                    </div>
                  </Field>
                </div>

                <div className="grid grid-cols-2 gap-2">
                  <Field label="시스템 체적 (Loop Vol)">
                    <div className="flex items-center gap-1.5">
                      <Input
                        className={INPUT_CLS}
                        type="number"
                        step={0.01}
                        value={cfg.loop_volume_m3}
                        onChange={(e) => patch({ loop_volume_m3: Number(e.target.value) })}
                      />
                      <span className="text-[9px] text-slate-500 w-6">m³</span>
                    </div>
                  </Field>
                  <Field label="최대 운전 시간">
                    <div className="flex items-center gap-1.5">
                      <Input
                        className={INPUT_CLS}
                        type="number"
                        value={cfg.max_minutes}
                        onChange={(e) => patch({ max_minutes: Number(e.target.value) })}
                      />
                      <span className="text-[9px] text-slate-500 w-6">min</span>
                    </div>
                  </Field>
                </div>
              </div>
            </div>
          </div>        </div>
      </div>
    </div>
  );
}
