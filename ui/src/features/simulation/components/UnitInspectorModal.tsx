import React, { useEffect, useState } from 'react';
import type { Node } from 'reactflow';

import {
  HRROEditor,
  ROEditor,
  UFEditor,
  NFEditor,
  MFEditor,
  PumpEditor,
} from '..'; // index.ts에서 export한다고 가정

import {
  DEFAULT_CHEMISTRY,
  type UnitData,
  type FlowData,
  type EndpointData,
  type UnitKind,
  type ChemistryInput,
  type UnitMode,
  type SetNodesFn,
  type SetEdgesFn,
  type HRROConfig,
  type ROConfig,
  type NFConfig,
  type UFConfig,
  type MFConfig,
  type PumpConfig,
} from '../model/types';

import { updateUnitCfg } from '../model/logic';
import { useBlockDeleteKeysWhenOpen } from '../hooks/useBlockDeleteKeysWhenOpen';

import { FeedInspectorBody } from './FeedInspectorBody';
import { useFeedChargeBalance } from '../hooks/useFeedChargeBalance';
import { roundTo, type ChargeBalanceMode } from '../chemistry';
import { normalizeWaterType, type FeedWaterType } from '../model/feedWater';

// ------------------------------------------------------------------
// Type Definitions
// ------------------------------------------------------------------
type FeedDraft = {
  flow_m3h: number;
  tds_mgL: number;
  temperature_C: number;
  ph: number;
  pressure_bar?: number;

  water_type?: FeedWaterType | string | null;
  water_subtype?: string | null;

  turbidity_ntu?: number | null;
  tss_mgL?: number | null;
  sdi15?: number | null;
  toc_mgL?: number | null;

  temp_min_C?: number | null;
  temp_max_C?: number | null;
  feed_note?: string | null;

  charge_balance_mode?: ChargeBalanceMode | null;

  [k: string]: unknown;
};

interface InspectorProps {
  isOpen: boolean;
  onClose: () => void;
  selEndpoint: (Node<FlowData> & { data: EndpointData }) | null;
  selUnit: Node<FlowData> | null;

  feed: FeedDraft;
  setFeed: React.Dispatch<React.SetStateAction<FeedDraft>>;

  feedChemistry: ChemistryInput;
  setFeedChemistry: React.Dispatch<React.SetStateAction<ChemistryInput>>;

  unitMode: UnitMode;
  setNodes: SetNodesFn;
  setEdges: SetEdgesFn;
  setSelectedNodeId: (id: string | null) => void;
}

