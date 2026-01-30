// ui/src/components/nodes/IONode.tsx
import { memo } from 'react';
import { Handle, Position, type NodeProps } from 'reactflow';
import { HANDLE_STYLE } from '@/features/simulation/model/types';

type IOData = {
  kind?: 'FEED' | 'PRODUCT';
  role?: 'feed' | 'product';
  label?: string;
};

function IONode({ data }: NodeProps<IOData>) {
  // role이나 kind 중 하나라도 있으면 감지
  const kind = data?.kind ?? (data?.role === 'product' ? 'PRODUCT' : 'FEED');
  const label = data?.label ?? (kind === 'PRODUCT' ? 'Product' : 'Feed');

  const isProduct = kind === 'PRODUCT';

  // 스타일 정의
  const baseClasses =
    'relative inline-flex items-center rounded-full px-3 py-1 text-[12px] font-medium shadow-sm transition-all';

  const themeClasses = isProduct
    ? 'bg-sky-500/10 border border-sky-400/70 text-sky-100 shadow-sky-500/20'
    : 'bg-emerald-500/10 border border-emerald-400/70 text-emerald-100 shadow-emerald-500/20';

  const dotColor = isProduct ? '#38bdf8' : '#34d399'; // Sky vs Emerald

  return (
    <div className={`${baseClasses} ${themeClasses}`}>
      <span>{label}</span>

      {/* Product는 왼쪽(입력), Feed는 오른쪽(출력) 핸들 */}
      <Handle
        type={isProduct ? 'target' : 'source'}
        position={isProduct ? Position.Left : Position.Right}
        id={isProduct ? 'in' : 'out'}
        style={{
          ...HANDLE_STYLE,
          [isProduct ? 'left' : 'right']: -5,
          background: dotColor,
          borderColor: dotColor,
        }}
      />
    </div>
  );
}

export default memo(IONode);
