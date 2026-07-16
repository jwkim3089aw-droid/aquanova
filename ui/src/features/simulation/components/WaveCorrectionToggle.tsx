import React, { useEffect, useState } from 'react';

const STORAGE_KEY = 'aquanova.precisionModeEnabled';
const LEGACY_STORAGE_KEY = 'aquanova.waveCorrectionEnabled';

function isTruthy(value: string | null | undefined): boolean {
  return ['1', 'true', 'yes', 'on', 'precision', 'calibrated'].includes(String(value || '').toLowerCase());
}

function readEnabled(): boolean {
  try {
    if (typeof window === 'undefined') return false;
    const url = new URL(window.location.href);
    const query =
      url.searchParams.get('precision_mode') ??
      url.searchParams.get('precisionMode') ??
      url.searchParams.get('calibrated') ??
      url.searchParams.get('wave_correction') ??
      url.searchParams.get('waveCorrection') ??
      url.searchParams.get('wave_calibration');

    if (isTruthy(query)) return true;

    const current = window.localStorage.getItem(STORAGE_KEY);
    if (current !== null) return isTruthy(current);

    return isTruthy(window.localStorage.getItem(LEGACY_STORAGE_KEY));
  } catch {
    return false;
  }
}

export default function WaveCorrectionToggle() {
  const [enabled, setEnabled] = useState<boolean>(readEnabled);

  useEffect(() => {
    try {
      const onStorage = () => setEnabled(readEnabled());
      window.addEventListener('storage', onStorage);
      return () => window.removeEventListener('storage', onStorage);
    } catch {
      return undefined;
    }
  }, []);

  const toggle = () => {
    const next = !enabled;
    setEnabled(next);
    try {
      if (next) {
        window.localStorage.setItem(STORAGE_KEY, 'true');
      } else {
        window.localStorage.removeItem(STORAGE_KEY);
        window.localStorage.removeItem(LEGACY_STORAGE_KEY);
      }
    } catch {
      // Ignore browser storage failures; the UI state still updates.
    }
  };

  return (
    <div
      data-aquanova-precision-toggle
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
      <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
        <strong style={{ fontSize: 12 }}>AquaNova 정밀 모드</strong>
        <span style={{ color: enabled ? '#bbf7d0' : '#cbd5e1' }}>
          {enabled ? 'ON · 정밀' : 'OFF · 기본'}
        </span>
      </div>

      <button
        type="button"
        aria-pressed={enabled}
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
            transform: enabled ? 'translateX(20px)' : 'translateX(0)',
            transition: 'transform 120ms ease',
          }}
        />
      </button>
    </div>
  );
}
