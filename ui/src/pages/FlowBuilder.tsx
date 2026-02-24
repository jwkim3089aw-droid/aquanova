// ui/src/pages/FlowBuilder.tsx

import React from 'react'; // [ADDED]
import FlowBuilderScreen from '@/features/simulation/FlowBuilderScreen'; // [CHANGED]

function FlowBuilderPage() {
  // [ADDED]
  return (
    // 뷰포트 전체 높이에 어두운 배경 적용
    <div className="min-h-screen bg-slate-950 text-slate-100 py-0">
      {' '}
      {/* [ADDED] */}
      <FlowBuilderScreen /> {/* [ADDED] */}
    </div>
  );
}

export default FlowBuilderPage; // [CHANGED]
