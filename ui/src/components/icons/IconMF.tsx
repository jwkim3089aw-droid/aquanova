// ui/src/components/icons/IconMF.tsx
import React from 'react';

interface FilterProps extends React.SVGProps<SVGSVGElement> {
  size?: number | string;
  color?: string;
  strokeWidth?: number;
}

export const MFIcon: React.FC<FilterProps> = ({
  size = 32,
  color = 'currentColor',
  strokeWidth = 1.5,
  style,
  ...props
}) => {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 32"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      stroke={color}
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      preserveAspectRatio="xMidYMid meet"
      style={{ display: 'block', ...style }}
      {...props}
    >
      <ellipse cx="12" cy="5" rx="9" ry="3" />
      <path d="M3 5V25C3 26.6569 7.02944 28 12 28C16.9706 28 21 26.6569 21 25V5" />
      <ellipse cx="12" cy="5" rx="3" ry="1" />
      <path d="M6 8 L7 24" />
      <path d="M9 8 L8 24" />
      <path d="M12 8 L13 24" />
      <path d="M15 8 L14 24" />
      <path d="M18 8 L19 24" />
      <path d="M3 10 C 5 11, 7 10, 9 11" strokeOpacity="0.5" />
      <path d="M15 11 C 17 10, 19 11, 21 10" strokeOpacity="0.5" />
    </svg>
  );
};

// 이 부분이 추가되어야 에러가 해결됩니다.
export default MFIcon;