// ui/src/features/flow-builder/ui/components/Layout.tsx
import React from "react";
import { HelpCircle, Link2, Loader2 } from "lucide-react";

// ==============================
// Canvas helpers
// ==============================

export function EmptyCanvasHint({ onAutoLink }: { onAutoLink: () => void }) {
  return (
    <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
      <div className="pointer-events-auto rounded-xl border border-slate-700 bg-slate-900/90 px-4 py-3 text-xs text-slate-200 shadow">
        <div className="flex items-start gap-2">
          <HelpCircle className="w-4 h-4 mt-[2px] text-sky-400" />
          <div>
            <div className="font-medium mb-1">
              캔버스에 유닛을 드래그해서 시뮬을 구성하세요.
            </div>
            <div className="text-slate-400">
              Feed → RO/NF/UF/MF/HRRO → Product 순으로 연결하면 됩니다.
            </div>
            <button
              onClick={onAutoLink}
              className="mt-2 inline-flex items-center gap-1 rounded-md border border-slate-700 bg-slate-900 px-2 py-1 text-[11px] hover:bg-slate-800"
            >
              <Link2 className="w-3 h-3" />
              자동 연결
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export function LoadingOverlay() {
  return (
    <div className="absolute inset-0 z-20 flex items-center justify-center bg-slate-950/70">
      <div className="flex items-center gap-2 rounded-lg border border-slate-700 bg-slate-900 px-4 py-2 text-xs text-slate-100">
        <Loader2 className="w-4 h-4 animate-spin" />
        Running simulation...
      </div>
    </div>
  );
}

export function PaletteItemBig({
  label,
  icon,
  onDragStart,
}: {
  label: string;
  icon: React.ReactNode;
  onDragStart: (ev: React.DragEvent) => void;
}) {
  return (
    <div
      draggable
      onDragStart={onDragStart}
      className="
        inline-flex items-center gap-2 rounded-xl
        border border-slate-700 bg-slate-900
        px-2 py-1
        text-xs text-slate-100
        shadow-sm cursor-grab active:cursor-grabbing hover:bg-slate-800
      "
    >
      <div className="p-1.5 rounded-lg bg-slate-800 text-sky-300">
        {icon}
      </div>
      <span>{label}</span>
    </div>
  );
}