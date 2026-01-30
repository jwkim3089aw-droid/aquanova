import React from 'react';

interface HRROIconProps extends React.SVGProps<SVGSVGElement> {
  /** 아이콘의 크기 (기본값: 48) */
  size?: number | string;
  /** 아이콘의 색상 (기본값: currentColor) */
  color?: string;
  /** 선의 두께 (기본값: 1.5 - 필터 본체 기준) */
  strokeWidth?: number;
}

export const HRROIcon: React.FC<HRROIconProps> = ({
  size = 48,
  color = 'currentColor',
  strokeWidth = 1.5,
  style,
  ...props
}) => {
  // 화살표의 두께를 본체보다 2배 두껍게 설정
  const arrowStrokeWidth = strokeWidth * 2; 

  return (
    <svg
      width={size}
      height={size}
      viewBox="-14 -4 52 40"
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
      {/* === 기존 RO 필터 본체 (기본 두께 유지) === */}
      <g id="base-filter">
        <ellipse cx="12" cy="5" rx="9" ry="3" />
        <ellipse cx="12" cy="5" rx="4" ry="1.5" />
        <path d="M3 5V25C3 26.6569 7.02944 28 12 28C16.9706 28 21 26.6569 21 25V5" />
        <line x1="6.5" y1="7.5" x2="6.5" y2="27.2" />
        <line x1="9.5" y1="8.2" x2="9.5" y2="27.8" />
        <line x1="14.5" y1="8.2" x2="14.5" y2="27.8" />
        <line x1="17.5" y1="7.5" x2="17.5" y2="27.2" />
      </g>

      {/* === 대형 순환 화살표 (두께 2배 적용) === */}
      <g id="circulation-arrows" strokeWidth={arrowStrokeWidth}>
        {/* 왼쪽 화살표 */}
        <path d="M 7 -1 C -12 0, -12 32, 7 33" />
        <path d="M 3 30 L 7 33 L 3 36" />

        {/* 오른쪽 화살표 */}
        <path d="M 17 33 C 36 32, 36 0, 17 -1" />
        <path d="M 21 2 L 17 -1 L 21 -4" />
      </g>
    </svg>
  );
};

export default HRROIcon;