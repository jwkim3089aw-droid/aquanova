// ui\src\App.tsx
// ui/src/App.tsx
import { Routes, Route, Navigate } from 'react-router-dom';
import { Shell } from './components/Shell';
import Header from './components/layout/Header';
import FlowBuilderScreen from './features/simulation/FlowBuilderScreen';
import Reports from './pages/Reports';

export default function App() {
  return (
    <div className="h-screen w-screen bg-slate-950 text-slate-100 overflow-hidden flex flex-col">
      <div className="flex-none z-50">
        <Header />
      </div>

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
