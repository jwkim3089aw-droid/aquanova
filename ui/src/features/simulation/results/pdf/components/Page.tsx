// ui/src/features/simulation/results/pdf/components/Page.tsx
import React from 'react';
import { THEME } from '../theme';

export function Page({
  children,
  breakBefore,
}: {
  children: React.ReactNode;
  breakBefore?: boolean;
}) {
  return (
    <div
      // ✅ 수정: Flex column을 적용하여 바닥글을 맨 아래로 밀어낼 수 있도록 설정
      className={`${THEME.PAGE} flex flex-col`}
      style={breakBefore ? ({ pageBreakBefore: 'always' } as any) : undefined}
    >
      {/* 본문 영역: 남은 공간을 모두 차지 */}
      <div className="flex-grow">{children}</div>

      {/* ✅ 추가: 인쇄 시 페이지 하단에 항상 고정되는 공통 바닥글 */}
      <div className="pt-4 mt-8 border-t border-slate-200 flex justify-between items-center text-[9px] text-slate-400 font-mono print:mt-auto">
        <div>Aquanova Simulation Engine © {new Date().getFullYear()}</div>
        <div>Strictly Confidential</div>
      </div>
    </div>
  );
}
