// ui/src/features/simulation/editors/UnitForms.tsx

import React from 'react';
import { Field, Input } from '../components/Common';
import MembraneSelect from '../components/MembraneSelect';

import {
  UnitData,
  HRROConfig,
  ROConfig,
  UFConfig,
  NFConfig,
  MFConfig,
  BaseMembraneConfig,
} from '../model/types';

// ==============================
// 1. Helper Styles & Logic
// ==============================
const GROUP_CLS =
  'p-2 border border-slate-800 rounded-lg bg-slate-900/40 mb-2 shadow-sm flex flex-col';
const HEADER_CLS =
  'text-[11px] font-bold text-slate-300 mb-2 border-b border-slate-700/50 pb-1 flex items-center gap-1.5 shrink-0';
const INPUT_CLS =
  'h-7 text-xs bg-slate-950 border-slate-700 focus:border-blue-500 focus:bg-slate-900 transition-colors w-full rounded px-2 outline-none text-slate-100 placeholder:text-slate-600';
const READONLY_CLS =
  'h-7 bg-slate-800/80 border border-slate-700/50 rounded px-2 flex items-center text-xs font-bold';

const mapMembraneChange = (updates: any) => {
  const patch: any = {};
  if (updates.mode !== undefined) patch.membrane_mode = updates.mode;
  if (updates.model !== undefined) patch.membrane_model = updates.model;
  if (updates.area !== undefined) patch.custom_area_m2 = updates.area;
  if (updates.A !== undefined) patch.custom_A_lmh_bar = updates.A;
  if (updates.B !== undefined) patch.custom_B_lmh = updates.B;
  if (updates.rej !== undefined) patch.custom_salt_rejection_pct = updates.rej;
  return patch;
};

// ==============================
// 2. 공통 펌프 및 압력 설정 섹션
// ==============================
function PumpSection({
  cfg,
  onChange,
  defaultPressure,
}: {
  cfg: BaseMembraneConfig;
  onChange: (patch: Partial<BaseMembraneConfig>) => void;
  defaultPressure: number;
}) {
  const isEnabled = cfg.enable_pump ?? true;

  return (
    <div
      className={`${GROUP_CLS} border-emerald-900/30 bg-emerald-900/10 !mb-0 shrink-0`}
    >
      <div className="flex items-center justify-between mb-1.5 pb-1 border-b border-emerald-900/20">
        <h4 className="text-[11px] font-bold text-emerald-400 flex items-center gap-1.5">
          ⚡ 고압 펌프 설정
        </h4>
        <label className="flex items-center gap-1.5 cursor-pointer select-none">
          <input
            type="checkbox"
            checked={isEnabled}
            onChange={(e) => onChange({ enable_pump: e.target.checked })}
            className="w-3 h-3 rounded border-slate-600 bg-slate-800 text-emerald-500 focus:ring-0"
          />
          <span className="text-[10px] font-bold text-slate-300">
            {isEnabled ? '사용' : '우회(Bypass)'}
          </span>
        </label>
      </div>

      {isEnabled && (
        <div className="grid grid-cols-2 gap-2">
          <Field label="목표 압력 (bar)">
            <Input
              value={cfg.pump_pressure_bar ?? defaultPressure}
              onChange={(e) =>
                onChange({ pump_pressure_bar: Number(e.target.value) })
              }
              className={`${INPUT_CLS} text-emerald-400 font-bold bg-emerald-950/40 border-emerald-800/50`}
            />
          </Field>
          <Field label="펌프 효율 (%)">
            <Input
              value={cfg.pump_efficiency_pct ?? 75}
              onChange={(e) =>
                onChange({ pump_efficiency_pct: Number(e.target.value) })
              }
              className={INPUT_CLS}
            />
          </Field>
        </div>
      )}
    </div>
  );
}

// ==============================
// 3. HRRO Editor
// ==============================
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

