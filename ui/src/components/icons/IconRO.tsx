import React from 'react';

interface FilterIconProps extends React.SVGProps<SVGSVGElement> {
  /** 아이콘의 크기 (기본값: 32 - 세로 비율이 길어져서 기본 크기를 조금 키웠습니다) */
  size?: number | string;
  /** 아이콘의 색상 (기본값: currentColor - 부모 요소의 글자색 상속) */
  color?: string;
  /** 선의 두께 (기본값: 1.5) */
  strokeWidth?: number;
}

export const FilterIcon: React.FC<FilterIconProps> = ({
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
      // viewBox를 "0 0 24 24"에서 "0 0 24 32"로 변경하여 세로 비율을 늘렸습니다.
      viewBox="0 0 24 32"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      stroke={color}
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      // preserveAspectRatio 설정을 추가하여 size가 정사각형이어도 아이콘 비율이 유지되게 합니다.
      preserveAspectRatio="xMidYMid meet"
      style={{ display: 'block', ...style }}
      {...props}
    >
      {/* 상단 바깥쪽 타원 (위치는 동일) */}
      <ellipse cx="12" cy="5" rx="9" ry="3" />
      
      {/* 상단 안쪽 구멍 (위치는 동일) */}
      <ellipse cx="12" cy="5" rx="4" ry="1.5" />
      
      {/* 몸통 옆면과 하단 곡선 (늘어난 높이에 맞춰 y좌표 수정) */}
      {/* V17 -> V25, 하단 곡선 제어점 및 끝점 y좌표도 그만큼 증가 */}
      <path d="M3 5V25C3 26.6569 7.02944 28 12 28C16.9706 28 21 26.6569 21 25V5" />
      
      {/* 수직 주름선들 (늘어난 높이에 맞춰 y2 좌표 수정) */}
      <line x1="6.5" y1="7.5" x2="6.5" y2="27.2" />
      <line x1="9.5" y1="8.2" x2="9.5" y2="27.8" />
      <line x1="14.5" y1="8.2" x2="14.5" y2="27.8" />
      <line x1="17.5" y1="7.5" x2="17.5" y2="27.2" />
    </svg>
  );
};

export default FilterIcon;