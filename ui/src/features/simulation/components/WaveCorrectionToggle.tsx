import React, { useEffect, useState } from 'react';

import {
  PRECISION_MODE_CHANGE_EVENT,
  readPrecisionModeEnabled,
  writePrecisionModeEnabled,
} from '../precisionMode';

export default function WaveCorrectionToggle() {
  const [enabled, setEnabled] = useState<boolean>(
    readPrecisionModeEnabled,
  );

  useEffect(() => {
    const sync = () => {
      setEnabled(readPrecisionModeEnabled());
    };

    window.addEventListener('storage', sync);
    window.addEventListener(
      PRECISION_MODE_CHANGE_EVENT,
      sync,
    );

    return () => {
      window.removeEventListener('storage', sync);
      window.removeEventListener(
        PRECISION_MODE_CHANGE_EVENT,
        sync,
      );
    };
  }, []);

  const toggle = () => {
    const next = !enabled;
    setEnabled(next);
    writePrecisionModeEnabled(next);
  };

  return (
    <div
      data-aquanova-precision-toggle
      data-testid="precision-mode-toggle"
      style={{
        position: 'fixed',
        right: 18,
        bottom: 18,
        zIndex: 9999,
        display: 'flex',
        alignItems: 'center',
        gap: 10,
        padding: '10px 12px',
        borderRadius: 12,
        border: '1px solid rgba(148, 163, 184, 0.5)',
        background: 'rgba(15, 23, 42, 0.92)',
        color: '#fff',
        boxShadow: '0 10px 25px rgba(15, 23, 42, 0.25)',
        fontSize: 12,
        lineHeight: 1.25,
        backdropFilter: 'blur(8px)',
      }}
      title="검증된 조건에서만 정밀 보정이 적용됩니다. 기본 계산은 AquaNova 물리 모델입니다."
    >
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          gap: 2,
        }}
      >
        <strong style={{ fontSize: 12 }}>
          AquaNova 정밀 모드
        </strong>

        <span
          data-testid="precision-mode-state"
          style={{
            color: enabled ? '#bbf7d0' : '#cbd5e1',
          }}
        >
          {enabled ? 'ON · 정밀' : 'OFF · 기본'}
        </span>
      </div>

      <button
        type="button"
        aria-label="AquaNova 정밀 모드"
        aria-pressed={enabled}
        data-testid="precision-mode-toggle-button"
        onClick={toggle}
        style={{
          width: 46,
          height: 24,
          borderRadius: 999,
          border: '1px solid rgba(255,255,255,0.25)',
          padding: 2,
          cursor: 'pointer',
          background: enabled ? '#16a34a' : '#475569',
          transition: 'background 120ms ease',
        }}
      >
        <span
          style={{
            display: 'block',
            width: 18,
            height: 18,
            borderRadius: '50%',
            background: '#fff',
            transform: enabled
              ? 'translateX(20px)'
              : 'translateX(0)',
            transition: 'transform 120ms ease',
          }}
        />
      </button>
    </div>
  );
}
