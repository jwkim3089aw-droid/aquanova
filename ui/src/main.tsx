// ui/src/main.tsx
import React, { ErrorInfo, ReactNode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import App from './App';
import { logger } from './utils/logger';
import './index.css';

// 화면의 #diag 요소에 텍스트를 추가하는 진단용 헬퍼 함수
function appendToDiag(s: string) {
  const d = document.getElementById('diag');
  if (d) d.textContent += '\n' + s;
}

interface ErrorBoundaryProps {
  children: ReactNode;
}

interface ErrorBoundaryState {
  error: Error | null;
}

class HardErrorBoundary extends React.Component<
  ErrorBoundaryProps,
  ErrorBoundaryState
> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    const errorMsg = error.stack || error.message || String(error);

    // 화면 진단 패널에 출력
    appendToDiag('[HardErrorBoundary] ' + errorMsg);
    if (info.componentStack)
      appendToDiag('[componentStack] ' + info.componentStack);

    // 콘솔 (및 추후 백엔드) 로깅 처리
    logger.error('[HardErrorBoundary] React Render Error', { error, info });
  }

  render() {
    if (this.state.error) {
      return (
        <div
          style={{
            padding: 16,
            background: '#fee2e2',
            border: '1px solid #fecaca',
            color: '#7f1d1d',
            borderRadius: 8,
          }}
        >
          <div style={{ fontWeight: 700, marginBottom: 8 }}>Render Error</div>
          <pre style={{ whiteSpace: 'pre-wrap' }}>
            {this.state.error.stack ||
              this.state.error.message ||
              String(this.state.error)}
          </pre>
        </div>
      );
    }
    return this.props.children;
  }
}

try {
  const rootEl = document.getElementById('root');
  if (!rootEl) throw new Error('#root not found');

  const root = createRoot(rootEl);

  root.render(
    <React.StrictMode>
      <HardErrorBoundary>
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </HardErrorBoundary>
    </React.StrictMode>,
  );

  appendToDiag('[ok] main.tsx mounted <App/>');
  logger.info('main.tsx mounted <App/>');
} catch (e: any) {
  const errorMsg = e?.stack || e?.message || String(e);

  appendToDiag('[fail] main.tsx render: ' + errorMsg);
  logger.error('main.tsx render failed', e);

  throw e;
}
