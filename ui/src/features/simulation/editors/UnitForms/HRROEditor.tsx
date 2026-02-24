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
    return <div className="text-red-400 p-4">Invalid Data</div>;

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
    pf_feed_ratio_pct: 120,
    pf_recovery_pct: 20,
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
      {/* 📊 상단 대시보드 */}
      <div className="grid grid-cols-4 gap-2 p-2 bg-slate-900 border border-slate-700 rounded-lg shadow-inner shrink-0 mb-2">
        <div className="flex flex-col items-center border-r border-slate-700">
          <span className="text-[10px] text-slate-400 font-bold mb-0.5">
            유입 유량 (Feed)
          </span>
          <span className="font-mono text-base font-bold text-slate-100">
            {feedFlow.toFixed(1)}{' '}
            <small className="text-[9px] font-normal text-slate-500">
              m³/h
            </small>
          </span>
        </div>
        <div className="flex flex-col items-center border-r border-slate-700">
          <span className="text-[10px] text-emerald-400 font-bold mb-0.5">
            목표 회수율
          </span>
          <span className="font-mono text-base font-bold text-emerald-400">
            {cfg.stop_recovery_pct}{' '}
            <small className="text-[9px] font-normal text-emerald-600/70">
              %
            </small>
          </span>
        </div>
        <div className="flex flex-col items-center border-r border-slate-700">
          <span className="text-[10px] text-blue-400 font-bold mb-0.5">
            생산 유량 (Permeate)
          </span>
          <span className="font-mono text-base font-bold text-blue-300">
            {permeateFlow.toFixed(1)}{' '}
            <small className="text-[9px] font-normal text-blue-500/70">
              m³/h
            </small>
          </span>
        </div>
        <div className="flex flex-col items-center">
          <span className="text-[10px] text-slate-400 font-bold mb-0.5">
            총 막 면적 (Area)
          </span>
          <span className="font-mono text-base font-bold text-slate-300">
            {totalArea.toFixed(1)}{' '}
            <small className="text-[9px] font-normal text-slate-500">m²</small>
          </span>
        </div>
      </div>

      <div className="flex-1 grid grid-cols-12 gap-3 overflow-hidden">
        {/* ========================================================= */}
        {/* 좌측: 기본 설정 및 수리학적 디테일 */}
        {/* ========================================================= */}
        <div className="col-span-8 flex flex-col gap-2 h-full min-h-0">
          <div className="flex gap-3 flex-1 min-h-0">
            {/* 1. 기본 운전 설정 */}
            <div className={`${GROUP_CLS} flex-1 !mb-0`}>
              <h4 className={HEADER_CLS}>⚙️ 기본 운전 설정 (Pass 1)</h4>
              <div className="flex flex-col gap-2 overflow-y-auto custom-scrollbar pr-1">
                <Field label="스테이지 (단) 수">
                  <div className="flex items-center h-7 gap-2 px-2 border border-slate-700 bg-slate-900/50 rounded">
                    <input
                      type="radio"
                      checked
                      readOnly
                      className="w-3 h-3 text-blue-500 bg-slate-800 border-slate-600 focus:ring-0"
                    />
                    <span className="text-slate-300 text-[11px] font-bold">
                      1 단 (Stage)
                    </span>
                  </div>
                </Field>
                <Field label="유량 계수 (Flow Factor)">
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
                <div className="flex flex-col gap-1">
                  <span className="text-[10px] font-medium text-slate-400">
                    수온 기준 (Temperature)
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
                <Field label="생산수 배압 (Back Pressure)">
                  <div className="flex items-center gap-1.5">
                    <Input
                      className={INPUT_CLS}
                      type="number"
                      value={cfg.permeate_back_pressure_bar}
                      onChange={(e) =>
                        patch({
                          permeate_back_pressure_bar: Number(e.target.value),
                        })
                      }
                    />
                    <span className="text-[10px] text-slate-500">bar</span>
                  </div>
                </Field>
              </div>
            </div>

            {/* 2. 유량 상세 */}
            <div
              className={`${GROUP_CLS} flex-1 !mb-0 border-blue-900/40 bg-blue-900/10`}
            >
              <h4 className={`${HEADER_CLS} border-blue-900/30 text-blue-400`}>
                🌊 유량 상세 (Flows)
              </h4>
              <div className="flex flex-col gap-2 overflow-y-auto custom-scrollbar pr-1">
                <Field label="유입 유량 (Feed Flow)">
                  <div className="flex items-center gap-1.5">
                    <Input
                      className={`${INPUT_CLS} text-blue-300 font-bold`}
                      value={cfg.feed_flow_m3h ?? ''}
                      placeholder="100"
                      onChange={(e) =>
                        patch({ feed_flow_m3h: Number(e.target.value) })
                      }
                    />
                    <span className="text-[10px] text-slate-500 w-7">m³/h</span>
                  </div>
                </Field>
                <Field label="시스템 회수율 (Recovery)">
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
                    <span className="text-[10px] text-slate-500 w-7">%</span>
                  </div>
                </Field>
                <Field label="생산 유량 (Permeate)">
                  <div className="flex items-center gap-1.5">
                    <div
                      className={`${READONLY_CLS} text-emerald-300 flex-1 justify-end`}
                    >
                      {permeateFlow.toFixed(1)}
                    </div>
                    <span className="text-[10px] text-slate-500 w-7">m³/h</span>
                  </div>
                </Field>
                <Field label="평균 플럭스 (Avg. Flux)">
                  <div className="flex items-center gap-1.5">
                    <div
                      className={`${READONLY_CLS} text-amber-300 flex-1 justify-end`}
                    >
                      {flux.toFixed(1)}
                    </div>
                    <span className="text-[10px] text-slate-500 w-7">LMH</span>
                  </div>
                </Field>
                <Field label="농축수 순환 (Recycle)">
                  <div className="flex items-center gap-1.5">
                    <Input
                      className={INPUT_CLS}
                      value={cfg.recirc_flow_m3h}
                      onChange={(e) =>
                        patch({ recirc_flow_m3h: Number(e.target.value) })
                      }
                    />
                    <span className="text-[10px] text-slate-500 w-7">m³/h</span>
                  </div>
                </Field>
                <Field label="바이패스 (Bypass)">
                  <div className="flex items-center gap-1.5">
                    <Input
                      className={INPUT_CLS}
                      value={cfg.bypass_flow_m3h}
                      onChange={(e) =>
                        patch({ bypass_flow_m3h: Number(e.target.value) })
                      }
                    />
                    <span className="text-[10px] text-slate-500 w-7">m³/h</span>
                  </div>
                </Field>
              </div>
            </div>
          </div>

          {/* 하단 멤브레인 정보 */}
          <div className="shrink-0">
            <div className="px-2 py-1.5 bg-slate-800/90 border-t border-x border-slate-700 rounded-t-md text-[10px] font-bold text-slate-200 shadow-sm">
              멤브레인 모델 및 제원 (Element Type Specs)
            </div>
            <div className="p-2 border border-slate-700 bg-slate-900/60 rounded-b-md">
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

              <div className="grid grid-cols-2 gap-3 mt-2 pt-2 border-t border-slate-700/60">
                <div className="flex justify-between items-center bg-slate-800/60 p-1.5 rounded border border-slate-700/60">
                  <span className="text-[10px] text-slate-400">
                    총 엘리먼트 수
                  </span>
                  <span className="font-bold text-[11px] text-slate-100">
                    {cfg.elements}{' '}
                    <small className="font-normal text-[9px] text-slate-500">
                      EA
                    </small>
                  </span>
                </div>
                <div className="flex justify-between items-center bg-amber-900/10 p-1.5 rounded border border-amber-900/40">
                  <span className="text-[10px] text-amber-500/80">
                    배관 차압 (Pre-stage ΔP)
                  </span>
                  <div className="flex items-center gap-1">
                    <Input
                      className="h-5 w-12 text-right text-[10px] bg-slate-950 border-slate-700 text-amber-400 font-bold px-1"
                      value={cfg.pre_stage_dp_bar}
                      onChange={(e) =>
                        patch({ pre_stage_dp_bar: Number(e.target.value) })
                      }
                    />
                    <span className="text-[9px] text-amber-600/60">bar</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* ========================================================= */}
        {/* 우측: 고급 설정 (Engineering Data) */}
        {/* ========================================================= */}
        <div className="col-span-4 flex flex-col gap-2 h-full min-h-0">
          <div className="px-2 py-1.5 bg-slate-800/80 border border-slate-700 rounded-md text-[10px] font-bold text-slate-200 tracking-wide shrink-0 shadow-sm flex items-center justify-between">
            <span>고급 설정 (Advanced)</span>
            <span className="text-[9px] font-normal text-slate-400">
              ⚙️ Engineering
            </span>
          </div>

          <div className={`${GROUP_CLS} shrink-0 !mb-0`}>
            <h5 className="text-[10px] text-slate-400 font-bold mb-1.5 uppercase">
              모듈 하드웨어 구성
            </h5>
            <div className="grid grid-cols-3 gap-1.5">
              <Field label="베셀 (PV)">
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
              <Field label="수량 / PV">
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
              <div className="flex flex-col justify-end">
                <div className="text-[10px] font-medium text-slate-400 mb-1 uppercase">
                  총 수량
                </div>
                <div
                  className={`${READONLY_CLS} justify-center text-[11px] text-slate-200`}
                >
                  {cfg.elements}
                </div>
              </div>
            </div>
          </div>

          <div className="shrink-0">
            <PumpSection cfg={cfg} onChange={patch} defaultPressure={50.0} />
          </div>

          {/* 플러그 흐름 & 운전 제한 */}
          <div className="grid grid-cols-2 gap-2 flex-1 min-h-0">
            <div className="flex flex-col p-2 border border-blue-900/40 bg-blue-900/10 rounded-lg">
              <h4 className="text-blue-400 font-bold mb-2 text-[10px] uppercase">
                플러그 흐름 (CCRO)
              </h4>
              <div className="flex flex-col gap-2">
                <Field label="반송 비율 (% to Feed)">
                  <Input
                    className={INPUT_CLS}
                    value={cfg.pf_feed_ratio_pct}
                    onChange={(e) =>
                      patch({ pf_feed_ratio_pct: Number(e.target.value) })
                    }
                  />
                </Field>
                <Field label="단일 패스 회수율 (%)">
                  <Input
                    className={INPUT_CLS}
                    value={cfg.pf_recovery_pct}
                    onChange={(e) =>
                      patch({ pf_recovery_pct: Number(e.target.value) })
                    }
                  />
                </Field>
              </div>
            </div>

            <div className="flex flex-col p-2 border border-slate-700 bg-slate-800/40 rounded-lg">
              <h4 className="text-slate-300 font-bold mb-2 text-[10px] uppercase">
                운전 제한 (Limits)
              </h4>
              <div className="flex flex-col gap-2">
                <Field label="최대 운전 시간 (min)">
                  <Input
                    className={INPUT_CLS}
                    value={cfg.max_minutes}
                    onChange={(e) =>
                      patch({ max_minutes: Number(e.target.value) })
                    }
                  />
                </Field>
                <Field label="시스템 체적 (m³)">
                  <Input
                    className={INPUT_CLS}
                    value={cfg.loop_volume_m3}
                    onChange={(e) =>
                      patch({ loop_volume_m3: Number(e.target.value) })
                    }
                  />
                </Field>
                <Field label="최대 허용 압력 (bar)">
                  <Input
                    className={`${INPUT_CLS} text-red-400 font-bold border-red-900/30 bg-red-950/10`}
                    value={cfg.burst_pressure_limit_bar}
                    onChange={(e) =>
                      patch({
                        burst_pressure_limit_bar: Number(e.target.value),
                      })
                    }
                  />
                </Field>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
