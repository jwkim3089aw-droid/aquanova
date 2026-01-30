// ui/src/features/flow-builder/components/FlowModals.tsx

import React, { useState, useEffect } from 'react';
import { Node } from 'reactflow';

// ui 폴더의 index.ts를 통해 에디터와 공용 컴포넌트 로드
import {
  Field,
  Input,
  HRROEditor,
  ROEditor,
  UFEditor,
  NFEditor,
  MFEditor,
  PumpEditor,
} from '..';

import MembraneSelect from './MembraneSelect';

// [NEW] 수질 카탈로그 import
import { WATER_CATALOG } from '../data/water_catalog';

import {
  UnitData,
  FlowData,
  EndpointData,
  UnitKind,
  ChemistryInput,
  unitLabel,
  UnitMode,
  clampf,
  SetNodesFn,
  SetEdgesFn,
} from '../model/types';

import { updateUnitCfg } from '../model/logic';

// ------------------------------------------------------------------
// Helper: Ion Input Field
// ------------------------------------------------------------------
function IonField({
  label,
  value,
  onChange,
}: {
  label: string;
  value: number | undefined;
  onChange: (v: number) => void;
}) {
  return (
    <div className="flex items-center justify-between gap-2 h-8 px-2 bg-slate-900 rounded border border-slate-700/50 hover:border-slate-600 focus-within:border-blue-500/50 transition-colors group">
      <span className="text-[11px] font-semibold text-slate-400 w-10 group-focus-within:text-blue-400 transition-colors">
        {label}
      </span>
      <input
        type="number"
        className="w-full bg-transparent text-right text-sm text-slate-200 outline-none placeholder:text-slate-700 focus:text-white font-mono"
        placeholder="0.0"
        value={value ?? ''}
        onFocus={(e) => e.target.select()}
        onChange={(e) => onChange(parseFloat(e.target.value) || 0)}
      />
      <span className="text-[9px] text-slate-600 w-6 text-right select-none">
        mg/L
      </span>
    </div>
  );
}

// ------------------------------------------------------------------
// Unit / Feed Settings Modal
// ------------------------------------------------------------------
interface InspectorProps {
  isOpen: boolean;
  onClose: () => void;
  selEndpoint: (Node<FlowData> & { data: EndpointData }) | null;
  selUnit: Node<FlowData> | null;
  feed: {
    flow_m3h: number;
    tds_mgL: number;
    temperature_C: number;
    ph: number;
  };
  setFeed: (v: any) => void;
  feedChemistry: ChemistryInput;
  setFeedChemistry: React.Dispatch<React.SetStateAction<ChemistryInput>>;
  unitMode: UnitMode;
  setNodes: SetNodesFn;
  setEdges: SetEdgesFn;
  setSelectedNodeId: (id: string | null) => void;
}

