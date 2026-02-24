// ui/src/features/simulation/FlowBuilderScreen.tsx
import React, { useCallback, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import ReactFlow, {
  Background,
  Controls,
  ReactFlowProvider,
  NodeChange,
} from 'reactflow';
import 'reactflow/dist/style.css';

import {
  nodeTypes,
  TopBar,
  UnitsToggle,
  LoadingOverlay,
  PaletteItemBig,
  ErrorBoundary,
} from '.';
import Footer from '@/components/Footer';

import IconRO from '@/components/icons/IconRO';
import IconHRRO from '@/components/icons/IconHRRO';
import IconUF from '@/components/icons/IconUF';
import IconMF from '@/components/icons/IconMF';
import IconNF from '@/components/icons/IconNF';

import { autoLinkLinear } from './model/logic';
import { SetEdgesFn, SetNodesFn } from './model/types';
import { useFlowLogic } from './hooks/useFlowLogic';

import {
  UnitInspectorModal,
  GlobalOptionsModal,
} from '@/features/simulation/components/FlowModals';

// 🛑 [WAVE PATCH] 방금 우리가 화려하게 업그레이드한 대시보드를 임포트합니다!
import { Visualization } from './results/Visualization';

import { AlertOctagon } from 'lucide-react';

const DELETE_KEYS = ['Backspace', 'Delete'] as const;

function FlowBuilderInner() {
  const navigate = useNavigate();
  const logic = useFlowLogic();

  const {
    rfRef,
    unitMode,
    scenarioName,
    setScenarioName,
    feed,
    setFeed,
    feedChemistry,
    setFeedChemistry,
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
    nodes,
    onNodesChange,
    edges,
    onEdgesChange,
    setEdges,
    loading,
    err,
    data,
    HRRO, // fallback
    editorOpen,
    setEditorOpen,
    optionsOpen,
    setOptionsOpen,
    toast,
    canUndo,
    canRedo,
    selEndpoint,
    selUnit,
    stageTypeHint,
    pushToast,
    undo,
    redo,
    onDragStartPalette,
    onDragOver,
    onDrop,
    onConnect,
    onNodeDragStop,
    onEdgesDelete,
    toggleUnits,
    onRun,
    saveLocal,
    loadLocal,
    saveToLibrary,
    resetAll,
    setNodes,
    setSelectedNodeId,
  } = logic;

  const isModalOpen = editorOpen || optionsOpen;
  const resultForViz = useMemo(() => data ?? HRRO, [data, HRRO]);

  const handleNodesChange = useCallback(
    (changes: NodeChange[]) => {
      const filtered = changes.filter((change) => {
        if (change.type !== 'remove') return true;

        const target = nodes.find((n) => n.id === change.id);
        const role = (target?.data as any)?.role;

        if (role === 'feed' || role === 'product') {
          pushToast('🚫 필수 노드(원수/생산수)는 삭제할 수 없습니다.');
          return false;
        }
        return true;
      });

      onNodesChange(filtered);
    },
    [nodes, onNodesChange, pushToast],
  );

  return (
    <div className="flex flex-col w-full h-full bg-slate-950 text-slate-100 font-sans text-xs overflow-hidden">
      {/* Top Toolbar */}
      <div className="flex-none z-30 px-3 py-2 bg-slate-950 border-b border-slate-800">
        <TopBar
          onRun={onRun}
          onAutoLink={() => {
            autoLinkLinear(nodes, setEdges as SetEdgesFn);
            pushToast('자동 연결 완료');
          }}
          onFit={() => rfRef.current?.fitView?.({ padding: 0.2 })}
          onUndo={undo}
          canUndo={canUndo}
          onRedo={redo}
          canRedo={canRedo}
          onSave={saveLocal}
          onLoad={loadLocal}
          onReset={resetAll}
          running={loading}
        >
          <div className="flex items-center gap-2">
            <UnitsToggle mode={unitMode} onChange={toggleUnits} />

            <div className="h-4 w-px bg-slate-800 mx-1" />

            <div className="flex items-center gap-1.5">
              <input
                value={scenarioName}
                onChange={(e) => setScenarioName(e.target.value)}
                className="h-8 rounded border border-slate-700 bg-slate-900 px-2 text-xs w-40 text-slate-100 focus:border-sky-500 outline-none"
                placeholder="시나리오 이름"
              />
              <button
                onClick={saveToLibrary}
                className="h-8 rounded border border-slate-700 bg-slate-800 px-3 text-xs hover:bg-slate-700 text-slate-300"
              >
                저장
              </button>
            </div>

            <button
              onClick={() => setOptionsOpen(true)}
              className="h-8 px-3 rounded border border-slate-700 bg-slate-800 text-xs text-slate-300 hover:bg-slate-700 ml-1"
            >
              옵션
            </button>
          </div>
        </TopBar>
      </div>

      {/* Main Workspace */}
      <div className="flex-1 flex min-h-0 p-2 gap-2">
        {/* Flow Canvas (좌측/중앙) */}
        <div className="flex-1 flex flex-col overflow-hidden rounded border border-slate-800 bg-slate-950 shadow-sm relative">
          <div className="flex-none px-3 min-h-[44px] py-1 border-b border-slate-800 bg-slate-900/50 flex items-center justify-between z-10">
            <div className="flex items-center gap-3">
              <span className="text-xs font-bold text-slate-300 flex items-center gap-1.5 tracking-wider">
                <span className="w-1.5 h-1.5 rounded-full bg-blue-500 shadow-[0_0_5px_rgba(59,130,246,0.5)]" />
                공정 흐름도
              </span>

              <div className="h-3 w-px bg-slate-700" />

              <div className="flex items-center gap-1">
                <PaletteItemBig
                  label="RO"
                  icon={<IconRO className="w-4 h-4" />}
                  onDragStart={(e) => onDragStartPalette('RO', e)}
                />
                <PaletteItemBig
                  label="HRRO"
                  icon={<IconHRRO className="w-4 h-4" />}
                  onDragStart={(e) => onDragStartPalette('HRRO', e)}
                />
                <PaletteItemBig
                  label="UF"
                  icon={<IconUF className="w-4 h-4" />}
                  onDragStart={(e) => onDragStartPalette('UF', e)}
                />
                <PaletteItemBig
                  label="NF"
                  icon={<IconNF className="w-4 h-4" />}
                  onDragStart={(e) => onDragStartPalette('NF', e)}
                />
                <PaletteItemBig
                  label="MF"
                  icon={<IconMF className="w-4 h-4" />}
                  onDragStart={(e) => onDragStartPalette('MF', e)}
                />
              </div>
            </div>
          </div>

          <div className="flex-1 relative bg-slate-950 min-h-0">
            <ReactFlow
              className="bg-slate-950 h-full w-full"
              nodeTypes={nodeTypes}
              nodes={nodes}
              edges={edges}
              onNodesChange={handleNodesChange}
              onEdgesChange={onEdgesChange}
              onConnect={onConnect}
              deleteKeyCode={isModalOpen ? null : (DELETE_KEYS as any)}
              onNodeClick={(_, node) => setSelectedNodeId(node.id)}
              onNodeDoubleClick={(_, node) => {
                setSelectedNodeId(node.id);
                setEditorOpen(true);
              }}
              onDrop={onDrop}
              onDragOver={onDragOver}
              onInit={(inst) => {
                rfRef.current = inst;
              }}
              onNodeDragStop={onNodeDragStop}
              onEdgesDelete={onEdgesDelete}
              onPaneClick={() => {
                setSelectedNodeId(null);
                setEditorOpen(false);
              }}
              fitView
              minZoom={0.1}
              maxZoom={2.0}
              proOptions={{ hideAttribution: true }}
            >
              <Background
                color="#1e293b"
                gap={20}
                size={1}
                className="opacity-30"
              />
              <Controls
                className="!bg-slate-900 !border-slate-700 !shadow-sm !text-slate-400 scale-90 origin-bottom-left"
                showInteractive={false}
              />
            </ReactFlow>
            {loading && <LoadingOverlay />}
          </div>
        </div>

        {/* 🛑 [WAVE PATCH] Result Panel (우측 대시보드 뷰 복구!) */}
        <div className="flex-none w-[450px] flex flex-col overflow-hidden rounded border border-slate-800 bg-slate-900/20 shadow-sm relative">
          {/* 로딩 오버레이 */}
          {loading && <LoadingOverlay />}

          {/* 에러 오버레이 */}
          {err && (
            <div className="absolute inset-0 z-20 bg-slate-950/80 p-4 flex flex-col items-center justify-center text-center backdrop-blur-sm">
              <AlertOctagon className="w-8 h-8 text-rose-500 mb-2" />
              <div className="text-rose-400 font-bold mb-1">
                Simulation Error
              </div>
              <div className="text-[10px] text-rose-200/70 overflow-auto max-h-40 p-2 bg-rose-950/50 rounded border border-rose-900/50">
                {err}
              </div>
            </div>
          )}

          {/* 방금 만든 진짜 대시보드 컴포넌트 렌더링! */}
          <Visualization result={resultForViz} unitMode={unitMode} />
        </div>
      </div>

      <Footer />

      <UnitInspectorModal
        isOpen={editorOpen}
        onClose={() => setEditorOpen(false)}
        selEndpoint={selEndpoint}
        selUnit={selUnit}
        feed={feed}
        setFeed={setFeed}
        feedChemistry={feedChemistry}
        setFeedChemistry={setFeedChemistry}
        unitMode={unitMode}
        setNodes={setNodes as SetNodesFn}
        setEdges={setEdges as SetEdgesFn}
        setSelectedNodeId={setSelectedNodeId}
      />

      <GlobalOptionsModal
        isOpen={optionsOpen}
        onClose={() => setOptionsOpen(false)}
        optAuto={optAuto}
        setOptAuto={setOptAuto}
        optMembrane={optMembrane}
        setOptMembrane={setOptMembrane}
        optSegments={optSegments}
        setOptSegments={setOptSegments}
        optPumpEff={optPumpEff}
        setOptPumpEff={setOptPumpEff}
        optErdEff={optErdEff}
        setOptErdEff={setOptErdEff}
        stageTypeHint={stageTypeHint}
      />

      {toast && (
        <div className="fixed bottom-12 right-6 z-[100] rounded bg-slate-800/95 border border-slate-600 text-slate-100 text-xs px-3 py-2 shadow-2xl flex items-center gap-2 animate-in fade-in slide-in-from-bottom-2">
          {toast}
        </div>
      )}
    </div>
  );
}

export default function FlowBuilderScreen() {
  return (
    <ReactFlowProvider>
      <ErrorBoundary>
        <FlowBuilderInner />
      </ErrorBoundary>
    </ReactFlowProvider>
  );
}
