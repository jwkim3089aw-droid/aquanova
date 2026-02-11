// ui/src/features/simulation/components/Common.tsx
import React from 'react';

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

/**
 * ✅ 정석: 항상 "controlled input"으로 동작하게 value를 정규화
 * - undefined/null/NaN -> '' 로 바꿔 uncontrolled -> controlled 경고 제거
 * - type 기본값: "number"
 * - step 기본값: "any"
 */
function normalizeInputValue(v: unknown): string | number {
  if (v === null || v === undefined) return '';
  if (typeof v === 'number') return Number.isFinite(v) ? v : '';
  return v as any;
}

export const Input = React.forwardRef<
  HTMLInputElement,
  React.InputHTMLAttributes<HTMLInputElement>
>(function Input({ type, step, className = '', value, ...rest }, ref) {
  return (
    <input
      ref={ref}
      {...rest}
      type={type ?? 'number'}
      step={step ?? 'any'}
      value={normalizeInputValue(value)}
      className={[
        'w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm',
        'text-slate-100 placeholder:text-slate-500',
        'outline-none focus:ring-2 focus:ring-sky-500/40',
        className,
      ].join(' ')}
    />
  );
});
Input.displayName = 'Input';

// ==============================
// Error boundary
// ==============================

type ErrorBoundaryProps = { children: React.ReactNode };
type ErrorBoundaryState = { error: unknown };

export class ErrorBoundary extends React.Component<
  ErrorBoundaryProps,
  ErrorBoundaryState
> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error: unknown) {
    return { error };
  }

  override render() {
    if (this.state.error) {
      const msg =
        this.state.error instanceof Error
          ? this.state.error.message
          : String(this.state.error);

      return (
        <div className="p-4 m-4 border rounded-lg bg-red-950/60 border-red-700 text-sm text-red-100">
          <div className="font-semibold mb-1">UI 오류가 발생했습니다.</div>
          <pre className="whitespace-pre-wrap text-[11px]">{msg}</pre>
          <div className="text-[11px] text-red-300 mt-2">
            F12 콘솔에 스택이 표시됩니다.
          </div>
        </div>
      );
    }
    return this.props.children as any;
  }
}
