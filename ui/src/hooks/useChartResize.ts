// ui\src\hooks\useChartResize.ts
import { useState, useEffect, useRef } from 'react';

/**
 * 부모 컨테이너(Div)의 크기 변화를 감지하여
 * 차트 라이브러리(Recharts 등)가 사용할 width, height를 실시간으로 반환합니다.
 */
export const useChartResize = () => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [dimensions, setDimensions] = useState({ width: 0, height: 0 });

  useEffect(() => {
    const element = containerRef.current;
    if (!element) return;

    const observer = new ResizeObserver((entries) => {
      // requestAnimationFrame으로 렌더링 사이클에 맞춰 부드럽게 업데이트
      window.requestAnimationFrame(() => {
        if (!Array.isArray(entries) || !entries.length) return;

        const entry = entries[0];
        const { width, height } = entry.contentRect;

        // 의미 있는 크기 변화가 있을 때만 상태 업데이트 (무한 렌더링 방지)
        if (width > 0 && height > 0) {
          setDimensions((prev) => {
            // 이전 크기와 동일하면 업데이트 스킵
            if (prev.width === width && prev.height === height) return prev;
            return { width, height };
          });
        }
      });
    });

    observer.observe(element);

    return () => {
      observer.disconnect();
    };
  }, []);

  return { containerRef, width, height };
};
