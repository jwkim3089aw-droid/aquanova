#!/usr/bin/env python3
from __future__ import annotations

import re
from pathlib import Path

MARK = "V121_WAVE_CORRECTION_TOGGLE"
COMP_IMPORT = "import WaveCorrectionToggle from './features/simulation/components/WaveCorrectionToggle'; // V121_WAVE_CORRECTION_TOGGLE"


def backup(path: Path) -> None:
    b = path.with_suffix(path.suffix + ".v121a_before_v121b.bak")
    if path.exists() and not b.exists():
        b.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")


def ensure_import(text: str) -> str:
    if "WaveCorrectionToggle" in text:
        return text
    imports = list(re.finditer(r"^import\s+.*?;\s*$", text, flags=re.M))
    if imports:
        pos = imports[-1].end()
        return text[:pos] + "\n" + COMP_IMPORT + text[pos:]
    return COMP_IMPORT + "\n" + text


def force_render(text: str) -> str:
    # Already rendered?
    if "<WaveCorrectionToggle" in text:
        return text

    # App.tsx currently has: return ( <div ...> ... </div> );
    # Wrap the returned root element with a fragment and append the fixed-position toggle.
    m = re.search(r"return\s*\(\s*(<div[\s\S]*</div>)\s*\);", text)
    if m:
        root_jsx = m.group(1).rstrip()
        replacement = (
            "return (\n"
            "    <>\n"
            f"{root_jsx}\n"
            f"      <WaveCorrectionToggle /> {{/* {MARK} */}}\n"
            "    </>\n"
            "  );"
        )
        return text[:m.start()] + replacement + text[m.end():]

    # Fallback for a different root tag: capture between return ( and the matching final );
    m2 = re.search(r"return\s*\(([\s\S]*?)\n\s*\);", text)
    if m2:
        body = m2.group(1).rstrip()
        replacement = (
            "return (\n"
            "    <>\n"
            f"{body}\n"
            f"      <WaveCorrectionToggle /> {{/* {MARK} */}}\n"
            "    </>\n"
            "  );"
        )
        return text[:m2.start()] + replacement + text[m2.end():]

    raise SystemExit("Could not find App.tsx return block. Please paste ui/src/App.tsx.")


def main() -> int:
    root = Path.cwd().resolve()
    app = root / "ui" / "src" / "App.tsx"
    if not app.exists():
        raise SystemExit(f"not found: {app}")

    backup(app)
    text = app.read_text(encoding="utf-8")
    text = ensure_import(text)
    text = force_render(text)
    app.write_text(text, encoding="utf-8")

    print("V121B force App render toggle patch applied")
    print(f"patched: {app}")
    print("Now App.tsx should both import and render <WaveCorrectionToggle />.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
