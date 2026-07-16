// ui/src/features/simulation/editors/UnitForms/MFEditor.tsx

import React from 'react';
import { Field, Input } from '../../components/Common';
import MembraneSelect from '../../components/MembraneSelect';
import { UnitData } from '../../model/types';
import { GROUP_CLS, HEADER_CLS, INPUT_CLS, mapMembraneChange } from './utils';
import { PumpSection } from './PumpSection';

export function MFEditor({
  node,
  feed,
  onChange,
}: {
  node: UnitData | undefined;
  feed?: any;
  onChange: (cfg: any) => void;
}) {
  if (!node || node.kind !== 'MF')
    return (
      <div className="text-red-400 text-xs p-4">
        유효하지 않은 데이터입니다. (Invalid Data)
      </div>
    );

  // MF 기본 설정값 (UF와 유사하지만 MF에 맞는 필드 사용)
  const cfg = {
    modules_count: 50,
    flux_lmh: 50.0,
    recovery_pct: 90.0,
    max_tmp_bar: 2.5,
    ...node.cfg,
  };

  const patch = (p: any) => onChange({ ...cfg, ...p });

  // 🛑 상단 대시보드(KPI) 표시용 계산
  const feedFlow = feed?.flow_m3h ?? 0;
  const currentArea = cfg.custom_area_m2 ?? cfg.membrane_area_m2 ?? 50.0;
  const totalArea = currentArea * (cfg.modules_count || 1);
  const grossPermeate = totalArea > 0 ? (cfg.flux_lmh * totalArea) / 1000 : 0;

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
            {cfg.modules_count}{' '}
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
            {cfg.flux_lmh.toFixed(1)}{' '}
            <small className="text-[9px] font-normal text-amber-600/70">
              LMH
            </small>
          </span>
        </div>
        <div className="flex flex-col items-center">
          <span className="text-[10px] text-blue-400 font-bold mb-0.5 uppercase tracking-wide">
            예상 총 생산량 (Gross Flow)
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
        {/* 좌측 패널 (Left Column) */}
        <div className="col-span-7 flex flex-col gap-2 h-full min-h-0 overflow-y-auto custom-scrollbar pr-1 pb-4">
          <PumpSection cfg={cfg} onChange={patch} defaultPressure={2.0} />

          <div className="shrink-0">
            <div className="px-3 py-2 bg-slate-800/90 border border-slate-700 rounded-t-md text-[11px] font-bold text-slate-200 tracking-wide">
              멤브레인 모델 (Membrane Type: {node.kind})
            </div>
            <div className="p-3 border-x border-b border-slate-700 bg-slate-900/60 rounded-b-md">
              <MembraneSelect
                unitType="MF"
                mode={cfg.membrane_mode}
                model={cfg.membrane_model}
                area={cfg.custom_area_m2 ?? cfg.membrane_area_m2 ?? 50.0}
                A={cfg.custom_A_lmh_bar ?? cfg.membrane_A_lmh_bar}
                onChange={(updates) => patch(mapMembraneChange(updates))}
              />
            </div>
          </div>
        </div>

        {/* 우측 패널 (Right Column) */}
        <div className="col-span-5 flex flex-col gap-2 h-full min-h-0">
          <div
            className={`${GROUP_CLS} flex-1 !mb-0 overflow-y-auto custom-scrollbar pr-1`}
          >
            <h4 className={HEADER_CLS}>⚙️ 운전 조건 (Operating Conditions)</h4>
            <div className="flex flex-col gap-3">
              <Field label="총 모듈 수 (Total Modules)">
                <Input
                  className={INPUT_CLS}
                  type="number"
                  value={cfg.modules_count}
                  onChange={(e) =>
                    patch({ modules_count: Number(e.target.value) })
                  }
                />
              </Field>
              <Field label="목표 설계 플럭스 (Design Flux, LMH)">
                <Input
                  className={`${INPUT_CLS} text-blue-300 font-bold bg-blue-950/40`}
                  type="number"
                  step={0.1}
                  value={cfg.flux_lmh}
                  onChange={(e) => patch({ flux_lmh: Number(e.target.value) })}
                />
              </Field>
              <Field label="시스템 회수율 (Recovery, %)">
                <Input
                  className={`${INPUT_CLS} text-amber-400 font-bold`}
                  type="number"
                  step={0.1}
                  value={cfg.recovery_pct}
                  onChange={(e) =>
                    patch({ recovery_pct: Number(e.target.value) })
                  }
                />
              </Field>
              <Field label="최대 허용 압력 (Max TMP, bar)">
                <Input
                  className={INPUT_CLS}
                  type="number"
                  step={0.1}
                  value={cfg.max_tmp_bar}
                  onChange={(e) =>
                    patch({ max_tmp_bar: Number(e.target.value) })
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
