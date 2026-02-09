// ui/src/components/charts/AutoSizedChart.tsx
import React, { useLayoutEffect, useRef, useState } from 'react';

type Props = {
  className?: string;
  minWidth?: number;
  minHeight?: number;
  children: (size: { width: number; height: number }) => React.ReactNode;
};

/**
 * ResizeObserver로 부모 컨테이너의 실제 px 크기를 측정해서
 * Recharts의 width/height를 직접 전달하는 안전한 래퍼.
 * (ResponsiveContainer width/height=-1 이슈 우회)
 */
export function AutoSizedChart({
  className,
  minWidth = 80,
  minHeight = 80,
  children,
}: Props) {
  const ref = useRef<HTMLDivElement | null>(null);
  const [size, setSize] = useState({ width: 0, height: 0 });

  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;

    const measure = () => {
      const r = el.getBoundingClientRect();
      const w = Math.floor(r.width);
      const h = Math.floor(r.height);
      if (w > 0 && h > 0) setSize({ width: w, height: h });
    };

    measure();

    const ro = new ResizeObserver(() => measure());
    ro.observe(el);

    return () => ro.disconnect();
  }, []);

  const ok = size.width >= minWidth && size.height >= minHeight;

  return (
    <div ref={ref} className={className}>
      {ok ? children(size) : null}
    </div>
  );
}
