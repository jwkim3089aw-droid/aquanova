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
      className={THEME.PAGE}
      style={breakBefore ? ({ pageBreakBefore: 'always' } as any) : undefined}
    >
      {children}
    </div>
  );
}