// ==============================
// 4. RO Editor (WAVE Synchronized)
// ==============================
export function ROEditor({
  node,
  feed, // 🛑 [WAVE PATCH] 원수(Feed) 유량 데이터를 받아오기 위해 추가
  onChange,
}: {
  node: UnitData | undefined;
  feed?: any;
  onChange: (cfg: ROConfig) => void;
}) {
  if (!node || (node.kind !== 'RO' && node.kind !== 'NF'))
    return <div className="text-red-400 text-xs p-4">Invalid Data</div>;

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

    recirc_flow_m3h: 0.0, // 순환
    bypass_flow_m3h: 0.0, // 바이패스

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

  // 🛑 [WAVE PATCH] 실시간 유량(Flows) & 플럭스(Flux) 자동 계산 로직
  const feedFlow = feed?.flow_m3h ?? 100;
  let currentRecovery = cfg.recovery_target_pct ?? 75;
  let permeateFlow = 0;

  if (cfg.mode === 'flow') {
    permeateFlow = cfg.flow_target_m3h ?? 50;
    currentRecovery = feedFlow > 0 ? (permeateFlow / feedFlow) * 100 : 0;
  } else {
    // recovery 또는 pressure 모드일 경우 예상 유량 계산
    permeateFlow = feedFlow * (currentRecovery / 100);
  }

  // 막 면적 (기본 37.2m² = 일반적인 8인치 막)
  const currentArea = cfg.custom_area_m2 ?? cfg.membrane_area_m2 ?? 37.2;
  const totalArea = currentArea * (cfg.elements || 60);
  const flux = totalArea > 0 ? (permeateFlow * 1000) / totalArea : 0;

  return (
    <div
      className="flex flex-col h-full text-slate-100 p-1 overflow-hidden"
      onKeyDown={(e) => e.stopPropagation()}
    >
      {/* 📊 상단 대시보드 (WAVE Flows 패널) */}
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
          <span className="text-[10px] text-amber-400 font-bold mb-0.5">
            평균 플럭스 (Flux)
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
        {/* ========================================================= */}
        {/* 좌측: 배열(Array) 및 기본 운전 제어 */}
        {/* ========================================================= */}
        <div className="col-span-6 flex flex-col gap-2 h-full min-h-0 overflow-y-auto custom-scrollbar pr-1">
          <div className="shrink-0">
            <div className="px-2 py-1.5 bg-slate-800/90 border border-slate-700 rounded-t-md text-[10px] font-bold text-slate-200">
              Membrane Type ({node.kind})
            </div>
            <div className="p-2 border-x border-b border-slate-700 bg-slate-900/60 rounded-b-md">
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
            <h4 className={HEADER_CLS}>📏 모듈 배열 (Array Configuration)</h4>
            <div className="grid grid-cols-3 gap-2">
              <Field label="PV (베셀 수)">
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
              <Field label="수량 / PV">
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
              <Field label="총 모듈 수">
                <div
                  className={`${READONLY_CLS} text-slate-300 w-full justify-center bg-slate-800/50`}
                >
                  {cfg.elements} EA
                </div>
              </Field>
            </div>
          </div>

          <div
            className={`${GROUP_CLS} shrink-0 !mb-0 border-blue-900/40 bg-blue-900/10`}
          >
            <h4 className={`${HEADER_CLS} border-blue-900/30 text-blue-400`}>
              🎯 운전 제어 목표 (Operating Target)
            </h4>
            <div className="flex flex-col gap-2">
              <Field label="제어 기준">
                <select
                  className={`${INPUT_CLS} border-blue-800/50 bg-blue-950/40 font-bold text-blue-200`}
                  value={cfg.mode}
                  onChange={(e) => patch({ mode: e.target.value as any })}
                >
                  <option value="recovery">
                    Target Recovery (회수율 고정)
                  </option>
                  <option value="flow">Target Permeate Flow (유량 고정)</option>
                  <option value="pressure">Feed Pressure (압력 고정)</option>
                </select>
              </Field>

              <div className="mt-1">
                {cfg.mode === 'recovery' && (
                  <Field label="목표 회수율 (%)">
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
                  <Field label="목표 생산 유량 (m³/h)">
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
                  <Field label="고정 유입 압력 (bar)">
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

        {/* ========================================================= */}
        {/* 우측: 노후화(Ageing) 및 수리학(Hydraulics) */}
        {/* ========================================================= */}
        <div className="col-span-6 flex flex-col gap-2 h-full min-h-0 overflow-y-auto custom-scrollbar pr-1">
          <PumpSection cfg={cfg} onChange={patch} defaultPressure={15.0} />

          <div
            className={`${GROUP_CLS} shrink-0 !mb-0 border-amber-900/30 bg-amber-900/5`}
          >
            <h4 className={`${HEADER_CLS} border-amber-900/20 text-amber-500`}>
              ⏳ 노후화 및 오염 계수 (Ageing & Fouling)
            </h4>
            <div className="grid grid-cols-2 gap-2">
              <Field label="운전 년수 (Age)">
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
                  <span className="text-[9px] text-slate-500 w-6">Yrs</span>
                </div>
              </Field>
              <div className="hidden" />

              <Field label="유량 계수 (Flow Factor)">
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
            <h4 className={HEADER_CLS}>💧 수리학적 압력 (Hydraulics)</h4>
            <div className="flex flex-col gap-2">
              <Field label="생산수 배압 (Permeate Pressure)">
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

          {/* 🛑 [WAVE PATCH] 추가된 Flow Routing 섹션 */}
          <div
            className={`${GROUP_CLS} shrink-0 !mb-0 border-blue-900/30 bg-blue-900/5`}
          >
            <h4 className={`${HEADER_CLS} border-blue-900/20 text-blue-400`}>
              🌊 유량 상세 (Flow Routing)
            </h4>
            <div className="grid grid-cols-2 gap-2">
              <Field label="농축수 순환 (Recycle)">
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
              <Field label="바이패스 (Bypass)">
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
}

// ==============================
// 5. UF Editor
// ==============================
export function UFEditor({
  node,
  onChange,
}: {
  node: UnitData | undefined;
  onChange: (cfg: UFConfig) => void;
}) {
  if (!node || node.kind !== 'UF')
    return <div className="text-red-400 text-xs p-4">Invalid Data</div>;

  // 기본값 설정 (WAVE Default 1:1 매칭)
  const cfg = {
    elements: 50,
    design_flux_lmh: 55.5,
    strainer_recovery_pct: 99.5,
    strainer_size_micron: 150.0,
    uf_maintenance: {
      filtration_duration_min: 60,
      backwash_duration_sec: 60,
      air_scour_duration_sec: 30,
      forward_flush_duration_sec: 30,
      acid_ceb_interval_h: 0,
      alkali_ceb_interval_h: 0,
      cip_interval_d: 0,
      mini_cip_interval_d: 0,
      backwash_flux_lmh: 100.0,
      ceb_flux_lmh: 80.0,
      forward_flush_flow_m3h_per_mod: 2.83,
      air_flow_nm3h_per_mod: 12.0,
    },
    ...node.cfg,
  } as UFConfig & { uf_maintenance: any }; // 타입 우회

  const patch = (p: Partial<UFConfig>) => onChange({ ...cfg, ...p });

  const patchMaintenance = (p: any) => {
    patch({
      uf_maintenance: {
        ...(cfg.uf_maintenance || {}),
        ...p,
      },
    } as any);
  };

  return (
    <div
      className="flex flex-col h-full text-slate-100 p-1 overflow-hidden"
      onKeyDown={(e) => e.stopPropagation()}
    >
      <div className="flex-1 grid grid-cols-12 gap-3 overflow-hidden">
        {/* ========================================================= */}
        {/* 좌측: 기본 설계 및 하드웨어 */}
        {/* ========================================================= */}
        <div className="col-span-7 flex flex-col gap-2 h-full min-h-0">
          <PumpSection cfg={cfg} onChange={patch} defaultPressure={3.4} />

          {/* 스트레이너 설정 */}
          <div
            className={`${GROUP_CLS} shrink-0 !mb-0 border-amber-900/40 bg-amber-900/10`}
          >
            <h4 className={`${HEADER_CLS} border-amber-900/30 text-amber-500`}>
              🛡️ 전처리 스트레이너 (Strainer Specification)
            </h4>
            <div className="grid grid-cols-2 gap-3">
              <Field label="스트레이너 회수율 (%)">
                <Input
                  className={`${INPUT_CLS} text-amber-400 font-bold`}
                  type="number"
                  step={0.1}
                  value={cfg.strainer_recovery_pct}
                  onChange={(e) =>
                    patch({ strainer_recovery_pct: Number(e.target.value) })
                  }
                />
              </Field>
              <Field label="스트레이너 크기 (μm)">
                <Input
                  className={INPUT_CLS}
                  type="number"
                  value={cfg.strainer_size_micron}
                  onChange={(e) =>
                    patch({ strainer_size_micron: Number(e.target.value) })
                  }
                />
              </Field>
            </div>
          </div>

          <MembraneSelect
            unitType="UF"
            mode={cfg.membrane_mode}
            model={cfg.membrane_model}
            area={cfg.custom_area_m2 ?? cfg.membrane_area_m2 ?? 77.0}
            A={cfg.custom_A_lmh_bar ?? cfg.membrane_A_lmh_bar}
            onChange={(updates) => patch(mapMembraneChange(updates))}
          />

          <div className={`${GROUP_CLS} flex-1 !mb-0`}>
            <h4 className={HEADER_CLS}>
              ⚙️ 모듈 선택 및 유량 (Module Selection)
            </h4>
            <div className="grid grid-cols-2 gap-3">
              <Field label="총 모듈 수 (Total Modules)">
                <Input
                  className={INPUT_CLS}
                  type="number"
                  value={cfg.elements}
                  onChange={(e) => patch({ elements: Number(e.target.value) })}
                />
              </Field>
              <Field label="목표 플럭스 (Filtrate Flux, LMH)">
                <Input
                  className={`${INPUT_CLS} text-blue-300 font-bold bg-blue-950/40`}
                  type="number"
                  step={0.1}
                  value={cfg.design_flux_lmh}
                  onChange={(e) =>
                    patch({ design_flux_lmh: Number(e.target.value) })
                  }
                />
              </Field>
            </div>
          </div>
        </div>

        {/* ========================================================= */}
        {/* 우측: WAVE 상세 유지보수 사이클 및 유량 */}
        {/* ========================================================= */}
        <div className="col-span-5 flex flex-col gap-2 h-full min-h-0">
          {/* Design Instantaneous Flux and Flow Rates */}
          <div
            className={`${GROUP_CLS} flex-1 !mb-0 overflow-y-auto custom-scrollbar pr-1 border-blue-900/30 bg-blue-900/5`}
          >
            <h4 className={`${HEADER_CLS} text-blue-400 border-blue-900/30`}>
              💦 설계 순시 유량 (Flux & Flow Rates)
            </h4>
            <div className="flex flex-col gap-2">
              <Field label="역세 플럭스 (Backwash Flux)">
                <div className="flex items-center gap-1.5">
                  <Input
                    className={INPUT_CLS}
                    value={cfg.uf_maintenance?.backwash_flux_lmh}
                    onChange={(e) =>
                      patchMaintenance({
                        backwash_flux_lmh: Number(e.target.value),
                      })
                    }
                  />
                  <span className="text-[10px] text-slate-500 w-6">LMH</span>
                </div>
              </Field>
              <Field label="CEB 플럭스 (CEB Flux)">
                <div className="flex items-center gap-1.5">
                  <Input
                    className={INPUT_CLS}
                    value={cfg.uf_maintenance?.ceb_flux_lmh}
                    onChange={(e) =>
                      patchMaintenance({ ceb_flux_lmh: Number(e.target.value) })
                    }
                  />
                  <span className="text-[10px] text-slate-500 w-6">LMH</span>
                </div>
              </Field>
              <Field label="포워드 플러시 (m³/h/module)">
                <div className="flex items-center gap-1.5">
                  <Input
                    className={INPUT_CLS}
                    value={cfg.uf_maintenance?.forward_flush_flow_m3h_per_mod}
                    onChange={(e) =>
                      patchMaintenance({
                        forward_flush_flow_m3h_per_mod: Number(e.target.value),
                      })
                    }
                  />
                </div>
              </Field>
              <Field label="공기 유량 (Nm³/h/module)">
                <div className="flex items-center gap-1.5">
                  <Input
                    className={INPUT_CLS}
                    value={cfg.uf_maintenance?.air_flow_nm3h_per_mod}
                    onChange={(e) =>
                      patchMaintenance({
                        air_flow_nm3h_per_mod: Number(e.target.value),
                      })
                    }
                  />
                </div>
              </Field>
            </div>
          </div>

          {/* Design Cycle Intervals */}
          <div
            className={`${GROUP_CLS} flex-1 !mb-0 overflow-y-auto custom-scrollbar pr-1`}
          >
            <h4 className={HEADER_CLS}>
              ⏱️ 설계 주기 (Design Cycle Intervals)
            </h4>
            <div className="flex flex-col gap-2">
              <Field label="여과 시간 (Filtration Duration)">
                <div className="flex items-center gap-1.5">
                  <Input
                    className={`${INPUT_CLS} text-emerald-400 font-bold`}
                    value={cfg.uf_maintenance?.filtration_duration_min}
                    onChange={(e) =>
                      patchMaintenance({
                        filtration_duration_min: Number(e.target.value),
                      })
                    }
                  />
                  <span className="text-[10px] text-slate-500 w-6">min</span>
                </div>
              </Field>
              <Field label="산성 CEB 주기 (Acid CEB)">
                <div className="flex items-center gap-1.5">
                  <Input
                    className={INPUT_CLS}
                    value={cfg.uf_maintenance?.acid_ceb_interval_h}
                    onChange={(e) =>
                      patchMaintenance({
                        acid_ceb_interval_h: Number(e.target.value),
                      })
                    }
                  />
                  <span className="text-[10px] text-slate-500 w-6">h</span>
                </div>
              </Field>
              <Field label="알칼리 CEB (Alkali/Oxidant CEB)">
                <div className="flex items-center gap-1.5">
                  <Input
                    className={INPUT_CLS}
                    value={cfg.uf_maintenance?.alkali_ceb_interval_h}
                    onChange={(e) =>
                      patchMaintenance({
                        alkali_ceb_interval_h: Number(e.target.value),
                      })
                    }
                  />
                  <span className="text-[10px] text-slate-500 w-6">h</span>
                </div>
              </Field>
              <Field label="CIP 주기 (CIP)">
                <div className="flex items-center gap-1.5">
                  <Input
                    className={INPUT_CLS}
                    value={cfg.uf_maintenance?.cip_interval_d}
                    onChange={(e) =>
                      patchMaintenance({
                        cip_interval_d: Number(e.target.value),
                      })
                    }
                  />
                  <span className="text-[10px] text-slate-500 w-6">d</span>
                </div>
              </Field>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ==============================
// 6. NF/MF/Pump
// ==============================

// 🛑 [WAVE PATCH] NF는 RO와 완벽히 동일한 구조(Array, Fouling 등)를 사용하므로 ROEditor 재사용
export function NFEditor(props: any) {
  return <ROEditor {...props} />;
}

export function MFEditor({ node, onChange }: any) {
  const cfg = node.cfg || {};
  return (
    <div className="space-y-3 p-4">
      <MembraneSelect
        unitType="MF"
        mode={cfg.membrane_mode}
        area={cfg.custom_area_m2 ?? cfg.membrane_area_m2}
        A={cfg.custom_A_lmh_bar ?? cfg.membrane_A_lmh_bar}
        onChange={(u) => onChange({ ...cfg, ...mapMembraneChange(u) })}
      />
      <div className="text-xs text-slate-400 mt-2">
        * 상세 설정 폼은 추후 확장 예정입니다.
      </div>
    </div>
  );
}

export function PumpEditor({ node }: any) {
  return (
    <div className="p-4 text-center text-xs text-slate-500 bg-slate-900/50 rounded-lg border border-slate-700 border-dashed">
      단독 고압 펌프(Pump) 노드 설정입니다.
    </div>
  );
}
