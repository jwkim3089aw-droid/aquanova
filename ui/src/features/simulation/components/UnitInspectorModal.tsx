// ui/src/features/simulation/components/UnitInspectorModal.tsx
import React, { useEffect, useLayoutEffect, useRef, useState } from 'react';
import type { Node } from 'reactflow';

import {
  HRROEditor,
  ROEditor,
  UFEditor,
  NFEditor,
  MFEditor,
  PumpEditor,
} from '..';

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
  type ROConfig,
  type NFConfig,
  type UFConfig,
  type MFConfig,
  type HRROConfig,
  type PumpConfig,
} from '../model/types';

import { updateUnitCfg } from '../model/logic';
import { useBlockDeleteKeysWhenOpen } from '../hooks/useBlockDeleteKeysWhenOpen';

import { FeedInspectorBody } from './FeedInspectorBody';
import { useFeedChargeBalance } from '../hooks/useFeedChargeBalance';
import { roundTo, type ChargeBalanceMode } from '../chemistry';

// ✅ water_type 정석화(백엔드 enum) 유틸
import { normalizeWaterType, type FeedWaterType } from '../model/feedWater';

// ------------------------------------------------------------------
// Unit / Feed Settings Modal
// ------------------------------------------------------------------
type FeedDraft = {
  flow_m3h: number;
  tds_mgL: number;
  temperature_C: number;
  ph: number;
  pressure_bar?: number;

  // ✅ 백엔드 enum과 일치(과거 데이터/하위호환 string도 허용)
  water_type?: FeedWaterType | string | null;
  water_subtype?: string | null;

  turbidity_ntu?: number | null;
  tss_mgL?: number | null;
  sdi15?: number | null;
  toc_mgL?: number | null;

  temp_min_C?: number | null;
  temp_max_C?: number | null;
  feed_note?: string | null;

  // UI 설정 저장용
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

  useBlockDeleteKeysWhenOpen(isOpen);

  const [localFeed, setLocalFeed] = useState<FeedDraft>(feed);
  const [localChem, setLocalChem] = useState<ChemistryInput>(
    feedChemistry ?? DEFAULT_CHEMISTRY,
  );
  const [localCfg, setLocalCfg] = useState<UnitData['cfg'] | null>(null);

  const [quick, setQuick] = useState({ nacl_mgL: 0, mgso4_mgL: 0 });
  const [detailsOpen, setDetailsOpen] = useState(false);

  // “한 화면 맞춤” 모드
  const [fitMode, setFitMode] = useState(true);
  const [fitScale, setFitScale] = useState(1);
  const [fitNeedsScroll, setFitNeedsScroll] = useState(false);

  const bodyRef = useRef<HTMLDivElement | null>(null);
  const contentRef = useRef<HTMLDivElement | null>(null);

  // 전하 보정 모드 (WAVE)
  const [cbMode, setCbMode] = useState<ChargeBalanceMode>('anions');

  useEffect(() => {
    if (!isOpen) return;

    const minT = feed?.temp_min_C ?? feed.temperature_C;
    const maxT = feed?.temp_max_C ?? feed.temperature_C;

    // ✅ 과거 데이터에 "해수" 같은 값이 있어도 enum으로 정규화해서 UI 상태를 만든다
    const wt = normalizeWaterType(feed?.water_type);

    setLocalFeed({
      ...feed,
      water_type: wt ?? '',
      water_subtype:
        feed?.water_subtype == null ? '' : String(feed.water_subtype),
      temp_min_C: minT,
      temp_max_C: maxT,
      feed_note: feed?.feed_note ?? '',
    });

    setLocalChem(feedChemistry ?? DEFAULT_CHEMISTRY);
    setQuick({ nacl_mgL: 0, mgso4_mgL: 0 });
    setDetailsOpen(false);

    const saved = feed?.charge_balance_mode ?? null;
    setCbMode(saved ?? 'anions');

    if (selUnit && (selUnit.data as any).type === 'unit') {
      const u = selUnit.data as UnitData;
      setLocalCfg(JSON.parse(JSON.stringify(u.cfg)) as UnitData['cfg']);
    } else {
      setLocalCfg(null);
    }

    setFitScale(1);
    setFitNeedsScroll(false);
  }, [isOpen, selEndpoint?.id, selUnit?.id, feed, feedChemistry]);

  // Fit 스케일 계산
  const fitActive = fitMode && !detailsOpen;

  useLayoutEffect(() => {
    if (!isOpen) return;

    if (!fitActive) {
      setFitScale(1);
      setFitNeedsScroll(false);
      return;
    }

    const body = bodyRef.current;
    const content = contentRef.current;
    if (!body || !content) return;

    const minScale = 0.85;

    const compute = () => {
      const b = bodyRef.current;
      const c = contentRef.current;
      if (!b || !c) return;

      const availH = Math.max(0, b.clientHeight - 8);
      const availW = Math.max(0, b.clientWidth - 8);

      const needH = c.scrollHeight;
      const needW = c.scrollWidth;

      if (needH <= 0 || needW <= 0 || availH <= 0 || availW <= 0) return;

      const sH = availH / needH;
      const sW = availW / needW;
      const raw = Math.min(1, sH, sW) * 0.98;

      const needsScroll = raw < minScale;

      if (needsScroll) {
        setFitNeedsScroll(true);
        setFitScale(1);
      } else {
        setFitNeedsScroll(false);
        setFitScale(raw);
      }

      requestAnimationFrame(() => {
        const bb = bodyRef.current;
        if (!bb) return;
        if (!needsScroll) {
          bb.scrollTop = 0;
          bb.scrollLeft = 0;
        }
      });
    };

    compute();

    const ro = new ResizeObserver(() => compute());
    ro.observe(body);
    ro.observe(content);

    window.addEventListener('resize', compute);
    return () => {
      ro.disconnect();
      window.removeEventListener('resize', compute);
    };
  }, [isOpen, fitActive]);

  // ✅✅✅ 핵심: 커스텀 훅은 "항상" 호출되어야 함 (return null 이전)
  const derived = useFeedChargeBalance(localChem, cbMode);

  // 이제부터 return null 해도 훅 순서는 깨지지 않음
  if (!isOpen || (!selEndpoint && !selUnit)) return null;

  const isFeedNode = selEndpoint?.data.role === 'feed';
  const isProductNode = selEndpoint?.data.role === 'product';

  const compact = fitActive;

  const handleApply = () => {
    if (isFeedNode) {
      const subtype = String(localFeed.water_subtype ?? '').trim();
      const note = String(localFeed.feed_note ?? '').trim();

      // ✅ derived.chemUsed는 "이온표(보정 적용)" 값,
      // ✅ scaling fields(알칼리/경도) 포함을 위해 localChem과 merge
      const chemOut: ChemistryInput = {
        ...localChem,
        ...(derived.chemUsed ?? localChem),
        alkalinity_mgL_as_CaCO3: derived.calcAlkalinity,
        calcium_hardness_mgL_as_CaCO3: derived.calcHardness,
      };

      // ✅ API/저장에 들어가는 값은 반드시 enum으로 정규화
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
      updateUnitCfg(selUnit.id, localCfg, setNodes);
    }
    onClose();
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-[2px]"
      onClick={onClose}
    >
      <div
        className="w-[min(1420px,96vw)] max-h-[96vh] flex flex-col rounded-xl border border-slate-800 bg-slate-950 shadow-2xl ring-1 ring-white/5 overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3 border-b border-slate-800 bg-slate-900/50 shrink-0">
          <div className="flex items-center gap-2">
            <div
              className={`w-2 h-2 rounded-full ${
                selEndpoint ? 'bg-blue-500' : 'bg-emerald-500'
              }`}
            />
            <h2 className="text-sm font-bold text-slate-100 tracking-wide">
              {isFeedNode
                ? '원수(FEED) 수질 분석'
                : selUnit
                  ? `${(selUnit.data as UnitData).kind} 설정`
                  : '설정'}
            </h2>
            {isFeedNode && (
              <span className="text-[11px] text-slate-500">
                (이온 조성 → TDS/경도/알칼리도 자동 계산)
              </span>
            )}
          </div>

          <div className="flex items-center gap-2">
            {isFeedNode && (
              <button
                onClick={() => setFitMode((v) => !v)}
                className={`px-3 py-1 rounded text-xs font-bold border transition-colors ${
                  fitMode
                    ? 'text-emerald-200 bg-emerald-900/20 border-emerald-900/40 hover:bg-emerald-900/30'
                    : 'text-slate-200 bg-slate-800 border-slate-700 hover:bg-slate-700'
                }`}
                title="상세 닫힘 상태에서 화면에 맞게 자동 축소/확대합니다."
              >
                화면 맞춤 {fitMode ? 'ON' : 'OFF'}
              </button>
            )}

            {isProductNode ? (
              <button
                onClick={onClose}
                className="px-3 py-1 rounded text-xs font-medium text-slate-300 bg-slate-800 border border-slate-700 hover:bg-slate-700"
              >
                닫기
              </button>
            ) : (
              <>
                <button
                  onClick={onClose}
                  className="px-3 py-1 rounded text-xs font-medium text-slate-400 hover:text-slate-200 transition-colors"
                >
                  취소
                </button>
                <button
                  onClick={handleApply}
                  className="px-4 py-1 rounded text-xs font-bold text-white bg-blue-600 hover:bg-blue-500 shadow-lg shadow-blue-900/20 transition-all active:scale-95"
                >
                  적용
                </button>
              </>
            )}
          </div>
        </div>

        {/* Body */}
        <div
          ref={bodyRef}
          className={`flex-1 ${
            fitActive
              ? fitNeedsScroll
                ? 'overflow-auto'
                : 'overflow-hidden'
              : 'overflow-y-auto'
          } ${compact ? 'p-3' : 'p-4'} scrollbar-thin scrollbar-thumb-slate-700 scrollbar-track-transparent`}
        >
          <div
            ref={contentRef}
            className={fitActive ? 'mx-auto w-full max-w-full' : 'w-full'}
            style={
              fitActive && !fitNeedsScroll
                ? {
                    transform: `scale(${fitScale})`,
                    transformOrigin: 'top center',
                    width: '100%',
                    maxWidth: '100%',
                  }
                : undefined
            }
          >
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
                compact={compact}
                derived={derived}
              />
            ) : selUnit && localCfg ? (
              (() => {
                const u = selUnit.data as UnitData;
                const kind = u.kind as UnitKind;

                const updateCfg = (newCfg: UnitData['cfg']) =>
                  setLocalCfg(newCfg);

                if (kind === 'HRRO')
                  return (
                    <HRROEditor
                      node={{ ...u, cfg: localCfg as HRROConfig } as any}
                      onChange={updateCfg as unknown as (c: HRROConfig) => void}
                    />
                  );

                if (kind === 'RO')
                  return (
                    <ROEditor
                      node={{ ...u, cfg: localCfg as ROConfig } as any}
                      onChange={updateCfg as unknown as (c: ROConfig) => void}
                    />
                  );

                if (kind === 'UF')
                  return (
                    <UFEditor
                      node={{ ...u, cfg: localCfg as UFConfig } as any}
                      onChange={updateCfg as unknown as (c: UFConfig) => void}
                    />
                  );

                if (kind === 'NF')
                  return (
                    <NFEditor
                      node={{ ...u, cfg: localCfg as NFConfig } as any}
                      onChange={updateCfg as unknown as (c: NFConfig) => void}
                    />
                  );

                if (kind === 'MF')
                  return (
                    <MFEditor
                      node={{ ...u, cfg: localCfg as MFConfig } as any}
                      onChange={updateCfg as unknown as (c: MFConfig) => void}
                    />
                  );

                if (kind === 'PUMP')
                  return (
                    <PumpEditor
                      node={{ ...u, cfg: localCfg as PumpConfig } as any}
                      onChange={updateCfg as unknown as (c: PumpConfig) => void}
                    />
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
                <p className="text-sm font-medium">최종 생산수</p>
                <p className="text-xs">시뮬레이션 결과에서 확인</p>
              </div>
            ) : (
              <div className="text-sm text-slate-400">
                선택된 노드가 없습니다.
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
