// ui/src/features/flow-builder/ui/components/Controls.tsx
import React from 'react';
import {
  Play,
  Save,
  Upload,
  Link2,
  Focus,
  Loader2,
  Trash2,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react';
import { UnitMode } from '../../model/types'; // 경로 주의

// ==============================
// 공통 툴바 버튼 컴포넌트 (리팩토링)
// ==============================

interface ToolbarButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'default' | 'primary' | 'danger';
}

function ToolbarButton({
  variant = 'default',
  className = '',
  children,
  ...props
}: ToolbarButtonProps) {
  const baseStyles =
    'min-w-[56px] h-8 text-sm rounded-md border px-2 py-1 flex items-center justify-center gap-1 transition-colors disabled:opacity-50 disabled:cursor-not-allowed';

  const variants = {
    primary: 'border-sky-500/70 bg-sky-900 text-white hover:bg-sky-800',
    default:
      'border-slate-700 bg-slate-900/80 text-slate-200 hover:bg-slate-800/80',
    danger: 'border-red-500/70 text-red-200 bg-red-950/50 hover:bg-red-900/60',
  };

  return (
    <button
      className={`${baseStyles} ${variants[variant]} ${className}`}
      {...props}
    >
      {children}
    </button>
  );
}

// ==============================
// 상단 툴바 (Top toolbar)
// ==============================

export function TopBar(props: {
  onRun: () => void;
  onAutoLink: () => void;
  onFit: () => void;
  onUndo: () => void;
  onRedo: () => void;
  onSave: () => void;
  onLoad: () => void;
  onReset: () => void;
  running: boolean;
  canUndo: boolean;
  canRedo: boolean;
  children?: React.ReactNode;
}) {
  const {
    onRun,
    onAutoLink,
    onFit,
    onUndo,
    onRedo,
    onSave,
    onLoad,
    onReset,
    running,
    canUndo,
    canRedo,
    children,
  } = props;

  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900/90 shadow-sm px-4 py-2.5 flex items-center w-full">
      <div className="flex items-center gap-1.5 text-xs flex-nowrap">
        {/* 1. 실행 버튼 (가장 누르기 편한 맨 왼쪽!) */}
        <ToolbarButton
          variant="primary"
          onClick={onRun}
          disabled={running}
          title="시뮬레이션 실행 (Ctrl/Cmd+Enter)"
          className="mr-1 px-3"
        >
          {running ? (
            <Loader2 className="w-3 h-3 animate-spin" />
          ) : (
            <Play className="w-3 h-3 fill-current" />
          )}
          {running ? '실행 중...' : '실행'}
        </ToolbarButton>

        {/* 2. 뷰 제어 */}
        <ToolbarButton onClick={onAutoLink} title="자동 연결">
          <Link2 className="w-3 h-3" />
          자동 연결
        </ToolbarButton>
        <ToolbarButton onClick={onFit} title="화면 맞춤">
          <Focus className="w-3 h-3" />
          화면 맞춤
        </ToolbarButton>

        <span className="mx-1.5 text-slate-700">|</span>

        {/* 3. 편집 */}
        <ToolbarButton onClick={onUndo} disabled={!canUndo}>
          실행 취소
        </ToolbarButton>
        <ToolbarButton onClick={onRedo} disabled={!canRedo}>
          다시 실행
        </ToolbarButton>

        <span className="mx-1.5 text-slate-700">|</span>

        {/* 4. 저장/불러오기 */}
        <ToolbarButton onClick={onSave} title="현재 워크플로우 저장">
          <Save className="w-3 h-3" />
          저장
        </ToolbarButton>
        <ToolbarButton onClick={onLoad} title="저장된 워크플로우 불러오기">
          <Upload className="w-3 h-3" />
          불러오기
        </ToolbarButton>

        <span className="mx-1.5 text-slate-700">|</span>

        {/* 5. 초기화 */}
        <ToolbarButton
          variant="danger"
          onClick={onReset}
          title="모든 노드 초기화"
        >
          초기화
        </ToolbarButton>

        <span className="mx-1.5 text-slate-700">|</span>

        {/* 6. 단위 및 옵션 (children) */}
        {children}
      </div>
    </div>
  );
}

// ==============================
// 단위 전환 (Units toggle)
// ==============================

export function UnitsToggle({
  mode,
  onChange,
}: {
  mode: UnitMode;
  onChange: (m: UnitMode) => void;
}) {
  const options: UnitMode[] = ['SI', 'US'];
  return (
    <div className="inline-flex rounded-lg border border-slate-700 bg-slate-900 p-[2px] text-xs">
      {options.map((m) => (
        <button
          key={m}
          onClick={() => onChange(m)}
          title={`${m} 단위로 변경`}
          className={`px-3 py-1 rounded-md transition-colors ${
            mode === m
              ? 'bg-sky-600 text-white'
              : 'text-slate-300 hover:bg-slate-800'
          }`}
        >
          {m}
        </button>
      ))}
    </div>
  );
}

// ==============================
// 노드 액션 버튼 (좌/우/삭제)
// ==============================

export function ActionButtons({
  onLeft,
  onRight,
  onRemove,
}: {
  onLeft?: () => void;
  onRight?: () => void;
  onRemove: () => void;
}) {
  return (
    <div className="flex items-center justify-end text-xs gap-1">
      {/* onLeft가 전달되었을 때만 렌더링 */}
      {onLeft && (
        <button
          onClick={onLeft}
          title="좌측으로 이동"
          className="p-1.5 rounded-md border border-slate-700 bg-slate-900/80 text-slate-300 hover:bg-slate-800"
        >
          <ChevronLeft className="w-3 h-3" />
        </button>
      )}

      {/* onRight가 전달되었을 때만 렌더링 */}
      {onRight && (
        <button
          onClick={onRight}
          title="우측으로 이동"
          className="p-1.5 rounded-md border border-slate-700 bg-slate-900/80 text-slate-300 hover:bg-slate-800"
        >
          <ChevronRight className="w-3 h-3" />
        </button>
      )}

      {/* 삭제 버튼 */}
      <button
        onClick={onRemove}
        title="노드 삭제"
        className="inline-flex items-center gap-1 rounded-md border border-red-600/70 bg-red-950 px-2 py-1.5 text-red-100 hover:bg-red-900 transition-colors"
      >
        <Trash2 className="w-3 h-3" />
        삭제
      </button>
    </div>
  );
}
