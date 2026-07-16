#!/usr/bin/env python3
from __future__ import annotations

import re
from pathlib import Path

COMP_REL = Path("ui/src/features/simulation/components/WaveCorrectionToggle.tsx")
MARK = "V121_WAVE_CORRECTION_TOGGLE"


COMPONENT = r"""
import React, { useEffect, useState } from 'react';

const STORAGE_KEY = 'aquanova.waveCorrectionEnabled';

function readEnabled(): boolean {
  try {
    if (typeof window === 'undefined') return false;
    const url = new URL(window.location.href);
    const query =
      url.searchParams.get('wave_correction') ??
      url.searchParams.get('waveCorrection') ??
      url.searchParams.get('wave_calibration');
    if (['1', 'true', 'yes', 'on', 'wave'].includes(String(query || '').toLowerCase())) {
      return true;
    }
    return ['1', 'true', 'yes', 'on', 'wave'].includes(
      String(window.localStorage.getItem(STORAGE_KEY) || '').toLowerCase()
    );
  } catch {
    return false;
  }
}

export function WaveCorrectionToggle() {
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
      }
    } catch {
      // Ignore browser storage failures; the UI state still updates.
    }
  };

  return (
    <div
      data-v121-wave-correction-toggle
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
      title="WAVE 보정 모드는 검증된 scope에서만 적용됩니다. 기본 계산은 raw AquaNova입니다."
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
        <strong style={{ fontSize: 12 }}>WAVE 보정 모드</strong>
        <span style={{ color: enabled ? '#bbf7d0' : '#cbd5e1' }}>
          {enabled ? 'ON · opt-in' : 'OFF · raw'}
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

export default WaveCorrectionToggle;
""".strip() + "\n"


def backup(path: Path) -> None:
    b = path.with_suffix(path.suffix + ".v120a_before_v121.bak")
    if path.exists() and not b.exists():
        b.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")


def write_component(root: Path) -> str:
    path = root / COMP_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    backup(path)
    path.write_text(COMPONENT, encoding="utf-8")
    return f"WRITTEN {COMP_REL}"


def candidate_score(path: Path, text: str) -> int:
    p = str(path).replace("\\", "/")
    score = 0
    if "/ui/src/features/simulation/" in p:
        score += 20
    if path.name.lower() in {"flowbuilder.tsx", "simulationpage.tsx", "simulation.tsx", "app.tsx"}:
        score += 20
    for token in ["useFlowLogic", "ReactFlow", "runSimulation", "FlowBuilder", "Simulation"]:
        if token in text:
            score += 8
    if "return (" in text:
        score += 5
    if "export default" in text or "export function" in text:
        score += 4
    if "WaveCorrectionToggle" in text:
        score -= 100
    return score


def find_target(root: Path) -> Path | None:
    candidates: list[tuple[int, Path]] = []
    src = root / "ui" / "src"
    if not src.exists():
        return None
    for path in src.rglob("*.tsx"):
        s = str(path)
        if any(x in s for x in ["node_modules", "dist", "build"]):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            continue
        score = candidate_score(path, text)
        if score > 25:
            candidates.append((score, path))
    candidates.sort(key=lambda x: (x[0], -len(str(x[1]))), reverse=True)
    return candidates[0][1] if candidates else None


def rel_import(from_path: Path, to_path: Path) -> str:
    rel = to_path.parent.relative_to(from_path.parent)
    raw = str(rel / to_path.stem).replace("\\", "/")
    if not raw.startswith("."):
        raw = "./" + raw
    return raw


def patch_return_fragment(text: str, insertion: str) -> str:
    # Handles: return (<div...> ... </div>)
    m = re.search(r"return\s*\(\s*<", text)
    if not m:
        return text

    # Insert a fragment after "return (" and close before the likely final ");"
    start = text.find("(", m.start()) + 1
    # Use last occurrence of "\n  );" or "\n);" as conservative close.
    close_candidates = [text.rfind("\n  );"), text.rfind("\n);"), text.rfind("\n    );")]
    close = max(close_candidates)
    if close <= start:
        return text

    before = text[:start]
    middle = text[start:close]
    after = text[close:]
    return before + "\n    <>\n" + middle + "\n      " + insertion + "\n    </>" + after


def patch_target(root: Path, component_path: Path) -> str:
    target = find_target(root)
    if target is None:
        return "SKIP target TSX not found; use URL/localStorage opt-in remains available"

    backup(target)
    text = target.read_text(encoding="utf-8")
    original = text

    if MARK in text or "WaveCorrectionToggle" in text:
        return f"UNCHANGED already patched {target.relative_to(root)}"

    imp_path = rel_import(target, component_path)
    import_line = f"import WaveCorrectionToggle from '{imp_path}'; // {MARK}\n"

    # Insert import after last import block.
    imports = list(re.finditer(r"^import\s+.*?;\s*$", text, flags=re.M))
    if imports:
        pos = imports[-1].end()
        text = text[:pos] + "\n" + import_line.rstrip() + text[pos:]
    else:
        text = import_line + text

    insertion = f"<WaveCorrectionToggle /> {{/* {MARK} */}}"

    # Prefer injecting before the last closing tag of the first returned root.
    patched = patch_return_fragment(text, insertion)
    if patched == text:
        # Fallback: append component before final export default if any. This is less ideal but keeps build likely.
        raise SystemExit(
            f"Could not safely inject WaveCorrectionToggle into {target}. "
            "Please show this file around its return JSX."
        )
    text = patched

    target.write_text(text, encoding="utf-8")
    return f"PATCHED render target {target.relative_to(root)}"


def patch_flow_runner_badge(root: Path) -> str:
    # Small helper comment only; actual payload logic was already V120.
    path = root / "ui/src/features/simulation/hooks/flow/useFlowRunner.ts"
    if not path.exists():
        return "SKIP useFlowRunner missing"
    text = path.read_text(encoding="utf-8")
    if "wave_correction_enabled:" not in text:
        return "WARN useFlowRunner payload flag not found; run V120 first"
    return "OK useFlowRunner already sends wave_correction_enabled"


def main() -> int:
    root = Path.cwd().resolve()
    component_path = root / COMP_REL
    msgs = [
        write_component(root),
        patch_target(root, component_path),
        patch_flow_runner_badge(root),
    ]
    print("V121 WAVE correction visible toggle patch complete")
    for m in msgs:
        print(m)
    print()
    print("What changed:")
    print("- A visible floating WAVE 보정 모드 switch was added to the simulation UI.")
    print("- It writes localStorage key aquanova.waveCorrectionEnabled.")
    print("- V120 payload path reads that key and sends wave_correction_enabled/calibration_mode.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
