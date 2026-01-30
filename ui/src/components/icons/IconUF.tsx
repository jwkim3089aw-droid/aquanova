import React from 'react';

interface FilterProps extends React.SVGProps<SVGSVGElement> {
  size?: number | string;
  color?: string;
  strokeWidth?: number;
}

export const UFIcon: React.FC<FilterProps> = ({
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
      <rect x="3" y="3" width="18" height="4" rx="1" />
      <rect x="3" y="25" width="18" height="4" rx="1" />
      <line x1="6" y1="7" x2="6" y2="25" />
      <line x1="9" y1="7" x2="9" y2="25" />
      <line x1="12" y1="7" x2="12" y2="25" />
      <line x1="15" y1="7" x2="15" y2="25" />
      <line x1="18" y1="7" x2="18" y2="25" />
    </svg>
  );
};

// 이 부분이 추가되어야 에러가 해결됩니다.
export default UFIcon;