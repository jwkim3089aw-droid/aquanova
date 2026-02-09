// ui\src\features\simulation\hooks\useBlockDeleteKeysWhenOpen.ts
import { useEffect } from 'react';

// 공통: 모달 열렸을 때 Delete/Backspace가 ReactFlow로 새는 걸 캡쳐 단계에서 차단
export function useBlockDeleteKeysWhenOpen(isOpen: boolean) {
  useEffect(() => {
    if (!isOpen) return;

    const handleKeyDownCapture = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement;

      // input/textarea에서는 정상 동작
      const tag = (target?.tagName || '').toUpperCase();
      if (tag === 'INPUT' || tag === 'TEXTAREA') return;

      if (e.key === 'Delete' || e.key === 'Backspace') {
        e.preventDefault();
        e.stopPropagation();
        e.stopImmediatePropagation();
      }
    };

    window.addEventListener('keydown', handleKeyDownCapture, true);
    return () =>
      window.removeEventListener('keydown', handleKeyDownCapture, true);
  }, [isOpen]);
}
