#!/usr/bin/env python3
from __future__ import annotations

import re
from pathlib import Path

MARK = "V121_WAVE_CORRECTION_TOGGLE"
COMP_REL = Path("ui/src/features/simulation/components/WaveCorrectionToggle.tsx")


def _backup(path: Path, suffix: str = ".v121_before_v121a.bak") -> None:
    b = path.with_suffix(path.suffix + suffix)
    if path.exists() and not b.exists():
        b.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")


def restore_broken_v121_injections(root: Path) -> list[str]:
    msgs: list[str] = []
    src = root / "ui" / "src"
    if not src.exists():
        return ["SKIP ui/src missing"]

    for path in src.rglob("*.tsx"):
        if path == root / COMP_REL:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            continue
        if MARK not in text and "WaveCorrectionToggle" not in text:
            continue

        # V121 made backups with this suffix.
        backup = path.with_suffix(path.suffix + ".v120a_before_v121.bak")
        if backup.exists():
            path.write_text(backup.read_text(encoding="utf-8"), encoding="utf-8")
            msgs.append(f"RESTORED broken V121 injection: {path.relative_to(root)}")
        else:
            # Conservative textual cleanup fallback.
            _backup(path)
            text2 = re.sub(r"^import\s+WaveCorrectionToggle\s+from\s+['\"][^'\"]+['\"];.*\n", "", text, flags=re.M)
            text2 = re.sub(r"\s*<WaveCorrectionToggle\s*/>\s*\{/\*\s*V121_WAVE_CORRECTION_TOGGLE\s*\*/\}", "", text2)
            path.write_text(text2, encoding="utf-8")
            msgs.append(f"CLEANED V121 injection without backup: {path.relative_to(root)}")
    return msgs or ["OK no broken V121 target injection found"]


def ensure_component(root: Path) -> str:
    path = root / COMP_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    _backup(path)
    if path.exists() and "data-v121-wave-correction-toggle" in path.read_text(encoding="utf-8"):
        return f"OK component exists: {path.relative_to(root)}"

    component = r"""
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
      if (next) window.localStorage.setItem(STORAGE_KEY, 'true');
      else window.localStorage.removeItem(STORAGE_KEY);
    } catch {}
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
      title="검증된 scope에서만 WAVE 보정이 적용됩니다. 기본 계산은 raw AquaNova입니다."
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
""".strip() + "\n"
    path.write_text(component, encoding="utf-8")
    return f"WRITTEN component: {path.relative_to(root)}"


def rel_import(from_path: Path, to_path: Path) -> str:
    rel = to_path.with_suffix("").relative_to(from_path.parent)
    raw = str(rel).replace("\\", "/")
    return raw if raw.startswith(".") else "./" + raw


def patch_app(root: Path) -> str:
    app = root / "ui" / "src" / "App.tsx"
    if not app.exists():
        return "SKIP App.tsx missing; component exists but not rendered"
    _backup(app)
    text = app.read_text(encoding="utf-8")
    original = text

    component_path = root / COMP_REL
    import_path = rel_import(app, component_path)

    if "WaveCorrectionToggle" not in text:
        import_line = f"import WaveCorrectionToggle from '{import_path}'; // {MARK}\n"
        imports = list(re.finditer(r"^import\s+.*?;\s*$", text, flags=re.M))
        if imports:
            pos = imports[-1].end()
            text = text[:pos] + "\n" + import_line.rstrip() + text[pos:]
        else:
            text = import_line + text

    if MARK not in text:
        # Pattern: return <Something />;
        text2, n = re.subn(
            r"return\s+(<[^;]+?>)\s*;",
            r"return (<>\1<WaveCorrectionToggle /> {/* " + MARK + r" */}</>);",
            text,
            count=1,
            flags=re.S,
        )
        if n:
            text = text2
        else:
            # Pattern: return ( ... );
            m = re.search(r"return\s*\((?P<body>[\s\S]*?)\n\s*\);", text)
            if not m:
                raise SystemExit("Could not safely patch App.tsx render. Please show ui/src/App.tsx.")
            body = m.group("body")
            new_body = "\n    <>\n" + body.rstrip() + "\n      <WaveCorrectionToggle /> {/* " + MARK + " */}\n    </>"
            text = text[:m.start("body")] + new_body + text[m.end("body"):]

    if text != original:
        app.write_text(text, encoding="utf-8")
        return f"PATCHED safe render in {app.relative_to(root)}"
    return f"UNCHANGED {app.relative_to(root)}"


def main() -> int:
    root = Path.cwd().resolve()
    msgs = []
    msgs.extend(restore_broken_v121_injections(root))
    msgs.append(ensure_component(root))
    msgs.append(patch_app(root))
    print("V121A restore/safe-toggle patch complete")
    for msg in msgs:
        print(msg)
    print()
    print("Refresh Vite after this patch. If Vite keeps old error cache, restart npm run dev.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
