// ui\src\features\simulation\editors\UnitForms.tsx

import React from 'react';
// ✅ [경로 수정] components가 같은 레벨에 있음
import { Field, Input } from '../components/Common';

// ✅ [경로 수정] MembraneSelect도 components 폴더로 이동했으므로 상대 경로 사용
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
// Helper Styles
// ==============================
const GROUP_CLS =
  'p-2.5 border border-slate-800 rounded bg-slate-950/30 mb-2.5';
const HEADER_CLS =
  'text-[11px] font-bold text-slate-400 mb-2 uppercase tracking-wide border-b border-slate-800/50 pb-1';
const INPUT_CLS =
  'h-7 text-sm bg-slate-900 border-slate-700 focus:border-blue-500 focus:bg-slate-800 transition-colors w-full rounded px-2 outline-none text-slate-200';

// ==============================
// 공통 펌프 설정 컴포넌트
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
    <div className={`${GROUP_CLS} border-emerald-900/30 bg-emerald-950/10`}>
      <div className="flex items-center justify-between mb-2 pb-1 border-b border-emerald-900/20">
        <h4 className="text-xs font-bold text-emerald-400 flex items-center gap-1.5">
          ⚡ Feed Pump Settings
        </h4>
        <label className="flex items-center gap-1.5 cursor-pointer select-none">
          <input
            type="checkbox"
            checked={isEnabled}
            onChange={(e) => onChange({ enable_pump: e.target.checked })}
            className="w-3.5 h-3.5 rounded border-slate-600 bg-slate-800 text-emerald-500 focus:ring-0"
          />
          <span className="text-[10px] uppercase font-bold text-slate-400">
            {isEnabled ? 'Active' : 'Bypass'}
          </span>
        </label>
      </div>

      {isEnabled && (
        <div className="grid grid-cols-2 gap-2">
          <Field label="Target Pressure (bar)">
            <Input
              value={cfg.pump_pressure_bar ?? defaultPressure}
              onChange={(e) =>
                onChange({ pump_pressure_bar: Number(e.target.value) })
              }
              className={`${INPUT_CLS} text-emerald-400 font-bold bg-emerald-950/20 border-emerald-500/30`}
            />
          </Field>
          <Field label="Efficiency (%)">
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
// 1. RO Editor
// ==============================
export function ROEditor({
  node,
  onChange,
}: {
  node: UnitData | undefined;
  onChange: (cfg: ROConfig) => void;
}) {
  const data = node;
  if (!data || data.kind !== 'RO')
    return <div className="text-red-400 text-xs">Invalid Data</div>;

  const raw = (data.cfg as ROConfig | undefined) ?? {};
  const cfg: ROConfig = {
    elements: 6,
    mode: 'pressure',
    pressure_bar: 16,
    recovery_target_pct: 75,
    ro_n_stages: 1,
    ro_flow_factor: 0.85,
    ro_temp_C: 25,
    ro_pass_permeate_back_pressure_bar: 0,
    ro_stage_pre_delta_p_bar: 0.31,
    ...raw,
  };
  const patch = (p: Partial<ROConfig>) => onChange({ ...cfg, ...p });

  return (
    <div
      className="space-y-2 text-slate-100 text-xs"
      onKeyDown={(e) => e.stopPropagation()}
    >
      <PumpSection cfg={cfg} onChange={patch} defaultPressure={15.0} />

      {/* ✅ MembraneSelect 컴포넌트 */}
      <div className="mb-2">
        <MembraneSelect
          unitType="RO"
          mode={cfg.membrane_mode}
          model={cfg.membrane_model}
          area={cfg.custom_area_m2 ?? cfg.membrane_area_m2}
          A={cfg.custom_A_lmh_bar ?? cfg.membrane_A_lmh_bar}
          B={cfg.custom_B_lmh ?? cfg.membrane_B_lmh}
          rej={cfg.custom_salt_rejection_pct ?? cfg.membrane_salt_rejection_pct}
          onChange={patch}
        />
      </div>

      <div className={GROUP_CLS}>
        <h4 className={HEADER_CLS}>Pass Configuration</h4>
        <div className="grid grid-cols-2 gap-2">
          <Field label="# Stages">
            <Input
              className={INPUT_CLS}
              value={cfg.ro_n_stages ?? 1}
              onChange={(e) => patch({ ro_n_stages: Number(e.target.value) })}
            />
          </Field>
          <Field label="Flow Factor">
            <Input
              className={INPUT_CLS}
              value={cfg.ro_flow_factor ?? 0.85}
              onChange={(e) =>
                patch({ ro_flow_factor: Number(e.target.value) })
              }
            />
          </Field>
          <Field label="Temp (°C)">
            <Input
              className={INPUT_CLS}
              value={cfg.ro_temp_C ?? 25}
              onChange={(e) => patch({ ro_temp_C: Number(e.target.value) })}
            />
          </Field>
          <Field label="Back Press (bar)">
            <Input
              className={INPUT_CLS}
              value={cfg.ro_pass_permeate_back_pressure_bar ?? 0}
              onChange={(e) =>
                patch({
                  ro_pass_permeate_back_pressure_bar: Number(e.target.value),
                })
              }
            />
          </Field>
        </div>
      </div>

      <div className={GROUP_CLS}>
        <h4 className={HEADER_CLS}>Control Strategy</h4>
        <div className="mb-2 flex gap-4 bg-slate-900 p-1.5 rounded border border-slate-800">
          <label className="flex items-center gap-1.5 cursor-pointer text-xs">
            <input
              type="radio"
              className="bg-slate-800 border-slate-600 text-blue-500"
              checked={cfg.mode === 'pressure'}
              onChange={() => patch({ mode: 'pressure' })}
            />{' '}
            Fix Pressure
          </label>
          <label className="flex items-center gap-1.5 cursor-pointer text-xs">
            <input
              type="radio"
              className="bg-slate-800 border-slate-600 text-blue-500"
              checked={cfg.mode === 'recovery'}
              onChange={() => patch({ mode: 'recovery' })}
            />{' '}
            Fix Recovery
          </label>
        </div>
        <div className="grid grid-cols-2 gap-2">
          {cfg.mode === 'pressure' ? (
            <Field label="Feed Press (bar)">
              <Input
                className={INPUT_CLS}
                value={cfg.pressure_bar ?? 16}
                onChange={(e) =>
                  patch({ pressure_bar: Number(e.target.value) })
                }
              />
            </Field>
          ) : (
            <Field label="Recovery (%)">
              <Input
                className={INPUT_CLS}
                value={cfg.recovery_target_pct ?? 75}
                onChange={(e) =>
                  patch({ recovery_target_pct: Number(e.target.value) })
                }
              />
            </Field>
          )}
        </div>
      </div>

      <div className={GROUP_CLS}>
        <h4 className={HEADER_CLS}>Stage Layout</h4>
        <div className="grid grid-cols-2 gap-2">
          <Field label="PV / Stage">
            <Input
              className={INPUT_CLS}
              value={cfg.ro_stage_pv_per_stage}
              onChange={(e) =>
                patch({
                  ro_stage_pv_per_stage: Number(e.target.value),
                  elements:
                    Number(e.target.value) * (cfg.ro_stage_els_per_pv || 6),
                })
              }
            />
          </Field>
          <Field label="Elements / PV">
            <Input
              className={INPUT_CLS}
              value={cfg.ro_stage_els_per_pv}
              onChange={(e) =>
                patch({
                  ro_stage_els_per_pv: Number(e.target.value),
                  elements:
                    (cfg.ro_stage_pv_per_stage || 1) * Number(e.target.value),
                })
              }
            />
          </Field>
          <Field label="Total Elements">
            <Input
              className={`${INPUT_CLS} bg-slate-800/50 text-slate-400`}
              value={cfg.elements}
              readOnly
            />
          </Field>
          <Field label="Boost Press (bar)">
            <Input
              className={INPUT_CLS}
              value={cfg.ro_stage_boost_press_bar ?? 0}
              onChange={(e) =>
                patch({ ro_stage_boost_press_bar: Number(e.target.value) })
              }
            />
          </Field>
          <Field label="Back Press (bar)">
            <Input
              className={INPUT_CLS}
              value={cfg.ro_stage_back_pressure_bar ?? 0}
              onChange={(e) =>
                patch({ ro_stage_back_pressure_bar: Number(e.target.value) })
              }
            />
          </Field>
          <Field label="Pre-stage ΔP">
            <Input
              className={INPUT_CLS}
              value={cfg.ro_stage_pre_delta_p_bar ?? 0.31}
              onChange={(e) =>
                patch({ ro_stage_pre_delta_p_bar: Number(e.target.value) })
              }
            />
          </Field>
        </div>
      </div>
    </div>
  );
}

// ==============================
// 2. UF Editor
// ==============================
export function UFEditor({
  node,
  onChange,
}: {
  node: UnitData | undefined;
  onChange: (cfg: UFConfig) => void;
}) {
  const data = node;
  if (!data || data.kind !== 'UF')
    return <div className="text-red-400 text-xs">Invalid Data</div>;

  const raw = (data.cfg as UFConfig | undefined) ?? {};
  const cfg: UFConfig = {
    elements: 6,
    filtration_duration_min: 30,
    uf_backwash_duration_s: 60,
    filtrate_flux_lmh_25C: 50,
    backwash_flux_lmh: 80,
    ...raw,
  };
  const patch = (p: Partial<UFConfig>) => onChange({ ...cfg, ...p });

  return (
    <div
      className="space-y-2 text-slate-100 text-xs"
      onKeyDown={(e) => e.stopPropagation()}
    >
      <PumpSection cfg={cfg} onChange={patch} defaultPressure={3.0} />

      {/* ✅ MembraneSelect 컴포넌트 */}
      <div className="mb-2">
        <MembraneSelect
          unitType="UF"
          mode={cfg.membrane_mode}
          model={cfg.membrane_model}
          area={cfg.custom_area_m2 ?? cfg.membrane_area_m2}
          A={cfg.custom_A_lmh_bar ?? cfg.membrane_A_lmh_bar}
          // UF는 B, Rej 없음
          onChange={patch}
        />
      </div>

      <div className={GROUP_CLS}>
        <h4 className={HEADER_CLS}>Module Configuration</h4>
        <div className="grid grid-cols-2 gap-2">
          <Field label="# Modules">
            <Input
              className={INPUT_CLS}
              value={cfg.elements}
              onChange={(e) => patch({ elements: Number(e.target.value) })}
            />
          </Field>
        </div>
      </div>

      <div className={GROUP_CLS}>
        <h4 className={HEADER_CLS}>Operation Cycle</h4>
        <div className="grid grid-cols-2 gap-2">
          <Field label="Filtration (min)">
            <Input
              className={INPUT_CLS}
              value={cfg.filtration_duration_min}
              onChange={(e) =>
                patch({ filtration_duration_min: Number(e.target.value) })
              }
            />
          </Field>
          <Field label="Backwash (sec)">
            <Input
              className={INPUT_CLS}
              value={cfg.uf_backwash_duration_s}
              onChange={(e) =>
                patch({ uf_backwash_duration_s: Number(e.target.value) })
              }
            />
          </Field>
        </div>
      </div>

      <div className={GROUP_CLS}>
        <h4 className={HEADER_CLS}>Flux Design</h4>
        <div className="grid grid-cols-2 gap-2">
          <Field label="Op Flux (lmh)">
            <Input
              className={INPUT_CLS}
              value={cfg.filtrate_flux_lmh_25C}
              onChange={(e) =>
                patch({ filtrate_flux_lmh_25C: Number(e.target.value) })
              }
            />
          </Field>
          <Field label="BW Flux (lmh)">
            <Input
              className={INPUT_CLS}
              value={cfg.backwash_flux_lmh}
              onChange={(e) =>
                patch({ backwash_flux_lmh: Number(e.target.value) })
              }
            />
          </Field>
        </div>
      </div>
    </div>
  );
}

// ==============================
// 3. HRRO Editor (Updated for WAVE Parity)
// ==============================================

export function HRROEditor({
  node,
  onChange,
}: {
  node: UnitData | undefined;
  onChange: (cfg: HRROConfig) => void;
}) {
  const data = node;
  if (!data || data.kind !== 'HRRO')
    return <div className="text-red-400 text-xs">Invalid Data</div>;

  const raw = (data.cfg as HRROConfig | undefined) ?? {};

  // [보완] WAVE 기본값에 맞춰 초기값 설정
  const cfg: HRROConfig = {
    elements: 6,
    p_set_bar: 28,
    recirc_flow_m3h: 12,
    bleed_m3h: 0,
    loop_volume_m3: 2,
    makeup_tds_mgL: 35000,
    timestep_s: 5,
    max_minutes: 30,
    stop_permeate_tds_mgL: null,
    stop_recovery_pct: 90, // WAVE 목표 회수율 반영

    // [신규 추가 필드 기본값]
    pf_feed_ratio_pct: 120, // WAVE Default
    pf_recovery_pct: 20, // WAVE Default
    hrro_flow_factor: 0.85, // 오염 계수
    hrro_stage_pre_delta_p_bar: 0.31, // 배관 손실

    ...raw,
  };

  const patch = (p: Partial<HRROConfig>) => onChange({ ...cfg, ...p });

  return (
    <div
      className="space-y-2 text-slate-100 text-xs"
      onKeyDown={(e) => e.stopPropagation()}
    >
      <PumpSection cfg={cfg} onChange={patch} defaultPressure={20.0} />

      {/* ✅ MembraneSelect 컴포넌트 */}
      <div className="mb-2">
        <MembraneSelect
          unitType="HRRO"
          model={cfg.membrane_model ?? 'filmtec-soar-7000i'}
          area={cfg.membrane_area_m2}
          A={cfg.membrane_A_lmh_bar}
          B={cfg.membrane_B_lmh}
          rej={cfg.membrane_salt_rejection_pct}
          onChange={patch}
        />
      </div>

      {/* [신규] Plug Flow (PF) 설정 - WAVE 하이브리드 모드 지원 */}
      <div className={`${GROUP_CLS} border-blue-900/30 bg-blue-950/10`}>
        <h4 className={`${HEADER_CLS} text-blue-400`}>
          Plug Flow (PF) Settings
        </h4>
        <div className="grid grid-cols-2 gap-2">
          <Field label="PF Feed Ratio (%)">
            <Input
              className={INPUT_CLS}
              value={cfg.pf_feed_ratio_pct ?? 120}
              onChange={(e) =>
                patch({ pf_feed_ratio_pct: Number(e.target.value) })
              }
            />
          </Field>
          <Field label="PF Recovery (%)">
            <Input
              className={INPUT_CLS}
              value={cfg.pf_recovery_pct ?? 20}
              onChange={(e) =>
                patch({ pf_recovery_pct: Number(e.target.value) })
              }
            />
          </Field>
        </div>
        <div className="mt-2 text-[9px] text-slate-500 leading-tight">
          * Configure the initial single-pass stage before the closed loop
          (Hybrid CCRO).
        </div>
      </div>

      <div className={GROUP_CLS}>
        <h4 className={HEADER_CLS}>Closed Circuit Settings</h4>
        <div className="grid grid-cols-2 gap-2">
          <Field label="Set Press. (bar)">
            <Input
              className={INPUT_CLS}
              value={cfg.p_set_bar}
              onChange={(e) => patch({ p_set_bar: Number(e.target.value) })}
            />
          </Field>
          <Field label="Recirc (m3/h)">
            <Input
              className={INPUT_CLS}
              value={cfg.recirc_flow_m3h}
              onChange={(e) =>
                patch({ recirc_flow_m3h: Number(e.target.value) })
              }
            />
          </Field>
          <Field label="Loop Vol (m3)">
            <Input
              className={INPUT_CLS}
              value={cfg.loop_volume_m3}
              onChange={(e) =>
                patch({ loop_volume_m3: Number(e.target.value) })
              }
            />
          </Field>
          <Field label="Bleed (m3/h)">
            <Input
              className={INPUT_CLS}
              value={cfg.bleed_m3h}
              onChange={(e) => patch({ bleed_m3h: Number(e.target.value) })}
            />
          </Field>
        </div>
      </div>

      <div className={GROUP_CLS}>
        <h4 className={HEADER_CLS}>Batch Control</h4>
        <div className="grid grid-cols-2 gap-2">
          <Field label="Max Time (min)">
            <Input
              className={INPUT_CLS}
              value={cfg.max_minutes}
              onChange={(e) => patch({ max_minutes: Number(e.target.value) })}
            />
          </Field>
          <Field label="Stop Recov (%)">
            <Input
              className={INPUT_CLS}
              value={cfg.stop_recovery_pct ?? ''}
              onChange={(e) =>
                patch({ stop_recovery_pct: Number(e.target.value) })
              }
            />
          </Field>
        </div>
      </div>

      <div className={GROUP_CLS}>
        <h4 className={HEADER_CLS}>Stage Layout</h4>
        <div className="grid grid-cols-2 gap-2">
          <Field label="PV / Stage">
            <Input
              className={INPUT_CLS}
              value={cfg.hrro_stage_pv_per_stage}
              onChange={(e) =>
                patch({
                  hrro_stage_pv_per_stage: Number(e.target.value),
                  elements:
                    Number(e.target.value) * (cfg.hrro_stage_els_per_pv || 6),
                })
              }
            />
          </Field>
          <Field label="Elements / PV">
            <Input
              className={INPUT_CLS}
              value={cfg.hrro_stage_els_per_pv}
              onChange={(e) =>
                patch({
                  hrro_stage_els_per_pv: Number(e.target.value),
                  elements:
                    (cfg.hrro_stage_pv_per_stage || 1) * Number(e.target.value),
                })
              }
            />
          </Field>
          <Field label="Total Elements">
            <Input
              className={`${INPUT_CLS} bg-slate-800/50 text-slate-400`}
              value={cfg.elements}
              readOnly
            />
          </Field>

          {/* [신규] Flow Factor & Delta P 추가 */}
          <Field label="Flow Factor">
            <Input
              className={INPUT_CLS}
              value={cfg.hrro_flow_factor ?? 0.85}
              onChange={(e) =>
                patch({ hrro_flow_factor: Number(e.target.value) })
              }
            />
          </Field>
          <Field label="Pre-stage ΔP">
            <Input
              className={INPUT_CLS}
              value={cfg.hrro_stage_pre_delta_p_bar ?? 0.31}
              onChange={(e) =>
                patch({ hrro_stage_pre_delta_p_bar: Number(e.target.value) })
              }
            />
          </Field>

          <Field label="Boost Press">
            <Input
              className={INPUT_CLS}
              value={cfg.hrro_stage_boost_press_bar ?? 0}
              onChange={(e) =>
                patch({ hrro_stage_boost_press_bar: Number(e.target.value) })
              }
            />
          </Field>
          <Field label="Back Press">
            <Input
              className={INPUT_CLS}
              value={cfg.hrro_stage_back_pressure_bar ?? 0}
              onChange={(e) =>
                patch({ hrro_stage_back_pressure_bar: Number(e.target.value) })
              }
            />
          </Field>
        </div>
      </div>
    </div>
  );
}

// ==============================
// 4. NF Editor
// ==============================
export function NFEditor({
  node,
  onChange,
}: {
  node: UnitData | undefined;
  onChange: (cfg: NFConfig) => void;
}) {
  const data = node;
  if (!data || data.kind !== 'NF')
    return <div className="text-red-400 text-xs">Invalid Data</div>;
  const raw = (data.cfg as NFConfig | undefined) ?? {};
  const cfg = { ...raw } as NFConfig;
  const patch = (p: Partial<NFConfig>) => onChange({ ...cfg, ...p });

  return (
    <div
      className="space-y-2 text-slate-100 text-xs"
      onKeyDown={(e) => e.stopPropagation()}
    >
      <PumpSection cfg={cfg} onChange={patch} defaultPressure={10.0} />

      {/* ✅ MembraneSelect 컴포넌트 */}
      <div className="mb-2">
        <MembraneSelect
          unitType="NF"
          mode={cfg.membrane_mode}
          model={cfg.membrane_model}
          area={cfg.custom_area_m2 ?? cfg.membrane_area_m2}
          A={cfg.custom_A_lmh_bar ?? cfg.membrane_A_lmh_bar}
          B={cfg.custom_B_lmh ?? cfg.membrane_B_lmh}
          rej={cfg.custom_salt_rejection_pct ?? cfg.membrane_salt_rejection_pct}
          onChange={patch}
        />
      </div>

      <div className={GROUP_CLS}>
        <h4 className={HEADER_CLS}>Control</h4>
        <div className="grid grid-cols-2 gap-2">
          <Field label="Recovery (%)">
            <Input
              className={INPUT_CLS}
              value={cfg.recovery_target_pct ?? 75}
              onChange={(e) =>
                patch({ recovery_target_pct: Number(e.target.value) })
              }
            />
          </Field>
          <Field label="Elements">
            <Input
              className={INPUT_CLS}
              value={cfg.elements}
              onChange={(e) => patch({ elements: Number(e.target.value) })}
            />
          </Field>
        </div>
      </div>
    </div>
  );
}

// ==============================
// 5. MF Editor
// ==============================
export function MFEditor({
  node,
  onChange,
}: {
  node: UnitData | undefined;
  onChange: (cfg: MFConfig) => void;
}) {
  const data = node;
  if (!data || data.kind !== 'MF')
    return <div className="text-red-400 text-xs">Invalid Data</div>;
  const raw = (data.cfg as MFConfig | undefined) ?? {};
  const cfg = { ...raw } as MFConfig;
  const patch = (p: Partial<MFConfig>) => onChange({ ...cfg, ...p });

  return (
    <div
      className="space-y-2 text-slate-100 text-xs"
      onKeyDown={(e) => e.stopPropagation()}
    >
      <PumpSection cfg={cfg} onChange={patch} defaultPressure={1.0} />

      {/* ✅ MembraneSelect 컴포넌트 */}
      <div className="mb-2">
        <MembraneSelect
          unitType="MF"
          mode={cfg.membrane_mode}
          model={cfg.membrane_model}
          area={cfg.custom_area_m2 ?? cfg.membrane_area_m2}
          A={cfg.custom_A_lmh_bar ?? cfg.membrane_A_lmh_bar}
          // MF는 B, Rej 없음
          onChange={patch}
        />
      </div>

      <div className={GROUP_CLS}>
        <h4 className={HEADER_CLS}>Settings</h4>
        <div className="grid grid-cols-2 gap-2">
          <Field label="Elements">
            <Input
              className={INPUT_CLS}
              value={cfg.elements}
              onChange={(e) => patch({ elements: Number(e.target.value) })}
            />
          </Field>
          <Field label="Flux (lmh)">
            <Input
              className={INPUT_CLS}
              value={cfg.mf_filtrate_flux_lmh_25C ?? 100}
              onChange={(e) =>
                patch({ mf_filtrate_flux_lmh_25C: Number(e.target.value) })
              }
            />
          </Field>
        </div>
      </div>
    </div>
  );
}

// ==============================
// 6. Pump Editor
// ==============================
export function PumpEditor({ node }: any) {
  return (
    <div className="p-4 text-center text-xs text-slate-500 bg-slate-900/50 rounded border border-slate-800 border-dashed">
      Standalone Pump Node
      <br />
      (Use integrated settings in UF/RO units)
    </div>
  );
}