// ------------------------------------------------------------------
// Main Component
// ------------------------------------------------------------------
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

  // 키보드 삭제 키 방지 (모달 열려있을 때)
  useBlockDeleteKeysWhenOpen(isOpen);

  // Local State for Editing
  const [localFeed, setLocalFeed] = useState<FeedDraft>(feed);
  const [localChem, setLocalChem] = useState<ChemistryInput>(
    feedChemistry ?? DEFAULT_CHEMISTRY,
  );
  // Unit Config State (Generic Container)
  const [localCfg, setLocalCfg] = useState<UnitData['cfg'] | null>(null);

  // Feed Specific States
  const [quick, setQuick] = useState({ nacl_mgL: 0, mgso4_mgL: 0 });
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [cbMode, setCbMode] = useState<ChargeBalanceMode>('anions');

  // Derived Calculations (Charge Balance)
  const derived = useFeedChargeBalance(localChem, cbMode);

  // Sync State on Open/Selection Change
  useEffect(() => {
    if (!isOpen) return;

    // 1. Sync Feed Data
    const minT = feed?.temp_min_C ?? feed.temperature_C;
    const maxT = feed?.temp_max_C ?? feed.temperature_C;
    const wt = normalizeWaterType(feed?.water_type);

    setLocalFeed({
      ...feed,
      water_type: wt ?? '',
      water_subtype: feed?.water_subtype ?? '',
      temp_min_C: minT,
      temp_max_C: maxT,
      feed_note: feed?.feed_note ?? '',
    });

    setLocalChem(feedChemistry ?? DEFAULT_CHEMISTRY);
    setQuick({ nacl_mgL: 0, mgso4_mgL: 0 });
    setDetailsOpen(false);

    const saved = feed?.charge_balance_mode ?? null;
    setCbMode(saved ?? 'anions');

    // 2. Sync Unit Config
    if (selUnit && (selUnit.data as any).type === 'unit') {
      const u = selUnit.data as UnitData;
      // Deep copy to prevent direct mutation of node data
      setLocalCfg(JSON.parse(JSON.stringify(u.cfg)));
    } else {
      setLocalCfg(null);
    }
  }, [isOpen, selEndpoint?.id, selUnit?.id, feed, feedChemistry]);

  if (!isOpen || (!selEndpoint && !selUnit)) return null;

  const isFeedNode = selEndpoint?.data.role === 'feed';
  const isProductNode = selEndpoint?.data.role === 'product';

  // Apply Changes
  const handleApply = () => {
    if (isFeedNode) {
      // Feed Update Logic
      const subtype = String(localFeed.water_subtype ?? '').trim();
      const note = String(localFeed.feed_note ?? '').trim();

      const chemOut: ChemistryInput = {
        ...localChem,
        ...(derived.chemUsed ?? localChem),
        alkalinity_mgL_as_CaCO3: derived.calcAlkalinity,
        calcium_hardness_mgL_as_CaCO3: derived.calcHardness,
      };

      setFeed((prev) => ({
        ...prev,
        ...localFeed,
        tds_mgL: roundTo(derived.totalTDS, 2),
        water_type: normalizeWaterType(localFeed.water_type),
        water_subtype: subtype.length > 0 ? subtype : null,
        feed_note: note.length > 0 ? note : null,
        charge_balance_mode: cbMode,
      }));

      setFeedChemistry(chemOut);
    } else if (selUnit && localCfg) {
      // Unit Update Logic
      updateUnitCfg(selUnit.id, localCfg, setNodes);
    }

    onClose();
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4"
      onClick={onClose}
    >
      {/* Large Modal Container */}
      <div
        className="w-full max-w-[1600px] h-[92vh] max-h-[1080px] flex flex-col rounded-xl border border-slate-800 bg-slate-950 shadow-2xl ring-1 ring-white/5 overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header Section */}
        <div className="flex items-center justify-between px-5 py-3 border-b border-slate-800 bg-slate-900/50 shrink-0 h-[60px]">
          <div className="flex items-center gap-3">
            <div
              className={`w-3 h-3 rounded-full shadow-lg ${
                selEndpoint
                  ? 'bg-blue-500 shadow-blue-500/40'
                  : 'bg-emerald-500 shadow-emerald-500/40'
              }`}
            />
            <div>
              <h2 className="text-base font-bold text-slate-100 tracking-wide flex items-center gap-2">
                {isFeedNode
                  ? '원수(FEED) 수질 분석'
                  : selUnit
                    ? `${(selUnit.data as UnitData).kind} 설정`
                    : '설정'}
              </h2>
            </div>
            {isFeedNode && (
              <span className="text-[11px] text-slate-500 ml-2 pt-1">
                (이온 조성 입력 → TDS/경도/알칼리도 자동 계산)
              </span>
            )}
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={onClose}
              className="px-4 py-2 rounded text-xs font-medium text-slate-400 hover:text-slate-200 hover:bg-slate-800 transition-colors"
            >
              취소
            </button>
            {!isProductNode && (
              <button
                onClick={handleApply}
                className="px-6 py-2 rounded text-xs font-bold text-white bg-blue-600 hover:bg-blue-500 shadow-lg shadow-blue-900/20 active:scale-95 transition-all"
              >
                적용
              </button>
            )}
            {isProductNode && (
              <button
                onClick={onClose}
                className="px-4 py-2 rounded text-xs font-medium text-slate-300 bg-slate-800 border border-slate-700 hover:bg-slate-700"
              >
                닫기
              </button>
            )}
          </div>
        </div>

        {/* Content Body */}
        <div className="flex-1 overflow-hidden bg-slate-950 p-4">
          {isFeedNode ? (
            <FeedInspectorBody
              localFeed={localFeed}
              setLocalFeed={setLocalFeed}
              localChem={localChem}
              setLocalChem={setLocalChem}
              quick={quick}
              setQuick={setQuick}
              detailsOpen={detailsOpen}
              setDetailsOpen={setDetailsOpen}
              cbMode={cbMode}
              setCbMode={setCbMode}
              unitMode={unitMode}
              compact={false}
              derived={derived}
            />
          ) : selUnit && localCfg ? (
            <div className="h-full overflow-y-auto pr-2 custom-scrollbar">
              {/* Unit Type Switching */}
              {(() => {
                const u = selUnit.data as UnitData;
                const kind = u.kind as UnitKind;
                const updateCfg = (newCfg: UnitData['cfg']) =>
                  setLocalCfg(newCfg);

                switch (kind) {
                  case 'HRRO':
                    return (
                      <HRROEditor
                        node={{ ...u, cfg: localCfg as HRROConfig } as any}
                        feed={localFeed}
                        onChange={updateCfg as any}
                      />
                    );
                  case 'RO':
                    return (
                      <ROEditor
                        node={{ ...u, cfg: localCfg as ROConfig } as any}
                        onChange={updateCfg as any}
                      />
                    );
                  case 'UF':
                    return (
                      <UFEditor
                        node={{ ...u, cfg: localCfg as UFConfig } as any}
                        onChange={updateCfg as any}
                      />
                    );
                  case 'NF':
                    return (
                      <NFEditor
                        node={{ ...u, cfg: localCfg as NFConfig } as any}
                        onChange={updateCfg as any}
                      />
                    );
                  case 'MF':
                    return (
                      <MFEditor
                        node={{ ...u, cfg: localCfg as MFConfig } as any}
                        onChange={updateCfg as any}
                      />
                    );
                  case 'PUMP':
                    return (
                      <PumpEditor
                        node={{ ...u, cfg: localCfg as PumpConfig } as any}
                        onChange={updateCfg as any}
                      />
                    );
                  default:
                    return (
                      <div className="text-sm text-red-300">
                        Unknown Unit Type: {kind}
                      </div>
                    );
                }
              })()}
            </div>
          ) : (
            <div className="h-full flex items-center justify-center text-slate-500">
              정보가 없습니다.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
