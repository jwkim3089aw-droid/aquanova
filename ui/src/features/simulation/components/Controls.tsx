// ui/src/features/flow-builder/ui/components/Controls.tsx
import React from "react";
import {
  Play,
  Save,
  Upload,
  Link2,
  Focus,
  Loader2,
  Trash2,
} from "lucide-react";
import { UnitMode } from "../../model/types"; // 경로 주의

// ==============================
// Top toolbar
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
    <div className="rounded-2xl border border-slate-800 bg-slate-900/90 shadow-sm px-4 py-3 flex items-center justify-between">
      <div className="flex items-center gap-2 text-xs">
        <button
          onClick={onRun}
          disabled={running}
          className="
            min-w-[56px] h-8
            rounded-md border border-sky-500/70
            px-2 py-1
            bg-sky-900 text-white text-sm disabled:opacity-50 flex items-center gap-1
          "
          title="Run (Ctrl/Cmd+Enter)"
        >
          {running ? (
            <Loader2 className="w-3 h-3 animate-spin" />
          ) : (
            <Play className="w-3 h-3" />
          )}{" "}
          {running ? "Running..." : "Run"}
        </button>
        <button
          onClick={onAutoLink}
          className="
            min-w-[56px] h-8
            text-sm
            rounded-md border border-slate-700 px-2 py-1
            bg-slate-900/80 hover:bg-slate-800/80 flex items-center gap-1
          "
          title="x 위치 기준 자동 연결"
        >
          <Link2 className="w-3 h-3" /> Auto
        </button>
        <button
          onClick={onFit}
          className="
            text-sm
            min-w-[56px] h-8
            rounded-md border border-slate-700 px-2 py-1
            bg-slate-900/80 hover:bg-slate-800/80 flex items-center gap-1
          "
          title="Fit View"
        >
          <Focus className="w-3 h-3" /> Fit
        </button>
        <button
          onClick={onUndo}
          disabled={!canUndo}
          className="
            text-sm
            min-w-[56px] h-8
            rounded-md border border-slate-700 px-2 py-1
            bg-slate-900/80 disabled:opacity-40
          "
        >
          Undo
        </button>
        <button
          onClick={onRedo}
          disabled={!canRedo}
          className="
            text-sm
            min-w-[56px] h-8
            rounded-md border border-slate-700 px-2 py-1
            bg-slate-900/80 disabled:opacity-40
          "
        >
          Redo
        </button>
        <span className="mx-1 text-slate-700">|</span>
        <button
          onClick={onSave}
          className="
            text-sm
            min-w-[56px] h-8
            rounded-md border border-slate-700 px-2 py-1
            bg-slate-900/80 hover:bg-slate-800/80 flex items-center gap-1
          "
        >
          <Save className="w-3 h-3" />
          Save
        </button>
        <button
          onClick={onLoad}
          className="
            text-sm
            min-w-[56px] h-8
            rounded-md border border-slate-700 px-2 py-1
            bg-slate-900/80 hover:bg-slate-800/80 flex items-center gap-1
          "
        >
          <Upload className="w-3 h-3" />
          Load
        </button>
        <button
          onClick={onReset}
          className="
            text-sm
            min-w-[56px] h-8
            rounded-md border border-red-500/70 px-2 py-1
            text-red-200 bg-red-950/50 hover:bg-red-900/60
          "
        >
          Reset
        </button>
        {children}
      </div>
    </div>
  );
}

// ==============================
// Units toggle
// ==============================

export function UnitsToggle({
  mode,
  onChange,
}: {
  mode: UnitMode;
  onChange: (m: UnitMode) => void;
}) {
  const options: UnitMode[] = ["SI", "US"];
  return (
    <div className="inline-flex rounded-lg border border-slate-700 bg-slate-900 p-[2px] text-xs">
      {options.map((m) => (
        <button
          key={m}
          onClick={() => onChange(m)}
          className={`px-3 py-1 rounded-md ${
            mode === m
              ? "bg-sky-600 text-white"
              : "text-slate-300 hover:bg-slate-800"
          }`}
        >
          {m}
        </button>
      ))}
    </div>
  );
}

// ==============================
// Node action buttons (좌/우/삭제)
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
    <div className="flex items-center justify-end text-xs">
      <button
        onClick={onRemove}
        className="inline-flex items-center gap-1 rounded-md border border-red-600/70 bg-red-950 px-2 py-1 text-red-100 hover:bg-red-900"
      >
        <Trash2 className="w-3 h-3" />
        Remove
      </button>
    </div>
  );
}