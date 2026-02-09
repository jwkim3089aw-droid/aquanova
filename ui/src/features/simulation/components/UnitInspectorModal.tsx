// ui/src/features/simulation/components/UnitInspectorModal.tsx
import React, { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { Node } from 'reactflow';

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

import {
  UnitData,
  FlowData,
  EndpointData,
  UnitKind,
  ChemistryInput,
  UnitMode,
  SetNodesFn,
  SetEdgesFn,
} from '../model/types';

import { updateUnitCfg } from '../model/logic';

import { useBlockDeleteKeysWhenOpen } from '../hooks/useBlockDeleteKeysWhenOpen';

import {
  ANIONS,
  CATIONS,
  NEUTRALS,
  MW,
  applyChargeBalance,
  type ChargeBalanceMode,
  fmtNumber,
  n0,
  roundTo,
  sumMeqL,
  sumMgL,
  mgL_to_meqL,
} from '../chemistry';

import { FeedInspectorBody, type FeedDerived } from './FeedInspectorBody';

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
    pressure_bar?: number;

    water_type?: string | null;
    water_subtype?: string | null;
    turbidity_ntu?: number | null;
    tss_mgL?: number | null;
    sdi15?: number | null;
    toc_mgL?: number | null;

    temp_min_C?: number | null;
    temp_max_C?: number | null;
    feed_note?: string | null;

    // (옵션) UI 설정 저장용
    charge_balance_mode?: ChargeBalanceMode | null;

    [k: string]: any;
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

  useBlockDeleteKeysWhenOpen(isOpen);

  const [localFeed, setLocalFeed] = useState<any>(feed);
  const [localChem, setLocalChem] = useState<any>(feedChemistry);
  const [localCfg, setLocalCfg] = useState<any>(null);

  const [quick, setQuick] = useState({ nacl_mgL: 0, mgso4_mgL: 0 });
  const [detailsOpen, setDetailsOpen] = useState(false);

  // “한 화면 맞춤” 모드
  const [fitMode, setFitMode] = useState(true);
  const [fitScale, setFitScale] = useState(1);

  // 글씨 너무 작아지는 문제 방지: minScale 이하로는 스크롤 허용
  const [fitNeedsScroll, setFitNeedsScroll] = useState(false);

  const bodyRef = useRef<HTMLDivElement | null>(null);
  const contentRef = useRef<HTMLDivElement | null>(null);

  // 전하 보정 모드 (WAVE)
  const [cbMode, setCbMode] = useState<ChargeBalanceMode>('anions');

  useEffect(() => {
    if (!isOpen) return;

    const minT = (feed as any)?.temp_min_C ?? feed.temperature_C;
    const maxT = (feed as any)?.temp_max_C ?? feed.temperature_C;

    setLocalFeed({
      ...feed,
      water_type: feed?.water_type == null ? '' : String(feed.water_type),
      water_subtype:
        feed?.water_subtype == null ? '' : String(feed.water_subtype),
      temp_min_C: minT,
      temp_max_C: maxT,
      feed_note: (feed as any)?.feed_note ?? '',
    });

    setLocalChem(feedChemistry || {});
    setQuick({ nacl_mgL: 0, mgso4_mgL: 0 });
    setDetailsOpen(false);

    const saved = (feed as any)?.charge_balance_mode as
      | ChargeBalanceMode
      | undefined;
    setCbMode(saved ?? 'anions');

    if (selUnit && (selUnit.data as any).type === 'unit') {
      setLocalCfg(JSON.parse(JSON.stringify((selUnit.data as any).cfg)));
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

  if (!isOpen || (!selEndpoint && !selUnit)) return null;

  const isFeedNode = selEndpoint?.data.role === 'feed';
  const isProductNode = selEndpoint?.data.role === 'product';

  // 전하 보정 적용 (KPI/Apply에 사용)
  const { chemUsed, meta: cbMeta } = applyChargeBalance(localChem, cbMode);

  // 원본 기준(참고용)
  const rawCationSum = sumMgL(localChem, CATIONS);
  const rawAnionSum = sumMgL(localChem, ANIONS);
  const rawNeutralSum = sumMgL(localChem, NEUTRALS);
  const rawTotalTDS = rawCationSum + rawAnionSum + rawNeutralSum;

  const rawCationMeq = sumMeqL(localChem, CATIONS);
  const rawAnionMeq = sumMeqL(localChem, ANIONS);
  const rawChargeBalance_meqL = rawCationMeq - rawAnionMeq;

  // 보정/사용 기준
  const cationSum = sumMgL(chemUsed, CATIONS);
  const anionSum = sumMgL(chemUsed, ANIONS);
  const neutralSum = sumMgL(chemUsed, NEUTRALS);
  const totalTDS = cationSum + anionSum + neutralSum;

  const cationMeq = sumMeqL(chemUsed, CATIONS);
  const anionMeq = sumMeqL(chemUsed, ANIONS);
  const chargeBalance_meqL = cationMeq - anionMeq;

  const ca_meq = mgL_to_meqL(n0(chemUsed?.ca_mgL), MW.Ca, +2);
  const mg_meq = mgL_to_meqL(n0(chemUsed?.mg_mgL), MW.Mg, +2);
  const calcHardness = (ca_meq + mg_meq) * 50.0;

  const hco3_meq = mgL_to_meqL(n0(chemUsed?.hco3_mgL), MW.HCO3, -1);
  const co3_meq = mgL_to_meqL(n0(chemUsed?.co3_mgL), MW.CO3, -2);
  const calcAlkalinity = (hco3_meq + co3_meq) * 50.0;

  const estConductivity_uScm = totalTDS * 1.7;

  const adjustmentText = (() => {
    const entries = Object.entries(cbMeta.adjustments_mgL);
    if (cbMode === 'off' || entries.length === 0) return '';
    const top = entries
      .sort((a, b) => Math.abs(b[1] as number) - Math.abs(a[1] as number))
      .slice(0, 4)
      .map(
        ([k, v]) =>
          `${k.replace('_mgL', '')} ${
            (v as number) > 0 ? '+' : ''
          }${fmtNumber(v as number, 3)} mg/L`,
      );
    return top.join(', ');
  })();

  const handleApply = () => {
    if (isFeedNode) {
      const chemForApply = cbMode === 'off' ? localChem : chemUsed;

      const chemOut = {
        ...chemForApply,
        alkalinity_mgL_as_CaCO3: calcAlkalinity,
        calcium_hardness_mgL_as_CaCO3: calcHardness,
      };

      setFeed({
        ...localFeed,
        tds_mgL: roundTo(totalTDS, 2),
        water_type: (localFeed.water_type ?? '') || null,
        water_subtype: (localFeed.water_subtype ?? '') || null,
        charge_balance_mode: cbMode,
      });
      setFeedChemistry(chemOut);
    } else if (selUnit && localCfg) {
      updateUnitCfg(selUnit.id, localCfg, setNodes);
    }
    onClose();
  };

  const compact = fitActive;

  const derived: FeedDerived = {
    totalTDS,
    rawTotalTDS,
    calcHardness,
    calcAlkalinity,
    estConductivity_uScm,
    chargeBalance_meqL,
    rawChargeBalance_meqL,
    cationMeq,
    anionMeq,
    rawCationMeq,
    rawAnionMeq,
    adjustmentText,
    cbNote: cbMeta.note,
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
          } ${
            compact ? 'p-3' : 'p-4'
          } scrollbar-thin scrollbar-thumb-slate-700 scrollbar-track-transparent`}
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
