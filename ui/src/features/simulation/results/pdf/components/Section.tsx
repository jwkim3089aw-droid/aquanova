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
    // 🛑 [WAVE PATCH] 템플릿 렌더링 시 제목과 내용이 다른 페이지로 찢어지는 것을 방지
    <div className={`${THEME.SECTION} print:break-inside-avoid`}>
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
