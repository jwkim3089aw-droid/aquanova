// ui/src/App.tsx
import { Routes, Route, Navigate } from 'react-router-dom';
import { Shell } from './components/Shell';
import Header from './components/layout/Header';
import FlowBuilderScreen from './features/simulation/FlowBuilderScreen';
import Reports from './pages/Reports';

export default function App() {
  return (
    // [핵심 최적화]
    // 1. h-screen: 화면 높이 100% 고정
    // 2. overflow-hidden: 브라우저 스크롤바 강제 제거 (내부 스크롤만 허용)
    <div className="h-screen w-screen bg-slate-950 text-slate-100 overflow-hidden flex flex-col">
      {/* 글로벌 헤더 (높이 고정) */}
      <div className="flex-none z-50">
        <Header />
      </div>

      {/* 메인 컨텐츠 (남은 공간 꽉 채움) */}
      <div className="flex-1 min-h-0 relative">
        <Shell active="builder">
          <main className="h-full w-full">
            <Routes>
              <Route path="/" element={<FlowBuilderScreen />} />
              <Route path="/reports" element={<Reports />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </main>
        </Shell>
      </div>
    </div>
  );
}
