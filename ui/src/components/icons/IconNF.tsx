import React from 'react';

interface FilterProps extends React.SVGProps<SVGSVGElement> {
  size?: number | string;
  color?: string;
  strokeWidth?: number;
}

export const NFIcon: React.FC<FilterProps> = ({
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
      <ellipse cx="12" cy="5" rx="4" ry="1.5" />
      <line x1="6" y1="8" x2="18" y2="26" strokeOpacity="0.8" />
      <line x1="18" y1="8" x2="6" y2="26" strokeOpacity="0.8" />
      <line x1="11" y1="8" x2="17" y2="18" strokeOpacity="0.8" />
      <line x1="13" y1="8" x2="7" y2="18" strokeOpacity="0.8" />
      <line x1="7" y1="18" x2="13" y2="27" strokeOpacity="0.8" />
      <line x1="17" y1="18" x2="11" y2="27" strokeOpacity="0.8" />
    </svg>
  );
};

// 이 부분이 추가되어야 에러가 해결됩니다.
export default NFIcon;