// ui/src/features/simulation/editors/UnitForms/ROEditor.tsx
import React, { memo } from 'react';
import { Field, Input } from '../../components/Common';
import MembraneSelect from '../../components/MembraneSelect';
import { UnitData, ROConfig } from '../../model/types';
import {
  GROUP_CLS,
  HEADER_CLS,
  INPUT_CLS,
  READONLY_CLS,
  mapMembraneChange,
} from './utils';
import { PumpSection } from './PumpSection';

// 폼 컴포넌트 리렌더링 방지를 위한 memo 적용
export const ROEditor = memo(function ROEditor({
  node,
  feed,
  onChange,
}: {
  node: UnitData | undefined;
  feed?: any;
  onChange: (cfg: ROConfig) => void;
}) {
  if (!node || (node.kind !== 'RO' && node.kind !== 'NF'))
    return (
      <div className="text-red-400 text-xs p-4">
        유효하지 않은 데이터입니다. (Invalid Data)
      </div>
    );

  const cfg = {
    mode: 'recovery' as const,
    recovery_target_pct: 75,
    pressure_bar: 15.0,
    flow_target_m3h: 50.0,
    vessel_count: 10,
    elements_per_vessel: 6,
    elements: 60,
    flow_factor: 0.85,
    spi: 1.1,
    age_years: 3.0,
    permeate_back_pressure_bar: 0.0,
    pre_stage_dp_bar: 0.3,
    recirc_flow_m3h: 0.0,
    bypass_flow_m3h: 0.0,
    ...node.cfg,
  } as ROConfig;

  const patch = (p: Partial<ROConfig>) => onChange({ ...cfg, ...p });

  const handleArrayChange = (
    field: 'vessel_count' | 'elements_per_vessel',
    value: number,
  ) => {
    const v = Math.max(1, value);
    const other =
      field === 'vessel_count'
        ? cfg.elements_per_vessel || 6
        : cfg.vessel_count || 10;
    patch({ [field]: v, elements: v * other });
  };

  const feedFlow = feed?.flow_m3h ?? 100;
  let currentRecovery = cfg.recovery_target_pct ?? 75;
  let permeateFlow = 0;

  if (cfg.mode === 'flow') {
    permeateFlow = cfg.flow_target_m3h ?? 50;
    currentRecovery = feedFlow > 0 ? (permeateFlow / feedFlow) * 100 : 0;
  } else {
    permeateFlow = feedFlow * (currentRecovery / 100);
  }

  const currentArea = cfg.custom_area_m2 ?? cfg.membrane_area_m2 ?? 37.2;
  const totalArea = currentArea * (cfg.elements || 60);
  const flux = totalArea > 0 ? (permeateFlow * 1000) / totalArea : 0;

  return (
    <div
      className="flex flex-col h-full text-slate-100 p-1 overflow-hidden"
      onKeyDown={(e) => e.stopPropagation()}
    >
      {/* 상단 요약 대시보드 (KPI) */}
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
            회수율 (Recovery)
          </span>
          <span className="font-mono text-base font-bold text-emerald-400">
            {currentRecovery.toFixed(1)}{' '}
            <small className="text-[9px] font-normal text-emerald-600/70">
              %
            </small>
          </span>
        </div>
        <div className="flex flex-col items-center border-r border-slate-700">
          <span className="text-[10px] text-blue-400 font-bold mb-0.5 uppercase tracking-wide">
            생산수 (Permeate)
          </span>
          <span className="font-mono text-base font-bold text-blue-300">
            {permeateFlow.toFixed(1)}{' '}
            <small className="text-[9px] font-normal text-blue-500/70">
              m³/h
            </small>
          </span>
        </div>
        <div className="flex flex-col items-center">
          <span className="text-[10px] text-amber-400 font-bold mb-0.5 uppercase tracking-wide">
            평균 플럭스 (Avg Flux)
          </span>
          <span className="font-mono text-base font-bold text-amber-300">
            {flux.toFixed(1)}{' '}
            <small className="text-[9px] font-normal text-amber-600/70">
              LMH
            </small>
          </span>
        </div>
      </div>

      <div className="flex-1 grid grid-cols-12 gap-3 overflow-hidden">
        {/* 좌측 패널 */}
        <div className="col-span-6 flex flex-col gap-2 h-full min-h-0 overflow-y-auto custom-scrollbar pr-1 pb-4">
          <div className="shrink-0">
            <div className="px-3 py-2 bg-slate-800/90 border border-slate-700 rounded-t-md text-[11px] font-bold text-slate-200 tracking-wide">
              멤브레인 모델 (Membrane Type: {node.kind})
            </div>
            <div className="p-3 border-x border-b border-slate-700 bg-slate-900/60 rounded-b-md">
              <MembraneSelect
                unitType={node.kind as 'RO' | 'NF'}
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
            <h4 className={HEADER_CLS}>모듈 배열 (Array Configuration)</h4>
            <div className="grid grid-cols-3 gap-2">
              <Field label="베셀 수 (Vessels)">
                <Input
                  className={INPUT_CLS}
                  type="number"
                  min={1}
                  value={cfg.vessel_count}
                  onChange={(e) =>
                    handleArrayChange('vessel_count', parseInt(e.target.value))
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
                    handleArrayChange(
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
              운전 제어 목표 (Operating Target)
            </h4>
            <div className="flex flex-col gap-2">
              <Field label="제어 기준 (Control Mode)">
                <select
                  className={`${INPUT_CLS} border-blue-800/50 bg-blue-950/40 font-bold text-blue-200`}
                  value={cfg.mode}
                  onChange={(e) => patch({ mode: e.target.value as any })}
                >
                  <option value="recovery">
                    목표 회수율 제어 (Target Recovery)
                  </option>
                  <option value="flow">
                    목표 생산 유량 제어 (Target Flow)
                  </option>
                  <option value="pressure">
                    고정 유입 압력 제어 (Fixed Feed Pressure)
                  </option>
                </select>
              </Field>

              <div className="mt-1">
                {cfg.mode === 'recovery' && (
                  <Field label="목표 회수율 (Target Recovery, %)">
                    <Input
                      className={`${INPUT_CLS} font-bold text-blue-300`}
                      type="number"
                      step={0.1}
                      value={cfg.recovery_target_pct}
                      onChange={(e) =>
                        patch({ recovery_target_pct: Number(e.target.value) })
                      }
                    />
                  </Field>
                )}
                {cfg.mode === 'flow' && (
                  <Field label="목표 생산 유량 (Target Flow, m³/h)">
                    <Input
                      className={`${INPUT_CLS} font-bold text-blue-300`}
                      type="number"
                      value={cfg.flow_target_m3h}
                      onChange={(e) =>
                        patch({ flow_target_m3h: Number(e.target.value) })
                      }
                    />
                  </Field>
                )}
                {cfg.mode === 'pressure' && (
                  <Field label="고정 유입 압력 (Feed Pressure, bar)">
                    <Input
                      className={`${INPUT_CLS} font-bold text-amber-300`}
                      type="number"
                      value={cfg.pressure_bar}
                      onChange={(e) =>
                        patch({ pressure_bar: Number(e.target.value) })
                      }
                    />
                  </Field>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* 우측 패널 */}
        <div className="col-span-6 flex flex-col gap-2 h-full min-h-0 overflow-y-auto custom-scrollbar pr-1 pb-4">
          <PumpSection cfg={cfg} onChange={patch} defaultPressure={15.0} />

          <div
            className={`${GROUP_CLS} shrink-0 !mb-0 border-amber-900/30 bg-amber-900/5`}
          >
            <h4 className={`${HEADER_CLS} border-amber-900/20 text-amber-500`}>
              노후화 및 오염 계수 (Ageing & Fouling)
            </h4>
            <div className="grid grid-cols-2 gap-x-3 gap-y-2">
              <Field label="막 사용 연수 (Membrane Age)">
                <div className="flex items-center gap-1.5">
                  <Input
                    className={INPUT_CLS}
                    type="number"
                    step={0.5}
                    value={cfg.age_years}
                    onChange={(e) =>
                      patch({ age_years: Number(e.target.value) })
                    }
                  />
                  <span className="text-[9px] text-slate-500 w-8">년(Yrs)</span>
                </div>
              </Field>
              <div className="hidden" />

              <Field label="유량 감소 계수 (Flow Factor)">
                <Input
                  className={INPUT_CLS}
                  type="number"
                  step={0.01}
                  value={cfg.flow_factor}
                  onChange={(e) =>
                    patch({ flow_factor: parseFloat(e.target.value) })
                  }
                />
              </Field>
              <Field label="염 투과 증가율 (SPI)">
                <Input
                  className={INPUT_CLS}
                  type="number"
                  step={0.05}
                  value={cfg.spi}
                  onChange={(e) => patch({ spi: parseFloat(e.target.value) })}
                />
              </Field>
            </div>
          </div>

          <div className={`${GROUP_CLS} shrink-0 !mb-0`}>
            <h4 className={HEADER_CLS}>수리학적 압력 (Hydraulics)</h4>
            <div className="flex flex-col gap-2">
              <Field label="생산수 배압 (Permeate Back Pressure)">
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
                  <span className="text-[9px] text-slate-500 w-6">bar</span>
                </div>
              </Field>
              <Field label="전단 배관 손실 (Pre-stage ΔP)">
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
                  <span className="text-[9px] text-slate-500 w-6">bar</span>
                </div>
              </Field>
            </div>
          </div>

          <div
            className={`${GROUP_CLS} shrink-0 !mb-0 border-blue-900/30 bg-blue-900/5`}
          >
            <h4 className={`${HEADER_CLS} border-blue-900/20 text-blue-400`}>
              유량 제어 (Flow Routing)
            </h4>
            <div className="grid grid-cols-2 gap-3">
              <Field label="농축수 순환 (Brine Recycle)">
                <div className="flex items-center gap-1.5">
                  <Input
                    className={INPUT_CLS}
                    type="number"
                    step={0.1}
                    value={cfg.recirc_flow_m3h ?? 0}
                    onChange={(e) =>
                      patch({ recirc_flow_m3h: Number(e.target.value) })
                    }
                  />
                  <span className="text-[9px] text-slate-500 w-6">m³/h</span>
                </div>
              </Field>
              <Field label="바이패스 유량 (Bypass Flow)">
                <div className="flex items-center gap-1.5">
                  <Input
                    className={INPUT_CLS}
                    type="number"
                    step={0.1}
                    value={cfg.bypass_flow_m3h ?? 0}
                    onChange={(e) =>
                      patch({ bypass_flow_m3h: Number(e.target.value) })
                    }
                  />
                  <span className="text-[9px] text-slate-500 w-6">m³/h</span>
                </div>
              </Field>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
});
