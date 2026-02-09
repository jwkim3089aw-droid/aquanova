// ui\src\main.tsx
// ui/src/main.tsx
import React from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import './index.css';

function log(s: string) {
  const d = document.getElementById('diag');
  if (d) d.textContent += '\n' + s;
  else console.log(s);
}

class HardErrorBoundary extends React.Component<
  { children: React.ReactNode },
  { error: any }
> {
  constructor(props: any) {
    super(props);
    this.state = { error: null };
  }
  static getDerivedStateFromError(error: any) {
    return { error };
  }
  componentDidCatch(error: any, info: any) {
    log(
      '[HardErrorBoundary] ' +
        (error?.stack || error?.message || String(error)),
    );
    if (info?.componentStack) log('[componentStack] ' + info.componentStack);
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
            {String(
              this.state.error?.stack ||
                this.state.error?.message ||
                this.state.error,
            )}
          </pre>
        </div>
      );
    }
    return this.props.children;
  }
}

import App from './App';

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

  log('[ok] main.tsx mounted <App/>');
} catch (e: any) {
  log('[fail] main.tsx render: ' + (e?.stack || e?.message || String(e)));
  throw e;
}
