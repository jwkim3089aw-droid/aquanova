#!/usr/bin/env python3
from __future__ import annotations

import re
import py_compile
from pathlib import Path

PRECISION_TOGGLE = r"""
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
""".strip() + "\n"


def backup(path: Path, suffix: str = ".v121b_before_v122.bak") -> None:
    if path.exists():
        b = path.with_suffix(path.suffix + suffix)
        if not b.exists():
            b.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")


def patch_toggle(root: Path) -> str:
    path = root / "ui/src/features/simulation/components/WaveCorrectionToggle.tsx"
    path.parent.mkdir(parents=True, exist_ok=True)
    backup(path)
    path.write_text(PRECISION_TOGGLE, encoding="utf-8")
    return f"PATCHED {path.relative_to(root)}"


def patch_app(root: Path) -> str:
    path = root / "ui/src/App.tsx"
    if not path.exists():
        return "SKIP App.tsx missing"
    backup(path)
    text = path.read_text(encoding="utf-8")
    text = text.replace("V121_WAVE_CORRECTION_TOGGLE", "V122_AQUANOVA_PRECISION_TOGGLE")
    path.write_text(text, encoding="utf-8")
    return f"PATCHED {path.relative_to(root)} marker only"


def patch_types(root: Path) -> str:
    path = root / "ui/src/api/types.ts"
    if not path.exists():
        return "SKIP ui/src/api/types.ts missing"
    backup(path)
    text = path.read_text(encoding="utf-8")

    text = text.replace("wave_correction_enabled?: boolean;", "precision_mode_enabled?: boolean;")
    text = text.replace("wave_correction_enabled?: boolean", "precision_mode_enabled?: boolean")
    text = text.replace("calibration_mode?: 'raw' | 'wave_opt_in' | string;", "engine_mode?: 'raw' | 'precision' | string;")
    text = text.replace("calibration_mode?: string;", "engine_mode?: string;")
    text = text.replace("wave_correction_report?:", "precision_report?:")
    text = text.replace("wave_correction_report?: ", "precision_report?: ")

    path.write_text(text, encoding="utf-8")
    return f"PATCHED {path.relative_to(root)}"


def patch_flow_runner(root: Path) -> str:
    path = root / "ui/src/features/simulation/hooks/flow/useFlowRunner.ts"
    if not path.exists():
        return "SKIP useFlowRunner.ts missing"
    backup(path)
    text = path.read_text(encoding="utf-8")

    # Rename frontend-facing helper/variables.
    replacements = {
        "isWaveCorrectionOptIn": "isPrecisionModeOptIn",
        "waveCorrectionEnabled": "precisionModeEnabled",
        "aquanova.waveCorrectionEnabled": "aquanova.precisionModeEnabled",
        "wave_correction_enabled": "precision_mode_enabled",
        "waveCorrection": "precisionMode",
        "wave_correction": "precision_mode",
        "wave_calibration": "precision_mode",
        "wave_opt_in": "precision",
    }
    for a, b in replacements.items():
        text = text.replace(a, b)

    # Make sure the helper supports the old localStorage key only as silent migration.
    if "aquanova.waveCorrectionEnabled" not in text and "aquanova.precisionModeEnabled" in text:
        marker = "window.localStorage.getItem('aquanova.precisionModeEnabled')"
        if marker in text:
            text = text.replace(
                marker,
                "(window.localStorage.getItem('aquanova.precisionModeEnabled') ?? window.localStorage.getItem('aquanova.waveCorrectionEnabled'))",
            )

    # Ensure payload uses public names if V120 format was slightly different.
    text = re.sub(r"calibration_mode\s*:\s*precisionModeEnabled\s*\?\s*['\"]precision['\"]\s*:\s*['\"]raw['\"]", "engine_mode: precisionModeEnabled ? 'precision' : 'raw'", text)
    if "precision_mode_enabled:" not in text and "const payload" in text:
        text = text.replace("project_id,", "project_id,\n      precision_mode_enabled: precisionModeEnabled,\n      engine_mode: precisionModeEnabled ? 'precision' : 'raw',", 1)

    path.write_text(text, encoding="utf-8")
    return f"PATCHED {path.relative_to(root)}"


def ensure_request_field(text: str, field_line: str, after_patterns: list[str]) -> str:
    field_name = field_line.split(":")[0].strip()
    if re.search(rf"\b{re.escape(field_name)}\s*:", text):
        return text
    for pat in after_patterns:
        m = re.search(pat, text)
        if m:
            insert = "\n    " + field_line
            return text[:m.end()] + insert + text[m.end():]
    # Fallback: insert near SimulationRequest class first non-empty indented area.
    m = re.search(r"class\s+SimulationRequest[^\n]*:\s*\n", text)
    if m:
        return text[:m.end()] + "    " + field_line + "\n" + text[m.end():]
    return text


