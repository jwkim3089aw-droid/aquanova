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
  'p-2.5 border border-slate-800 rounded bg-slate-950/30 mb-2.5';
const HEADER_CLS =
  'text-[11px] font-bold text-slate-400 mb-2 uppercase tracking-wide border-b border-slate-800/50 pb-1';
const INPUT_CLS =
  'h-7 text-sm bg-slate-900 border-slate-700 focus:border-blue-500 focus:bg-slate-800 transition-colors w-full rounded px-2 outline-none text-slate-200';

/**
 * ✅ MembraneSelect의 일반적인 출력({ area, A... })을
 * 실제 Config의 커스텀 필드({ custom_area_m2, ... })로 매핑하는 헬퍼
 */
const mapMembraneChange = (updates: any) => {
  const patch: any = {};

  if (updates.mode !== undefined) patch.membrane_mode = updates.mode;
  if (updates.model !== undefined) patch.membrane_model = updates.model;

  // 커스텀 입력값 매핑
  if (updates.area !== undefined) patch.custom_area_m2 = updates.area;
  if (updates.A !== undefined) patch.custom_A_lmh_bar = updates.A;
  if (updates.B !== undefined) patch.custom_B_lmh = updates.B;
  if (updates.rej !== undefined) patch.custom_salt_rejection_pct = updates.rej;

  return patch;
};

