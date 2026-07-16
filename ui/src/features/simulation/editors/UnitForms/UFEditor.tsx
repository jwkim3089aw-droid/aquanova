// ui/src/features/simulation/editors/UnitForms/UFEditor.tsx
import React from 'react';
import { Field, Input } from '../../components/Common';
import MembraneSelect from '../../components/MembraneSelect';
import { UnitData, UFConfig } from '../../model/types';
import { GROUP_CLS, HEADER_CLS, INPUT_CLS, mapMembraneChange } from './utils';
import { PumpSection } from './PumpSection';

export function UFEditor({
  node,
  feed,
  onChange,
}: {
  node: UnitData | undefined;
  feed?: any;
  onChange: (cfg: UFConfig) => void;
}) {
  if (!node || node.kind !== 'UF')
    return (
      <div className="text-red-400 text-xs p-4">
        유효하지 않은 데이터입니다. (Invalid Data)
      </div>
    );

  const cfg = {
    elements: 62,
    design_flux_lmh: 41.0,
    recovery_target_pct: 96.5,
    strainer_recovery_pct: 99.5,
    strainer_size_micron: 150.0,
    uf_maintenance: {
      filtration_duration_min: 60,
      backwash_duration_sec: 60,
      drain_duration_sec: 30,
      top_backwash_duration_sec: 30,
      bottom_backwash_duration_sec: 30,
      air_scour_duration_sec: 20,
      forward_flush_duration_sec: 40,
      acid_ceb_interval_h: 24,
      alkali_ceb_interval_h: 24,
      cip_interval_d: 30,
      mini_cip_interval_d: 0,
      backwash_flux_lmh: 100.0,
      ceb_flux_lmh: 80.0,
      forward_flush_flow_m3h_per_mod: 2.83,
      air_flow_nm3h_per_mod: 12.0,
      ceb_soaking_min: 10,
      cip_heating_min: 60,
      power_plc_kw: 0.1,
      power_valve_kw: 0.0,
      valves_per_train: 6,
      valve_action_sec: 5.0,
      air_scour_pressure_bar: 0.75,
      filtrate_pressure_bar: 0.5,
      filtration_piping_dp_bar: 0.4,
      strainer_dp_bar: 0.1,
      backwash_piping_dp_bar: 0.5,
      cip_piping_dp_bar: 2.5,
    },
    ...node.cfg,
  } as UFConfig & { uf_maintenance: any };

  const patch = (p: Partial<UFConfig>) => onChange({ ...cfg, ...p });

  const patchMaintenance = (p: any) => {
    patch({
      uf_maintenance: {
        ...(cfg.uf_maintenance || {}),
        ...p,
      },
    } as any);
  };

  const feedFlow = (node as any)?.computed_feed_flow ?? feed?.flow_m3h ?? 0;
  const currentArea = cfg.custom_area_m2 ?? cfg.membrane_area_m2 ?? 77.0;
  const totalArea = currentArea * (cfg.elements || 62);
  const grossPermeate =
    totalArea > 0 ? (cfg.design_flux_lmh * totalArea) / 1000 : 0;

  return (
    <div
      className="flex flex-col h-full text-slate-100 p-1 overflow-hidden"
      onKeyDown={(e) => e.stopPropagation()}
    >
      <div className="grid grid-cols-4 gap-2 p-2 bg-slate-900 border border-slate-700 rounded-lg shadow-inner shrink-0 mb-2">
        <div className="flex flex-col items-center border-r border-slate-700">
          <span className="text-[10px] text-slate-400 font-bold mb-0.5 uppercase tracking-wide">
            유입수 (Feed Flow)
          </span>
          <span className="font-mono text-base font-bold text-slate-100">
            {feedFlow > 0 ? feedFlow.toFixed(1) : '-'}{' '}
            <small className="text-[9px] font-normal text-slate-500">
              m³/h
            </small>
          </span>
        </div>
        <div className="flex flex-col items-center border-r border-slate-700">
          <span className="text-[10px] text-emerald-400 font-bold mb-0.5 uppercase tracking-wide">
            총 모듈 수 (Modules)
          </span>
          <span className="font-mono text-base font-bold text-emerald-400">
            {cfg.elements}{' '}
            <small className="text-[9px] font-normal text-emerald-600/70">
              EA
            </small>
          </span>
        </div>
        <div className="flex flex-col items-center border-r border-slate-700">
          <span className="text-[10px] text-amber-400 font-bold mb-0.5 uppercase tracking-wide">
            목표 플럭스 (Target Flux)
          </span>
          <span className="font-mono text-base font-bold text-amber-300">
            {cfg.design_flux_lmh.toFixed(1)}{' '}
            <small className="text-[9px] font-normal text-amber-600/70">
              LMH
            </small>
          </span>
        </div>
        <div className="flex flex-col items-center">
          <span className="text-[10px] text-blue-400 font-bold mb-0.5 uppercase tracking-wide">
            예상 총 생산량 (Gross)
          </span>
          <span className="font-mono text-base font-bold text-blue-300">
            {grossPermeate.toFixed(1)}{' '}
            <small className="text-[9px] font-normal text-blue-500/70">
              m³/h
            </small>
          </span>
        </div>
      </div>

      <div className="flex-1 grid grid-cols-12 gap-3 overflow-hidden">
        <div className="col-span-7 flex flex-col gap-2 h-full min-h-0 overflow-y-auto custom-scrollbar pr-1 pb-4">
          <PumpSection cfg={cfg} onChange={patch} defaultPressure={3.2} />

          <div className="shrink-0">
            <div className="px-3 py-2 bg-slate-800/90 border border-slate-700 rounded-t-md text-[11px] font-bold text-slate-200 tracking-wide">
              멤브레인 모델 (Membrane Type: {node.kind})
            </div>
            <div className="p-3 border-x border-b border-slate-700 bg-slate-900/60 rounded-b-md">
              <MembraneSelect
                unitType="UF"
                mode={cfg.membrane_mode}
                model={cfg.membrane_model}
                area={cfg.custom_area_m2 ?? cfg.membrane_area_m2 ?? 77.0}
                A={cfg.custom_A_lmh_bar ?? cfg.membrane_A_lmh_bar}
                onChange={(updates) => patch(mapMembraneChange(updates))}
              />
            </div>
          </div>

          <div className={`${GROUP_CLS} flex-1 !mb-0`}>
            <h4 className={HEADER_CLS}>
              ⚙️ 모듈 및 회수율 (Module & Recovery)
            </h4>
            <div className="grid grid-cols-3 gap-3">
              <Field label="총 모듈 수 (Modules)">
                <Input
                  className={INPUT_CLS}
                  type="number"
                  value={cfg.elements}
                  onChange={(e) => patch({ elements: Number(e.target.value) })}
                />
              </Field>
              <Field label="운전 플럭스 (LMH)">
                <Input
                  className={`${INPUT_CLS} text-amber-300 font-bold bg-amber-950/40`}
                  type="number"
                  step={0.1}
                  value={cfg.design_flux_lmh}
                  onChange={(e) =>
                    patch({ design_flux_lmh: Number(e.target.value) })
                  }
                />
              </Field>
              <Field label="시스템 회수율 (%)">
                <Input
                  className={`${INPUT_CLS} text-green-300 font-bold bg-green-950/40`}
                  type="number"
                  step={0.1}
                  value={cfg.recovery_target_pct}
                  onChange={(e) =>
                    patch({ recovery_target_pct: Number(e.target.value) })
                  }
                />
              </Field>
            </div>
          </div>

          <div
            className={`${GROUP_CLS} shrink-0 !mb-0 border-amber-900/40 bg-amber-900/10 mt-2`}
          >
            <h4 className={`${HEADER_CLS} border-amber-900/30 text-amber-500`}>
              🛡️ 전처리 스트레이너 (Strainer)
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
              <Field label="포어 사이즈 (μm)">
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

          <div
            className={`${GROUP_CLS} shrink-0 border-slate-700 bg-slate-800/20 mt-2`}
          >
            <h4 className={HEADER_CLS}>📐 압력 강하 설계 (Pressure Drops)</h4>
            <div className="grid grid-cols-3 gap-2">
              <Field label="여과 배관 손실 (bar)">
                <Input
                  className={INPUT_CLS}
                  type="number"
                  step={0.01}
                  value={cfg.uf_maintenance?.filtration_piping_dp_bar}
                  onChange={(e) =>
                    patchMaintenance({
                      filtration_piping_dp_bar: Number(e.target.value),
                    })
                  }
                />
              </Field>
              <Field label="스트레이너 차압 (bar)">
                <Input
                  className={INPUT_CLS}
                  type="number"
                  step={0.01}
                  value={cfg.uf_maintenance?.strainer_dp_bar}
                  onChange={(e) =>
                    patchMaintenance({
                      strainer_dp_bar: Number(e.target.value),
                    })
                  }
                />
              </Field>
              <Field label="역세 배관 손실 (bar)">
                <Input
                  className={INPUT_CLS}
                  type="number"
                  step={0.01}
                  value={cfg.uf_maintenance?.backwash_piping_dp_bar}
                  onChange={(e) =>
                    patchMaintenance({
                      backwash_piping_dp_bar: Number(e.target.value),
                    })
                  }
                />
              </Field>
            </div>
          </div>
        </div>

        <div className="col-span-5 flex flex-col gap-2 h-full min-h-0 overflow-y-auto custom-scrollbar pr-1 pb-4">
          <div
            className={`${GROUP_CLS} shrink-0 border-blue-900/30 bg-blue-900/5`}
          >
            <h4 className={`${HEADER_CLS} text-blue-400 border-blue-900/30`}>
              💦 세정 시퀀스 (Backwash & Flush)
            </h4>
            <div className="flex flex-col gap-2">
              <Field label="여과 공정 시간 (min)">
                <Input
                  className={`${INPUT_CLS} text-emerald-400 font-bold`}
                  type="number"
                  value={cfg.uf_maintenance?.filtration_duration_min}
                  onChange={(e) =>
                    patchMaintenance({
                      filtration_duration_min: Number(e.target.value),
                    })
                  }
                />
              </Field>
              <Field label="공기 세정 시간 (s)">
                <Input
                  className={INPUT_CLS}
                  type="number"
                  value={cfg.uf_maintenance?.air_scour_duration_sec}
                  onChange={(e) =>
                    patchMaintenance({
                      air_scour_duration_sec: Number(e.target.value),
                    })
                  }
                />
              </Field>
              <Field label="포워드 플러시 시간 (s)">
                <Input
                  className={INPUT_CLS}
                  type="number"
                  value={cfg.uf_maintenance?.forward_flush_duration_sec}
                  onChange={(e) =>
                    patchMaintenance({
                      forward_flush_duration_sec: Number(e.target.value),
                    })
                  }
                />
              </Field>
              <div className="grid grid-cols-2 gap-2">
                <Field label="상부 역세 시간 (s)">
                  <Input
                    className={INPUT_CLS}
                    type="number"
                    value={cfg.uf_maintenance?.top_backwash_duration_sec}
                    onChange={(e) =>
                      patchMaintenance({
                        top_backwash_duration_sec: Number(e.target.value),
                      })
                    }
                  />
                </Field>
                <Field label="하부 역세 시간 (s)">
                  <Input
                    className={INPUT_CLS}
                    type="number"
                    value={cfg.uf_maintenance?.bottom_backwash_duration_sec}
                    onChange={(e) =>
                      patchMaintenance({
                        bottom_backwash_duration_sec: Number(e.target.value),
                      })
                    }
                  />
                </Field>
              </div>
            </div>
          </div>

          <div
            className={`${GROUP_CLS} shrink-0 border-purple-900/30 bg-purple-900/5`}
          >
            <h4
              className={`${HEADER_CLS} text-purple-400 border-purple-900/30`}
            >
              🧪 화학 세정 (CEB & CIP)
            </h4>
            <div className="grid grid-cols-2 gap-2">
              <Field label="산성 CEB 주기 (h)">
                <Input
                  className={INPUT_CLS}
                  type="number"
                  value={cfg.uf_maintenance?.acid_ceb_interval_h}
                  onChange={(e) =>
                    patchMaintenance({
                      acid_ceb_interval_h: Number(e.target.value),
                    })
                  }
                />
              </Field>
              <Field label="알칼리 CEB 주기 (h)">
                <Input
                  className={INPUT_CLS}
                  type="number"
                  value={cfg.uf_maintenance?.alkali_ceb_interval_h}
                  onChange={(e) =>
                    patchMaintenance({
                      alkali_ceb_interval_h: Number(e.target.value),
                    })
                  }
                />
              </Field>
              {/* 🚀 추가된 폼: CEB 플럭스 */}
              <Field label="CEB 플럭스 (LMH)">
                <Input
                  className={INPUT_CLS}
                  type="number"
                  step={0.1}
                  value={cfg.uf_maintenance?.ceb_flux_lmh}
                  onChange={(e) =>
                    patchMaintenance({
                      ceb_flux_lmh: Number(e.target.value),
                    })
                  }
                />
              </Field>
              {/* 🚀 추가된 폼: 역세 플럭스 */}
              <Field label="역세 플럭스 (LMH)">
                <Input
                  className={INPUT_CLS}
                  type="number"
                  step={0.1}
                  value={cfg.uf_maintenance?.backwash_flux_lmh}
                  onChange={(e) =>
                    patchMaintenance({
                      backwash_flux_lmh: Number(e.target.value),
                    })
                  }
                />
              </Field>
              <Field label="CEB 약품 침전 (min)">
                <Input
                  className={INPUT_CLS}
                  type="number"
                  value={cfg.uf_maintenance?.ceb_soaking_min}
                  onChange={(e) =>
                    patchMaintenance({
                      ceb_soaking_min: Number(e.target.value),
                    })
                  }
                />
              </Field>
              <Field label="정밀세정(CIP) 주기 (d)">
                <Input
                  className={INPUT_CLS}
                  type="number"
                  value={cfg.uf_maintenance?.cip_interval_d}
                  onChange={(e) =>
                    patchMaintenance({ cip_interval_d: Number(e.target.value) })
                  }
                />
              </Field>
            </div>
          </div>

          <div
            className={`${GROUP_CLS} shrink-0 border-rose-900/30 bg-rose-900/5`}
          >
            <h4 className={`${HEADER_CLS} text-rose-400 border-rose-900/30`}>
              ⚡ 전력 및 장비 제원 (Power)
            </h4>
            <div className="grid grid-cols-2 gap-2">
              <Field label="PLC 전력 (kW/Train)">
                <Input
                  className={INPUT_CLS}
                  type="number"
                  step={0.01}
                  value={cfg.uf_maintenance?.power_plc_kw}
                  onChange={(e) =>
                    patchMaintenance({ power_plc_kw: Number(e.target.value) })
                  }
                />
              </Field>
              <Field label="밸브 구동 전력 (kW)">
                <Input
                  className={INPUT_CLS}
                  type="number"
                  step={0.01}
                  value={cfg.uf_maintenance?.power_valve_kw}
                  onChange={(e) =>
                    patchMaintenance({ power_valve_kw: Number(e.target.value) })
                  }
                />
              </Field>
              <Field label="트레인당 밸브 수 (EA)">
                <Input
                  className={INPUT_CLS}
                  type="number"
                  value={cfg.uf_maintenance?.valves_per_train}
                  onChange={(e) =>
                    patchMaintenance({
                      valves_per_train: Number(e.target.value),
                    })
                  }
                />
              </Field>
              <Field label="밸브 개폐 시간 (s)">
                <Input
                  className={INPUT_CLS}
                  type="number"
                  step={0.1}
                  value={cfg.uf_maintenance?.valve_action_sec}
                  onChange={(e) =>
                    patchMaintenance({
                      valve_action_sec: Number(e.target.value),
                    })
                  }
                />
              </Field>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
