// ui/src/features/simulation/results/pdf/components/Section.tsx
import React from 'react';
import { THEME } from '../theme';

export function Section({
  title,
  icon,
  right,
  children,
}: {
  title: string;
  icon?: React.ReactNode;
  right?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div className={THEME.SECTION}>
      <div className={THEME.SECTION_HEAD}>
        <div className={THEME.SECTION_TITLE}>
          {icon}
          {title}
        </div>
        <div className="flex items-center gap-2">{right}</div>
      </div>
      <div className={THEME.SECTION_BODY}>{children}</div>
    </div>
  );
}
