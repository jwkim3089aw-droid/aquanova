// ui/src/components/common/DetailedResultModal/index.tsx
import React, { useEffect, useMemo, useState, useCallback } from 'react';
import {
  X,
  Calculator,
  Globe,
  Layers,
  LayoutDashboard,
  FlaskConical,
  Waves,
  Clock,
  Activity,
  CircleDollarSign,
  ClipboardCheck,
} from 'lucide-react';

import { UnitMode } from '../../../features/simulation/model/types';
import { STYLES } from './constants';
import { SidebarBtn, TabBtn } from './SharedComponents';
import { SummaryTab } from './tabs/SummaryTab';
import { ProfileChartTab } from './tabs/ProfileChartTab';
import { ChemistryTab } from './tabs/ChemistryTab';
import { EnergyOpexTab } from './tabs/EnergyOpexTab';
import { AuditTab } from './tabs/AuditTab';

interface DetailedResultModalProps {
  isOpen: boolean;
  onClose: () => void;
  data: any;
  mode: 'SYSTEM' | 'STAGE';
  unitMode: UnitMode;
}

export function DetailedResultModal({
  isOpen,
  onClose,
  data,
}: DetailedResultModalProps) {
  const [selectedScope, setSelectedScope] = useState<'SYSTEM' | number>(
    'SYSTEM',
  );
  const [activeTab, setActiveTab] = useState<string>('summary');

  useEffect(() => {
    if (isOpen) {
      setSelectedScope('SYSTEM');
      setActiveTab('summary');
    }
  }, [isOpen]);

  const safeData = data || {};
  const kpi = safeData.kpi || {};
  const stages = safeData.stage_metrics || [];
  const economics = safeData.economics || null;
  const dosing = safeData.dosing || null;

  const currentData = useMemo(() => {
    return selectedScope === 'SYSTEM'
      ? { ...safeData, ...kpi }
      : stages[selectedScope] || {};
  }, [safeData, kpi, stages, selectedScope]);

  const isSystemView = selectedScope === 'SYSTEM';
  const isHRRO = currentData.module_type === 'HRRO';

  const currentChemistry = useMemo(() => {
    if (isSystemView) return safeData.chemistry || null;
    if (['UF', 'MF'].includes(currentData.module_type)) return null;
    return safeData.chemistry || null;
  }, [isSystemView, currentData.module_type, safeData.chemistry]);

  const chartData = useMemo(() => {
    if (!currentData) return [];
    if (
      isHRRO &&
      currentData.time_history &&
      Array.isArray(currentData.time_history)
    ) {
      return currentData.time_history.map((d: any) => ({
        ...d,
        flux_lmh: Number(d.flux_lmh ?? 0),
        pressure_bar: Number(d.pressure_bar ?? 0),
        recovery_pct: Number(d.recovery_pct ?? 0),
        time_min: Number(d.time_min ?? 0),
      }));
    }
    return currentData.element_profile || [];
  }, [currentData, isHRRO]);

  // 💡 [핵심 최적화 1] O(N) 탐색 방지 및 하위 컴포넌트 리렌더링 차단 (메모이제이션 프레임 고정)
  const streams = useMemo(() => {
    if (isSystemView) {
      return {
        feed: safeData.streams?.find((s: any) => s.label === 'Feed'),
        perm: safeData.streams?.find(
          (s: any) => s.label === 'Product' || s.label === 'Permeate',
        ),
        conc: safeData.streams?.find(
          (s: any) => s.label === 'Brine' || s.label === 'Concentrate',
        ),
      };
    } else {
      return {
        feed: {
          flow_m3h: currentData.Qf ?? currentData.gross_flow_m3h,
          tds_mgL: currentData.Cf ?? 0,
          pressure_bar: currentData.p_in_bar ?? 0,
        },
        perm: {
          flow_m3h: currentData.Qp ?? currentData.net_flow_m3h,
          tds_mgL: currentData.Cp ?? 0,
          pressure_bar: 0,
        },
        conc: {
          flow_m3h: currentData.Qc ?? currentData.backwash_loss_m3h,
          tds_mgL: currentData.Cc ?? 0,
          pressure_bar: currentData.p_out_bar ?? 0,
        },
      };
    }
  }, [isSystemView, safeData.streams, currentData]);

  const displayRecovery = currentData.recovery_pct ?? 0;
  const displayEnergy = currentData.sec_kwhm3 ?? 0;
  const displayFlux = currentData.flux_lmh ?? currentData.jw_avg_lmh ?? 0;
  const displayNDP = currentData.ndp_bar ?? 0;

  // 💡 [핵심 최적화 2] 렌더링마다 생성되는 인라인 함수 차단
  const handleTabChange = useCallback(
    (tabName: string) => () => setActiveTab(tabName),
    [],
  );
  const handleScopeChange = useCallback(
    (scope: 'SYSTEM' | number) => () => setSelectedScope(scope),
    [],
  );

  if (!isOpen || !data) return null;

  return (
    <div className={STYLES.OVERLAY}>
      <div className={STYLES.CONTAINER}>
        {/* HEADER */}
        <div className={STYLES.HEADER}>
          <div className="flex items-center gap-4">
            <div className="bg-gradient-to-br from-blue-600 to-indigo-700 p-2.5 rounded-lg text-white shadow-lg shadow-blue-900/20 ring-1 ring-white/10">
              <Calculator className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-bold text-slate-100 tracking-tight">
                공정 분석 및 상세 진단 (Process Analysis & Audit)
              </h2>
              <div className="flex items-center gap-2 text-[11px] text-slate-500 font-mono mt-0.5">
                <span className="bg-slate-800 px-1.5 rounded text-slate-400 border border-slate-700">
                  ID: {safeData.scenario_id?.slice(0, 8) || 'N/A'}
                </span>
                <span className="w-1 h-1 bg-slate-600 rounded-full mx-1" />
                <span
                  className={
                    isSystemView
                      ? 'text-blue-400 font-bold'
                      : 'text-emerald-400 font-bold'
                  }
                >
                  {isSystemView
                    ? '시스템 종합 요약 (System Overview)'
                    : `스테이지 ${Number(selectedScope) + 1} (${currentData.module_type})`}
                </span>
              </div>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-slate-800 rounded-lg text-slate-400 hover:text-white transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="flex flex-1 overflow-hidden">
          {/* SIDEBAR */}
          <div className={STYLES.SIDEBAR}>
            <div className="p-4 pt-6 pb-2 text-[10px] font-bold text-slate-500 uppercase tracking-wider flex items-center gap-2">
              <Globe className="w-3 h-3" /> 시스템 경계 (System Boundary)
            </div>
            <SidebarBtn
              active={selectedScope === 'SYSTEM'}
              onClick={handleScopeChange('SYSTEM')}
              icon={LayoutDashboard}
              label="전체 시스템 (Overall Plant)"
            />
            <div className="mt-6 mb-2 px-4 text-[10px] font-bold text-slate-500 uppercase tracking-wider flex items-center gap-2">
              <Layers className="w-3 h-3" /> 단위 공정 (Process Stages)
            </div>
            <div className="space-y-0.5 px-2">
              {stages.map((s: any, idx: number) => (
                <SidebarBtn
                  key={`${s.stage ?? idx}-${s.module_type ?? 'X'}`}
                  active={selectedScope === idx}
                  onClick={handleScopeChange(idx)}
                  icon={s.module_type === 'HRRO' ? Clock : Waves}
                  label={`스테이지 ${s.stage} (Stage ${s.stage})`}
                  badge={s.module_type}
                />
              ))}
            </div>
          </div>

          {/* CONTENT */}
          <div className={STYLES.CONTENT}>
            <div className={STYLES.TAB_BAR}>
              <TabBtn
                active={activeTab === 'summary'}
                onClick={handleTabChange('summary')}
                icon={Activity}
                label="요약 (Overview)"
              />
              <TabBtn
                active={activeTab === 'audit'}
                onClick={handleTabChange('audit')}
                icon={ClipboardCheck}
                label="설계 진단 (Design Audit)"
              />
              {!isSystemView && (isHRRO || chartData.length > 0) && (
                <TabBtn
                  active={activeTab === 'profile'}
                  onClick={handleTabChange('profile')}
                  icon={isHRRO ? Clock : Waves}
                  label={
                    isHRRO
                      ? '동적 사이클 (Dynamic Cycle)'
                      : '압력 프로파일 (Pressure Profile)'
                  }
                />
              )}
              <TabBtn
                active={activeTab === 'chemistry'}
                onClick={handleTabChange('chemistry')}
                icon={FlaskConical}
                label="수질 화학 (Chemistry)"
              />
              <TabBtn
                active={activeTab === 'power'}
                onClick={handleTabChange('power')}
                icon={CircleDollarSign}
                label="OPEX & 에너지 (Cost & Energy)"
              />
            </div>

            <div className={STYLES.SCROLL_AREA}>
              {activeTab === 'summary' && (
                <SummaryTab
                  isSystemView={isSystemView}
                  currentData={currentData}
                  feed={streams.feed}
                  perm={streams.perm}
                  conc={streams.conc}
                  stages={stages}
                  displayRecovery={displayRecovery}
                  displayEnergy={displayEnergy}
                  displayFlux={displayFlux}
                  displayNDP={displayNDP}
                  setSelectedScope={setSelectedScope}
                  isHRRO={isHRRO}
                />
              )}
              {activeTab === 'audit' && (
                <AuditTab
                  isSystemView={isSystemView}
                  currentData={currentData}
                  isHRRO={isHRRO}
                />
              )}
              {activeTab === 'profile' && !isSystemView && (
                <ProfileChartTab isHRRO={isHRRO} chartData={chartData} />
              )}
              {activeTab === 'chemistry' && (
                <ChemistryTab chemistry={currentChemistry} />
              )}
              {activeTab === 'power' && (
                <EnergyOpexTab
                  isSystemView={isSystemView}
                  economics={economics}
                  displayEnergy={displayEnergy}
                  dosing={dosing}
                />
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