export function UnitInspectorModal(props: InspectorProps) {
  const {
    isOpen,
    onClose,
    selEndpoint,
    selUnit,
    feed,
    setFeed,
    feedChemistry,
    setFeedChemistry,
    unitMode,
    setNodes,
  } = props;

  const [localFeed, setLocalFeed] = useState(feed);
  const [localChem, setLocalChem] = useState<any>(feedChemistry);
  const [localCfg, setLocalCfg] = useState<any>(null);

  // -------------------------------------------------------------
  // [NUCLEAR FIX] 브라우저 레벨 이벤트 인터셉터
  // 모달이 열려있으면 window 레벨에서 Del 키 이벤트를 '캡쳐' 단계에서 죽여버립니다.
  // -------------------------------------------------------------
  useEffect(() => {
    if (!isOpen) return;

    const handleKeyDownCapture = (e: KeyboardEvent) => {
      // 1. 입력창(Input, Textarea)에서는 정상적으로 글자가 지워져야 함 -> 통과
      const target = e.target as HTMLElement;
      if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA') {
        return;
      }

      // 2. 그 외(배경 등)에서 Del이나 Backspace를 누르면 -> 즉결 처형
      if (e.key === 'Delete' || e.key === 'Backspace') {
        e.preventDefault(); // 브라우저 뒤로가기 방지
        e.stopPropagation(); // 상위로 전파 방지
        e.stopImmediatePropagation(); // ★ 가장 중요: ReactFlow가 듣기도 전에 차단
      }
    };

    // 'true' 옵션은 캡쳐링 단계(이벤트가 내려오는 단계)에서 낚아챈다는 뜻입니다.
    window.addEventListener('keydown', handleKeyDownCapture, true);

    return () => {
      window.removeEventListener('keydown', handleKeyDownCapture, true);
    };
  }, [isOpen]);

  // 로컬 상태 초기화
  useEffect(() => {
    if (isOpen) {
      setLocalFeed(feed);
      setLocalChem(feedChemistry || {});

      if (selUnit && selUnit.data.type === 'unit') {
        setLocalCfg(JSON.parse(JSON.stringify(selUnit.data.cfg)));
      } else {
        setLocalCfg(null);
      }
    }
  }, [isOpen, selEndpoint?.id, selUnit?.id]);

  if (!isOpen || (!selEndpoint && !selUnit)) return null;

  // ... (이하 로직 동일)
  const cationSum =
    (localChem.na_mgL || 0) +
    (localChem.k_mgL || 0) +
    (localChem.ca_mgL || 0) +
    (localChem.mg_mgL || 0) +
    (localChem.nh4_mgL || 0) +
    (localChem.sr_mgL || 0) +
    (localChem.ba_mgL || 0) +
    (localChem.fe_mgL || 0) +
    (localChem.mn_mgL || 0);
  const anionSum =
    (localChem.cl_mgL || 0) +
    (localChem.so4_mgL || 0) +
    (localChem.hco3_mgL || 0) +
    (localChem.no3_mgL || 0) +
    (localChem.f_mgL || 0) +
    (localChem.br_mgL || 0) +
    (localChem.po4_mgL || 0) +
    (localChem.co3_mgL || 0);
  const neutralSum =
    (localChem.sio2_mgL || 0) +
    (localChem.b_mgL || 0) +
    (localChem.co2_mgL || 0);
  const totalTDS = cationSum + anionSum + neutralSum;
  const calcHardness =
    (localChem.ca_mgL || 0) * 2.497 + (localChem.mg_mgL || 0) * 4.118;
  const calcAlkalinity =
    (localChem.hco3_mgL || 0) * 0.82 + (localChem.co3_mgL || 0) * 1.66;

  const applyPreset = (presetId: string) => {
    const preset = WATER_CATALOG.find((p) => p.id === presetId);
    if (!preset) return;

    const ions = preset.ions;
    const calcTDS = Object.values(ions).reduce((sum, v) => sum + v, 0);

    setLocalFeed((prev) => ({
      ...prev,
      temperature_C: preset.temp_C,
      ph: preset.ph,
      tds_mgL: calcTDS,
    }));

    setLocalChem({
      nh4_mgL: ions.NH4,
      k_mgL: ions.K,
      na_mgL: ions.Na,
      mg_mgL: ions.Mg,
      ca_mgL: ions.Ca,
      sr_mgL: ions.Sr,
      ba_mgL: ions.Ba,
      fe_mgL: ions.Fe,
      mn_mgL: ions.Mn,
      hco3_mgL: ions.HCO3,
      no3_mgL: ions.NO3,
      cl_mgL: ions.Cl,
      f_mgL: ions.F,
      so4_mgL: ions.SO4,
      br_mgL: ions.Br,
      po4_mgL: ions.PO4,
      co3_mgL: ions.CO3,
      sio2_mgL: ions.SiO2,
      b_mgL: ions.B,
      co2_mgL: ions.CO2,
      alkalinity_mgL_as_CaCO3: 0,
      calcium_hardness_mgL_as_CaCO3: 0,
    });
  };

  const handleApply = () => {
    if (selEndpoint?.data.role === 'feed') {
      setFeed({ ...localFeed, tds_mgL: totalTDS });
      setFeedChemistry(localChem);
    } else if (selUnit && localCfg) {
      updateUnitCfg(selUnit.id, localCfg, setNodes);
    }
    onClose();
  };

  const isProductNode = selEndpoint?.data.role === 'product';

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-[2px]"
      onClick={onClose}
    >
      <div
        className="w-[960px] max-h-[85vh] flex flex-col rounded-xl border border-slate-800 bg-slate-950 shadow-2xl ring-1 ring-white/5 overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3 border-b border-slate-800 bg-slate-900/50 shrink-0">
          <div className="flex items-center gap-2">
            <div
              className={`w-2 h-2 rounded-full ${selEndpoint ? 'bg-blue-500' : 'bg-emerald-500'}`}
            ></div>
            <h2 className="text-sm font-bold text-slate-100 uppercase tracking-wide">
              {selEndpoint?.data.role === 'feed'
                ? 'Feed Water Analysis'
                : selUnit
                  ? `${(selUnit.data as UnitData).kind} Configuration`
                  : 'Settings'}
            </h2>
          </div>
          <div className="flex items-center gap-2">
            {isProductNode ? (
              <button
                onClick={onClose}
                className="px-3 py-1 rounded text-xs font-medium text-slate-300 bg-slate-800 border border-slate-700 hover:bg-slate-700"
              >
                Close
              </button>
            ) : (
              <>
                <button
                  onClick={onClose}
                  className="px-3 py-1 rounded text-xs font-medium text-slate-400 hover:text-slate-200 transition-colors"
                >
                  Cancel
                </button>
                <button
                  onClick={handleApply}
                  className="px-4 py-1 rounded text-xs font-bold text-white bg-blue-600 hover:bg-blue-500 shadow-lg shadow-blue-900/20 transition-all active:scale-95"
                >
                  Apply
                </button>
              </>
            )}
          </div>
        </div>

        {/* Content Area */}
        <div className="flex-1 overflow-y-auto p-5 scrollbar-thin scrollbar-thumb-slate-700 scrollbar-track-transparent">
          {selEndpoint?.data.role === 'feed' ? (
            <div className="space-y-5">
              {/* 1. Water Library & Physical Props Grid */}
              <div className="grid grid-cols-12 gap-4">
                <div className="col-span-12 lg:col-span-8 p-3 bg-slate-900/50 border border-slate-800 rounded-lg flex flex-col justify-center">
                  <label className="text-[10px] font-bold text-blue-400 mb-1.5 uppercase tracking-wider">
                    🌊 Preset Library
                  </label>
                  <select
                    className="w-full bg-slate-950 border border-slate-700 rounded px-2 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-blue-500 cursor-pointer"
                    onChange={(e) => applyPreset(e.target.value)}
                    defaultValue=""
                  >
                    <option value="" disabled>
                      -- Load Standard Water Composition --
                    </option>
                    <optgroup label="Seawater">
                      {WATER_CATALOG.filter(
                        (w) => w.category === 'Seawater',
                      ).map((w) => (
                        <option key={w.id} value={w.id}>
                          {w.name}
                        </option>
                      ))}
                    </optgroup>
                    <optgroup label="Brackish Water">
                      {WATER_CATALOG.filter(
                        (w) => w.category === 'Brackish',
                      ).map((w) => (
                        <option key={w.id} value={w.id}>
                          {w.name}
                        </option>
                      ))}
                    </optgroup>
                    <optgroup label="Wastewater & Reuse">
                      {WATER_CATALOG.filter((w) =>
                        ['Waste', 'Reuse'].includes(w.category),
                      ).map((w) => (
                        <option key={w.id} value={w.id}>
                          {w.name}
                        </option>
                      ))}
                    </optgroup>
                  </select>
                </div>

                <div className="col-span-12 lg:col-span-4 grid grid-cols-2 gap-2">
                  <Field label={`Temp (${unitLabel('temp', unitMode)})`}>
                    <Input
                      className="h-9 text-center font-mono"
                      value={localFeed.temperature_C}
                      onChange={(e) =>
                        setLocalFeed({
                          ...localFeed,
                          temperature_C: Number(e.target.value),
                        })
                      }
                    />
                  </Field>
                  <Field label="pH Level">
                    <Input
                      className="h-9 text-center font-mono"
                      value={localFeed.ph}
                      min={0}
                      max={14}
                      onChange={(e) =>
                        setLocalFeed({
                          ...localFeed,
                          ph: clampf(Number(e.target.value), 0, 14),
                        })
                      }
                    />
                  </Field>
                  <div className="col-span-2">
                    <Field label={`Feed Flow (${unitLabel('flow', unitMode)})`}>
                      <Input
                        className="h-9 font-bold text-emerald-400 text-right font-mono"
                        value={localFeed.flow_m3h}
                        onChange={(e) =>
                          setLocalFeed({
                            ...localFeed,
                            flow_m3h: Number(e.target.value),
                          })
                        }
                      />
                    </Field>
                  </div>
                </div>
              </div>

              {/* 2. Calculated Summary */}
              <div className="grid grid-cols-3 gap-px bg-slate-800 rounded-lg overflow-hidden border border-slate-800">
                <div className="bg-slate-900/80 p-3 flex flex-col items-center justify-center gap-1">
                  <span className="text-[10px] font-bold text-slate-500 uppercase">
                    Total TDS
                  </span>
                  <div className="text-xl font-mono text-emerald-400 font-bold">
                    {totalTDS.toFixed(2)}{' '}
                    <span className="text-xs font-normal text-slate-600">
                      mg/L
                    </span>
                  </div>
                </div>
                <div className="bg-slate-900/80 p-3 flex flex-col items-center justify-center gap-1">
                  <span className="text-[10px] font-bold text-slate-500 uppercase">
                    Hardness
                  </span>
                  <div className="text-xl font-mono text-blue-300 font-medium">
                    {calcHardness.toFixed(1)}{' '}
                    <span className="text-xs font-normal text-slate-600">
                      as CaCO3
                    </span>
                  </div>
                </div>
                <div className="bg-slate-900/80 p-3 flex flex-col items-center justify-center gap-1">
                  <span className="text-[10px] font-bold text-slate-500 uppercase">
                    Alkalinity
                  </span>
                  <div className="text-xl font-mono text-blue-300 font-medium">
                    {calcAlkalinity.toFixed(1)}{' '}
                    <span className="text-xs font-normal text-slate-600">
                      as CaCO3
                    </span>
                  </div>
                </div>
              </div>

              {/* 3. Detailed Chemistry */}
              <div className="pt-2">
                <h3 className="text-xs font-bold text-slate-300 mb-3 flex items-center gap-2">
                  <span className="w-1 h-4 bg-blue-500 rounded-sm"></span>
                  Detailed Ionic Composition
                </h3>

                <div className="grid grid-cols-3 gap-3">
                  <div className="bg-slate-900/40 p-3 rounded border border-blue-900/30">
                    <div className="text-[10px] font-bold text-blue-400 mb-2 flex justify-between uppercase tracking-wider">
                      <span>Cations (+)</span>{' '}
                      <span>{cationSum.toFixed(1)}</span>
                    </div>
                    <div className="space-y-1">
                      <IonField
                        label="NH4"
                        value={localChem.nh4_mgL}
                        onChange={(v) =>
                          setLocalChem({ ...localChem, nh4_mgL: v })
                        }
                      />
                      <IonField
                        label="K"
                        value={localChem.k_mgL}
                        onChange={(v) =>
                          setLocalChem({ ...localChem, k_mgL: v })
                        }
                      />
                      <IonField
                        label="Na"
                        value={localChem.na_mgL}
                        onChange={(v) =>
                          setLocalChem({ ...localChem, na_mgL: v })
                        }
                      />
                      <IonField
                        label="Mg"
                        value={localChem.mg_mgL}
                        onChange={(v) =>
                          setLocalChem({ ...localChem, mg_mgL: v })
                        }
                      />
                      <IonField
                        label="Ca"
                        value={localChem.ca_mgL}
                        onChange={(v) =>
                          setLocalChem({ ...localChem, ca_mgL: v })
                        }
                      />
                      <IonField
                        label="Sr"
                        value={localChem.sr_mgL}
                        onChange={(v) =>
                          setLocalChem({ ...localChem, sr_mgL: v })
                        }
                      />
                      <IonField
                        label="Ba"
                        value={localChem.ba_mgL}
                        onChange={(v) =>
                          setLocalChem({ ...localChem, ba_mgL: v })
                        }
                      />
                      <IonField
                        label="Fe"
                        value={localChem.fe_mgL}
                        onChange={(v) =>
                          setLocalChem({ ...localChem, fe_mgL: v })
                        }
                      />
                      <IonField
                        label="Mn"
                        value={localChem.mn_mgL}
                        onChange={(v) =>
                          setLocalChem({ ...localChem, mn_mgL: v })
                        }
                      />
                    </div>
                  </div>

                  <div className="bg-slate-900/40 p-3 rounded border border-rose-900/30">
                    <div className="text-[10px] font-bold text-rose-400 mb-2 flex justify-between uppercase tracking-wider">
                      <span>Anions (-)</span> <span>{anionSum.toFixed(1)}</span>
                    </div>
                    <div className="space-y-1">
                      <IonField
                        label="HCO3"
                        value={localChem.hco3_mgL}
                        onChange={(v) =>
                          setLocalChem({ ...localChem, hco3_mgL: v })
                        }
                      />
                      <IonField
                        label="NO3"
                        value={localChem.no3_mgL}
                        onChange={(v) =>
                          setLocalChem({ ...localChem, no3_mgL: v })
                        }
                      />
                      <IonField
                        label="Cl"
                        value={localChem.cl_mgL}
                        onChange={(v) =>
                          setLocalChem({ ...localChem, cl_mgL: v })
                        }
                      />
                      <IonField
                        label="F"
                        value={localChem.f_mgL}
                        onChange={(v) =>
                          setLocalChem({ ...localChem, f_mgL: v })
                        }
                      />
                      <IonField
                        label="SO4"
                        value={localChem.so4_mgL}
                        onChange={(v) =>
                          setLocalChem({ ...localChem, so4_mgL: v })
                        }
                      />
                      <IonField
                        label="Br"
                        value={localChem.br_mgL}
                        onChange={(v) =>
                          setLocalChem({ ...localChem, br_mgL: v })
                        }
                      />
                      <IonField
                        label="PO4"
                        value={localChem.po4_mgL}
                        onChange={(v) =>
                          setLocalChem({ ...localChem, po4_mgL: v })
                        }
                      />
                      <IonField
                        label="CO3"
                        value={localChem.co3_mgL}
                        onChange={(v) =>
                          setLocalChem({ ...localChem, co3_mgL: v })
                        }
                      />
                    </div>
                  </div>

                  <div className="bg-slate-900/40 p-3 rounded border border-emerald-900/30">
                    <div className="text-[10px] font-bold text-emerald-400 mb-2 flex justify-between uppercase tracking-wider">
                      <span>Neutrals</span> <span>{neutralSum.toFixed(1)}</span>
                    </div>
                    <div className="space-y-1">
                      <IonField
                        label="SiO2"
                        value={localChem.sio2_mgL}
                        onChange={(v) =>
                          setLocalChem({ ...localChem, sio2_mgL: v })
                        }
                      />
                      <IonField
                        label="B"
                        value={localChem.b_mgL}
                        onChange={(v) =>
                          setLocalChem({ ...localChem, b_mgL: v })
                        }
                      />
                      <IonField
                        label="CO2"
                        value={localChem.co2_mgL}
                        onChange={(v) =>
                          setLocalChem({ ...localChem, co2_mgL: v })
                        }
                      />
                    </div>
                  </div>
                </div>
              </div>
            </div>
          ) : selUnit && localCfg ? (
            /* Unit Configuration */
            (() => {
              const u = selUnit.data as UnitData;
              const kind = u.kind as UnitKind;
              const proxyUnit = { ...u, cfg: localCfg };
              const updateCfg = (newCfg: any) => setLocalCfg(newCfg);

              if (kind === 'HRRO')
                return <HRROEditor node={proxyUnit} onChange={updateCfg} />;
              if (kind === 'RO')
                return (
                  <ROEditor node={proxyUnit} onChange={updateCfg as any} />
                );
              if (kind === 'UF')
                return (
                  <UFEditor node={proxyUnit} onChange={updateCfg as any} />
                );
              if (kind === 'NF')
                return (
                  <NFEditor node={proxyUnit} onChange={updateCfg as any} />
                );
              if (kind === 'MF')
                return (
                  <MFEditor node={proxyUnit} onChange={updateCfg as any} />
                );
              if (kind === 'PUMP')
                return (
                  <PumpEditor node={proxyUnit as any} onChange={updateCfg} />
                );

              return (
                <div className="text-sm text-red-300">
                  Unknown Unit Type: {kind}
                </div>
              );
            })()
          ) : isProductNode ? (
            <div className="h-full flex flex-col items-center justify-center text-slate-500 opacity-60">
              <div className="text-4xl mb-2">🏁</div>
              <p className="text-sm font-medium">Final Product Water</p>
              <p className="text-xs">Results available after simulation</p>
            </div>
          ) : (
            <div className="text-sm text-slate-400">No node selected.</div>
          )}
        </div>
      </div>
    </div>
  );
}

