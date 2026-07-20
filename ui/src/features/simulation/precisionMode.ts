export const PRECISION_MODE_STORAGE_KEY =
  'aquanova.precisionModeEnabled';

export const LEGACY_PRECISION_MODE_STORAGE_KEYS = [
  'aquanova.waveCorrectionEnabled',
  'aquanova.precision_mode_enabled',
] as const;

export const PRECISION_MODE_CHANGE_EVENT =
  'aquanova:precision-mode-change';

const PRECISION_QUERY_KEYS = [
  'precision_mode',
  'precisionMode',
  'calibrated',
  'wave_correction',
  'waveCorrection',
  'wave_calibration',
] as const;

const TRUTHY_VALUES = new Set([
  '1',
  'true',
  'yes',
  'on',
  'precision',
  'calibrated',
  'wave',
]);

export function isPrecisionModeTruthy(
  value: string | null | undefined,
): boolean {
  return TRUTHY_VALUES.has(
    String(value ?? '')
      .trim()
      .toLowerCase(),
  );
}

export function readPrecisionModeEnabled(
  targetWindow?: Window,
): boolean {
  try {
    const browserWindow =
      targetWindow ??
      (typeof window !== 'undefined' ? window : undefined);

    if (!browserWindow) return false;

    const url = new URL(browserWindow.location.href);

    for (const key of PRECISION_QUERY_KEYS) {
      const value = url.searchParams.get(key);

      if (value !== null) {
        return isPrecisionModeTruthy(value);
      }
    }

    const current =
      browserWindow.localStorage.getItem(
        PRECISION_MODE_STORAGE_KEY,
      );

    if (current !== null) {
      return isPrecisionModeTruthy(current);
    }

    for (const key of LEGACY_PRECISION_MODE_STORAGE_KEYS) {
      const legacyValue =
        browserWindow.localStorage.getItem(key);

      if (legacyValue !== null) {
        return isPrecisionModeTruthy(legacyValue);
      }
    }

    return false;
  } catch {
    return false;
  }
}

export function writePrecisionModeEnabled(
  enabled: boolean,
  targetWindow?: Window,
): void {
  try {
    const browserWindow =
      targetWindow ??
      (typeof window !== 'undefined' ? window : undefined);

    if (!browserWindow) return;

    if (enabled) {
      browserWindow.localStorage.setItem(
        PRECISION_MODE_STORAGE_KEY,
        'true',
      );
    } else {
      browserWindow.localStorage.removeItem(
        PRECISION_MODE_STORAGE_KEY,
      );

      for (const key of LEGACY_PRECISION_MODE_STORAGE_KEYS) {
        browserWindow.localStorage.removeItem(key);
      }
    }

    browserWindow.dispatchEvent(
      new CustomEvent(PRECISION_MODE_CHANGE_EVENT, {
        detail: { enabled },
      }),
    );
  } catch {
    // Browser storage can be unavailable in private or restricted contexts.
  }
}
