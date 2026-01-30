// ui/src/componetns/icons/IconPump.tsx
import React from "react";

export default function IconPump({ className }: { className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      {/* 간단한 펌프 심볼 (원 + 화살표 느낌) */}
      <circle cx="12" cy="12" r="9" />
      <path d="M12 12l6 4" />
      <path d="M12 12L6 8" />
      <path d="M12 3v9" />
    </svg>
  );
}