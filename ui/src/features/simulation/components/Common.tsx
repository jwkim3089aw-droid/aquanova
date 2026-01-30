// ui/src/features/flow-builder/ui/components/Common.tsx
import React from "react";

// ==============================
// Generic Field / Input
// ==============================

export function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <label className="grid gap-1 text-xs text-slate-300">
      <span>{label}</span>
      {children}
    </label>
  );
}

export function Input(props: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      {...props}
      type={props.type ?? "number"}
      step={props.step ?? "any"}
      className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm
                 text-slate-100 placeholder:text-slate-500
                 outline-none focus:ring-2 focus:ring-sky-500/40"
    />
  );
}

// ==============================
// Error boundary
// ==============================

export class ErrorBoundary extends React.Component<
  { children: React.ReactNode },
  { error: any }
> {
  constructor(props: any) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error: any) {
    return { error };
  }

  override render() {
    if (this.state.error) {
      return (
        <div className="p-4 m-4 border rounded-lg bg-red-950/60 border-red-700 text-sm text-red-100">
          <div className="font-semibold mb-1">UI 오류가 발생했습니다.</div>
          <pre className="whitespace-pre-wrap text-[11px]">
            {String(this.state.error?.message || this.state.error)}
          </pre>
          <div className="text-[11px] text-red-300 mt-2">
            F12 콘솔에 스택이 표시됩니다.
          </div>
        </div>
      );
    }
    return this.props.children as any;
  }
}