// ui/src/features/simulation/editors/UnitForms/UFEditor.tsx

import React from 'react';
import { Field, Input } from '../../components/Common';
import MembraneSelect from '../../components/MembraneSelect';
import { UnitData, UFConfig } from '../../model/types';
import { GROUP_CLS, HEADER_CLS, INPUT_CLS, mapMembraneChange } from './utils';
import { PumpSection } from './PumpSection';

export function UFEditor({
  node,
  onChange,
}: {
  node: UnitData | undefined;
  onChange: (cfg: UFConfig) => void;
}) {
  if (!node || node.kind !== 'UF')
    return <div className="text-red-400 text-xs p-4">Invalid Data</div>;

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

  return (
    <div
      className="flex flex-col h-full text-slate-100 p-1 overflow-hidden"
      onKeyDown={(e) => e.stopPropagation()}
    >
      <div className="flex-1 grid grid-cols-12 gap-3 overflow-hidden">
        <div className="col-span-7 flex flex-col gap-2 h-full min-h-0">
          <PumpSection cfg={cfg} onChange={patch} defaultPressure={3.4} />

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

        <div className="col-span-5 flex flex-col gap-2 h-full min-h-0">
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