// Global Options Modal (Keep unchanged or apply similar capture logic if needed)
interface GlobalOptionsProps {
  isOpen: boolean;
  onClose: () => void;
  optAuto: boolean;
  setOptAuto: (v: boolean) => void;
  optMembrane: any;
  setOptMembrane: (v: any) => void;
  optSegments: number;
  setOptSegments: (v: number) => void;
  optPumpEff: number;
  setOptPumpEff: (v: number) => void;
  optErdEff: number;
  setOptErdEff: (v: number) => void;
  stageTypeHint: 'RO' | 'NF' | 'UF' | 'MF' | 'HRRO' | undefined;
}

export function GlobalOptionsModal(props: GlobalOptionsProps) {
  const {
    isOpen,
    onClose,
    optAuto,
    setOptAuto,
    optMembrane,
    setOptMembrane,
    optSegments,
    setOptSegments,
    optPumpEff,
    setOptPumpEff,
    optErdEff,
    setOptErdEff,
    stageTypeHint,
  } = props;

  // [Optional] Global Options Modal에도 동일한 보호 로직 적용
  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDownCapture = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement;
      if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA') return;
      if (e.key === 'Delete' || e.key === 'Backspace') {
        e.preventDefault();
        e.stopPropagation();
        e.stopImmediatePropagation();
      }
    };
    window.addEventListener('keydown', handleKeyDownCapture, true);
    return () =>
      window.removeEventListener('keydown', handleKeyDownCapture, true);
  }, [isOpen]);

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-[2px]"
      onClick={onClose}
    >
      <div
        className="w-full max-w-md rounded-xl border border-slate-700 bg-slate-950 p-0 shadow-2xl overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* ... (기존 내용 동일) */}
        <div className="flex items-center justify-between px-5 py-3 border-b border-slate-800 bg-slate-900/50">
          <h2 className="text-sm font-bold text-slate-100 uppercase tracking-wide">
            Global Project Options
          </h2>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-white transition-colors"
          >
            ✕
          </button>
        </div>

        <div className="p-5 space-y-5">
          <div className="flex items-center gap-3 p-3 bg-blue-900/10 border border-blue-900/30 rounded-lg">
            <label className="flex items-center gap-3 w-full cursor-pointer">
              <input
                type="checkbox"
                className="w-4 h-4 rounded border-slate-600 bg-slate-800 text-blue-600 focus:ring-offset-0 focus:ring-0"
                checked={optAuto}
                onChange={(e) => setOptAuto(e.target.checked)}
              />
              <div className="flex flex-col">
                <span className="text-sm font-bold text-blue-100">
                  Auto-Configuration Mode
                </span>
                <span className="text-[10px] text-blue-300/70">
                  Automatically calculate element quantity based on flow
                </span>
              </div>
            </label>
          </div>

          <div className="space-y-4">
            <div>
              <label className="block text-[10px] font-bold text-slate-400 uppercase mb-1.5">
                Default Membrane Model
              </label>
              <MembraneSelect
                unitType={stageTypeHint || 'RO'}
                mode="catalog"
                model={
                  typeof optMembrane === 'string'
                    ? optMembrane
                    : optMembrane?.membrane_model
                }
                onChange={(v) => setOptMembrane(v)}
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <Field label="Elements per Vessel">
                <Input
                  disabled={optAuto}
                  className="text-center"
                  value={optSegments}
                  onChange={(e) => setOptSegments(Number(e.target.value))}
                />
              </Field>
              <div className="col-span-1"></div>
              <Field label="Pump Efficiency (0-1)">
                <Input
                  disabled={optAuto}
                  className="text-center"
                  value={optPumpEff}
                  step={0.01}
                  onChange={(e) => setOptPumpEff(Number(e.target.value))}
                />
              </Field>
              <Field label="ERD Efficiency (0-1)">
                <Input
                  disabled={optAuto}
                  className="text-center"
                  value={optErdEff}
                  step={0.01}
                  onChange={(e) => setOptErdEff(Number(e.target.value))}
                />
              </Field>
            </div>
          </div>
        </div>

        <div className="px-5 py-3 bg-slate-900/30 border-t border-slate-800 flex justify-end">
          <button
            onClick={onClose}
            className="px-5 py-1.5 bg-slate-100 hover:bg-white text-slate-900 rounded-md text-xs font-bold transition-colors shadow-lg"
          >
            Save & Close
          </button>
        </div>
      </div>
    </div>
  );
}