def ensure_output_field(text: str, field_line: str, after_patterns: list[str]) -> str:
    field_name = field_line.split(":")[0].strip()
    if re.search(rf"\b{re.escape(field_name)}\s*:", text):
        return text
    for pat in after_patterns:
        m = re.search(pat, text)
        if m:
            return text[:m.end()] + "\n    " + field_line + text[m.end():]
    m = re.search(r"class\s+ScenarioOutput[^\n]*:\s*\n", text)
    if m:
        return text[:m.end()] + "    " + field_line + "\n" + text[m.end():]
    return text


def patch_schema(root: Path) -> str:
    path = root / "app/schemas/simulation.py"
    if not path.exists():
        return "SKIP app/schemas/simulation.py missing"
    backup(path)
    text = path.read_text(encoding="utf-8")

    # Make sure typing imports can support the new fields.
    if "Dict" not in text or "Any" not in text:
        text = text.replace("from typing import ", "from typing import Any, Dict, ", 1)

    text = ensure_request_field(
        text,
        "precision_mode_enabled: bool = False",
        [r"\n\s*wave_correction_enabled\s*:\s*bool\s*=\s*False"],
    )
    text = ensure_request_field(
        text,
        'engine_mode: Optional[str] = None',
        [r"\n\s*calibration_mode\s*:\s*Optional\[str\]\s*=\s*None", r"\n\s*precision_mode_enabled\s*:\s*bool\s*=\s*False"],
    )
    text = ensure_output_field(
        text,
        "precision_report: Optional[Dict[str, Any]] = None",
        [r"\n\s*wave_correction_report\s*:\s*Optional\[Dict\[str,\s*Any\]\]\s*=\s*None"],
    )

    path.write_text(text, encoding="utf-8")
    py_compile.compile(str(path), doraise=True)
    return f"PATCHED {path.relative_to(root)}"


def patch_endpoint(root: Path) -> str:
    path = root / "app/api/v1/endpoints/simulation.py"
    if not path.exists():
        return "SKIP app/api/v1/endpoints/simulation.py missing"
    backup(path)
    text = path.read_text(encoding="utf-8")

    # Broaden trigger condition while preserving internal correction engine call.
    text = text.replace(
        'getattr(request, "wave_correction_enabled", False)',
        '(getattr(request, "precision_mode_enabled", False) or getattr(request, "wave_correction_enabled", False))',
    )
    text = text.replace(
        "getattr(request, 'wave_correction_enabled', False)",
        "(getattr(request, 'precision_mode_enabled', False) or getattr(request, 'wave_correction_enabled', False))",
    )

    # Any mode checks should accept public precision labels.
    text = text.replace('"wave_opt_in"', '"wave_opt_in", "precision", "calibrated", "validated"')
    text = text.replace("'wave_opt_in'", "'wave_opt_in', 'precision', 'calibrated', 'validated'")

    # If endpoint reads calibration_mode only, let engine_mode alias feed it.
    if "engine_mode" not in text and "calibration_mode" in text:
        text = text.replace(
            'getattr(request, "calibration_mode", None)',
            '(getattr(request, "engine_mode", None) or getattr(request, "calibration_mode", None))',
        )
        text = text.replace(
            "getattr(request, 'calibration_mode', None)",
            "(getattr(request, 'engine_mode', None) or getattr(request, 'calibration_mode', None))",
        )

    # Public response name.
    text = text.replace("wave_correction_report", "precision_report")

    path.write_text(text, encoding="utf-8")
    py_compile.compile(str(path), doraise=True)
    return f"PATCHED {path.relative_to(root)}"


def patch_runtime_report_alias(root: Path) -> str:
    # Do not rename internal runtime helper; it remains a private validation bridge.
    # This intentionally only changes public API/UI names.
    return "OK internal validation helper names unchanged"


def main() -> int:
    root = Path.cwd().resolve()
    messages = [
        patch_toggle(root),
        patch_app(root),
        patch_types(root),
        patch_flow_runner(root),
        patch_schema(root),
        patch_endpoint(root),
        patch_runtime_report_alias(root),
    ]
    print("V122 AquaNova precision-mode rebrand patch applied")
    for msg in messages:
        print(msg)
    print()
    print("Public UI/API names now use AquaNova precision mode.")
    print("Internal validation/correction helper names remain private implementation details.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