// ==============================
// 2. 공통 펌프 설정 섹션
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
// 3. HRRO Editor (Dashboard Style)
// ==============================
export function HRROEditor({
  node,
  onChange,
}: {
  node: UnitData | undefined;
  onChange: (cfg: HRROConfig) => void;
}) {
  if (!node || node.kind !== 'HRRO')
    return <div className="text-red-400 p-4">Invalid Data</div>;

  const raw = (node.cfg as HRROConfig | undefined) ?? {};
  const cfg: HRROConfig = {
    elements: 6,
    p_set_bar: 28,
    recirc_flow_m3h: 12,
    bleed_m3h: 0,
    loop_volume_m3: 2,
    makeup_tds_mgL: 35000,
    timestep_s: 5,
    max_minutes: 30,
    stop_recovery_pct: 90,
    pf_feed_ratio_pct: 120,
    pf_recovery_pct: 20,
    hrro_flow_factor: 0.85,
    hrro_stage_pre_delta_p_bar: 0.31,
    ...raw,
  };

  const patch = (p: Partial<HRROConfig>) => onChange({ ...cfg, ...p });

  // 면적 계산 시 사용자 정의(custom) 값을 우선 참조
  const currentArea = cfg.custom_area_m2 ?? cfg.membrane_area_m2 ?? 40.9;
  const totalArea = currentArea * (cfg.elements || 6);

  return (
    <div
      className="flex flex-col h-full space-y-2 text-slate-100 text-[11px] p-1 overflow-hidden"
      onKeyDown={(e) => e.stopPropagation()}
    >
      {/* 📊 상단 대시보드 */}
      <div className="grid grid-cols-4 gap-2 p-1.5 bg-blue-600/10 border border-blue-500/30 rounded shadow-inner">
        <div className="flex flex-col items-center border-r border-blue-500/20">
          <span className="text-[9px] text-blue-400 font-bold uppercase">
            총 여과 면적
          </span>
          <span className="font-mono text-sm">
            {totalArea.toFixed(1)} <small className="text-[10px]">m²</small>
          </span>
        </div>
        <div className="flex flex-col items-center border-r border-blue-500/20">
          <span className="text-[9px] text-emerald-400 font-bold uppercase">
            목표 회수율
          </span>
          <span className="font-mono text-sm text-emerald-400">
            {cfg.stop_recovery_pct}%
          </span>
        </div>
        <div className="flex flex-col items-center border-r border-blue-500/20">
          <span className="text-[9px] text-amber-400 font-bold uppercase">
            운전 설정 압력
          </span>
          <span className="font-mono text-sm">
            {cfg.p_set_bar} <small className="text-[10px]">bar</small>
          </span>
        </div>
        <div className="flex flex-col items-center">
          <span className="text-[9px] text-slate-400 font-bold uppercase">
            하이브리드 모드
          </span>
          <span
            className={`font-mono text-sm ${cfg.pf_recovery_pct > 0 ? 'text-blue-400' : 'text-slate-600'}`}
          >
            {cfg.pf_recovery_pct > 0 ? '활성' : '비활성'}
          </span>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-2 flex-1 overflow-hidden">
        {/* 1열: 하드웨어 & 멤브레인 */}
        <div className="space-y-2 overflow-y-auto pr-1 scrollbar-thin">
          <PumpSection cfg={cfg} onChange={patch} defaultPressure={20.0} />
          <MembraneSelect
            unitType="HRRO"
            mode={cfg.membrane_mode}
            model={cfg.membrane_model}
            area={cfg.custom_area_m2 ?? cfg.membrane_area_m2}
            A={cfg.custom_A_lmh_bar ?? cfg.membrane_A_lmh_bar}
            B={cfg.custom_B_lmh ?? cfg.membrane_B_lmh}
            rej={
              cfg.custom_salt_rejection_pct ?? cfg.membrane_salt_rejection_pct
            }
            onChange={(updates) => patch(mapMembraneChange(updates))}
          />
        </div>

        {/* 2열: 공정 제어 */}
        <div className="space-y-2 overflow-y-auto pr-1 scrollbar-thin">
          <div className="p-2 border border-blue-900/40 bg-blue-950/10 rounded">
            <h4 className="text-blue-400 font-bold mb-2 uppercase text-[10px]">
              🌊 플러그 플로우
            </h4>
            <div className="grid grid-cols-1 gap-2">
              <Field label="공급 유량비 (%)">
                <Input
                  className={INPUT_CLS}
                  value={cfg.pf_feed_ratio_pct}
                  onChange={(e) =>
                    patch({ pf_feed_ratio_pct: Number(e.target.value) })
                  }
                />
              </Field>
              <Field label="전단 회수율 (%)">
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
          <div className="p-2 border border-slate-800 bg-slate-900/20 rounded">
            <h4 className="text-slate-400 font-bold mb-2 uppercase text-[10px]">
              ⏱️ 배치 운전 제어
            </h4>
            <Field label="종료 회수율 (%)">
              <Input
                className={`${INPUT_CLS} text-emerald-400`}
                value={cfg.stop_recovery_pct}
                onChange={(e) =>
                  patch({ stop_recovery_pct: Number(e.target.value) })
                }
              />
            </Field>
            <Field label="최대 운전 시간 (min)">
              <Input
                className={INPUT_CLS}
                value={cfg.max_minutes}
                onChange={(e) => patch({ max_minutes: Number(e.target.value) })}
              />
            </Field>
          </div>
        </div>

        {/* 3열: 수리 설계 */}
        <div className="space-y-2 overflow-y-auto pr-1 scrollbar-thin">
          <div className="p-2 border border-slate-800 bg-slate-900/20 rounded">
            <h4 className="text-slate-400 font-bold mb-2 uppercase text-[10px]">
              ⚙️ 수리 설계
            </h4>
            <div className="grid grid-cols-2 gap-2">
              <Field label="압력(bar)">
                <Input
                  className={INPUT_CLS}
                  value={cfg.p_set_bar}
                  onChange={(e) => patch({ p_set_bar: Number(e.target.value) })}
                />
              </Field>
              <Field label="순환(m³/h)">
                <Input
                  className={INPUT_CLS}
                  value={cfg.recirc_flow_m3h}
                  onChange={(e) =>
                    patch({ recirc_flow_m3h: Number(e.target.value) })
                  }
                />
              </Field>
              <Field label="루프(m³)">
                <Input
                  className={INPUT_CLS}
                  value={cfg.loop_volume_m3}
                  onChange={(e) =>
                    patch({ loop_volume_m3: Number(e.target.value) })
                  }
                />
              </Field>
              <Field label="배출(m³/h)">
                <Input
                  className={INPUT_CLS}
                  value={cfg.bleed_m3h}
                  onChange={(e) => patch({ bleed_m3h: Number(e.target.value) })}
                />
              </Field>
            </div>
            <div className="mt-3 pt-2 border-t border-slate-800 grid grid-cols-2 gap-2">
              <Field label="PV/Stage">
                <Input
                  className={INPUT_CLS}
                  value={cfg.hrro_stage_pv_per_stage}
                  onChange={(e) =>
                    patch({
                      hrro_stage_pv_per_stage: Number(e.target.value),
                      elements:
                        Number(e.target.value) *
                        (cfg.hrro_stage_els_per_pv || 6),
                    })
                  }
                />
              </Field>
              <Field label="Els/PV">
                <Input
                  className={INPUT_CLS}
                  value={cfg.hrro_stage_els_per_pv}
                  onChange={(e) =>
                    patch({
                      hrro_stage_els_per_pv: Number(e.target.value),
                      elements:
                        (cfg.hrro_stage_pv_per_stage || 1) *
                        Number(e.target.value),
                    })
                  }
                />
              </Field>
            </div>
            <div className="mt-2 p-1.5 bg-slate-950 rounded border border-slate-800 flex justify-between items-center">
              <span className="text-[9px] text-slate-500 font-bold uppercase">
                Total Elements
              </span>
              <span className="text-blue-400 font-mono font-bold">
                {cfg.elements} EA
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ==============================
// 4. RO Editor
// ==============================
export function ROEditor({
  node,
  onChange,
}: {
  node: UnitData | undefined;
  onChange: (cfg: ROConfig) => void;
}) {
  if (!node || node.kind !== 'RO')
    return <div className="text-red-400 text-xs">Invalid Data</div>;
  const cfg = {
    elements: 6,
    mode: 'pressure' as const,
    pressure_bar: 16,
    recovery_target_pct: 75,
    ro_n_stages: 1,
    ro_flow_factor: 0.85,
    ...node.cfg,
  } as ROConfig;
  const patch = (p: Partial<ROConfig>) => onChange({ ...cfg, ...p });

  return (
    <div
      className="space-y-2 text-slate-100 text-xs"
      onKeyDown={(e) => e.stopPropagation()}
    >
      <PumpSection cfg={cfg} onChange={patch} defaultPressure={15.0} />
      <MembraneSelect
        unitType="RO"
        mode={cfg.membrane_mode}
        model={cfg.membrane_model}
        area={cfg.custom_area_m2 ?? cfg.membrane_area_m2}
        A={cfg.custom_A_lmh_bar ?? cfg.membrane_A_lmh_bar}
        B={cfg.custom_B_lmh ?? cfg.membrane_B_lmh}
        rej={cfg.custom_salt_rejection_pct ?? cfg.membrane_salt_rejection_pct}
        onChange={(updates) => patch(mapMembraneChange(updates))}
      />
      <div className={GROUP_CLS}>
        <h4 className={HEADER_CLS}>Control Strategy</h4>
        <div className="grid grid-cols-2 gap-2">
          <Field label="Control Mode">
            <select
              className={INPUT_CLS}
              value={cfg.mode}
              onChange={(e) => patch({ mode: e.target.value as any })}
            >
              <option value="pressure">Fix Pressure</option>
              <option value="recovery">Fix Recovery</option>
            </select>
          </Field>
          {cfg.mode === 'pressure' ? (
            <Field label="Feed Press (bar)">
              <Input
                className={INPUT_CLS}
                value={cfg.pressure_bar}
                onChange={(e) =>
                  patch({ pressure_bar: Number(e.target.value) })
                }
              />
            </Field>
          ) : (
            <Field label="Recovery (%)">
              <Input
                className={INPUT_CLS}
                value={cfg.recovery_target_pct}
                onChange={(e) =>
                  patch({ recovery_target_pct: Number(e.target.value) })
                }
              />
            </Field>
          )}
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
    return <div className="text-red-400 text-xs">Invalid Data</div>;
  const cfg = {
    elements: 6,
    filtration_duration_min: 30,
    uf_backwash_duration_s: 60,
    ...node.cfg,
  } as UFConfig;
  const patch = (p: Partial<UFConfig>) => onChange({ ...cfg, ...p });

  return (
    <div
      className="space-y-2 text-slate-100 text-xs"
      onKeyDown={(e) => e.stopPropagation()}
    >
      <PumpSection cfg={cfg} onChange={patch} defaultPressure={3.0} />
      <MembraneSelect
        unitType="UF"
        mode={cfg.membrane_mode}
        model={cfg.membrane_model}
        area={cfg.custom_area_m2 ?? cfg.membrane_area_m2}
        A={cfg.custom_A_lmh_bar ?? cfg.membrane_A_lmh_bar}
        onChange={(updates) => patch(mapMembraneChange(updates))}
      />
      <div className={GROUP_CLS}>
        <h4 className={HEADER_CLS}>Operation</h4>
        <div className="grid grid-cols-2 gap-2">
          <Field label="# Modules">
            <Input
              className={INPUT_CLS}
              value={cfg.elements}
              onChange={(e) => patch({ elements: Number(e.target.value) })}
            />
          </Field>
          <Field label="Filtration (min)">
            <Input
              className={INPUT_CLS}
              value={cfg.filtration_duration_min}
              onChange={(e) =>
                patch({ filtration_duration_min: Number(e.target.value) })
              }
            />
          </Field>
        </div>
      </div>
    </div>
  );
}

// ==============================
// 6. NF/MF/Pump (Placeholders)
// ==============================
export function NFEditor({ node, onChange }: any) {
  const cfg = node.cfg || {};
  return (
    <div className="space-y-2">
      <MembraneSelect
        unitType="NF"
        mode={cfg.membrane_mode}
        area={cfg.custom_area_m2 ?? cfg.membrane_area_m2}
        A={cfg.custom_A_lmh_bar ?? cfg.membrane_A_lmh_bar}
        B={cfg.custom_B_lmh ?? cfg.membrane_B_lmh}
        rej={cfg.custom_salt_rejection_pct ?? cfg.membrane_salt_rejection_pct}
        onChange={(u) => onChange({ ...cfg, ...mapMembraneChange(u) })}
      />
    </div>
  );
}

export function MFEditor({ node, onChange }: any) {
  const cfg = node.cfg || {};
  return (
    <div className="space-y-2">
      <MembraneSelect
        unitType="MF"
        mode={cfg.membrane_mode}
        area={cfg.custom_area_m2 ?? cfg.membrane_area_m2}
        A={cfg.custom_A_lmh_bar ?? cfg.membrane_A_lmh_bar}
        onChange={(u) => onChange({ ...cfg, ...mapMembraneChange(u) })}
      />
    </div>
  );
}

export function PumpEditor({ node }: any) {
  return (
    <div className="p-4 text-center text-xs text-slate-500 bg-slate-900/50 rounded border border-slate-800 border-dashed">
      Standalone Pump Node Settings
    </div>
  );
}
