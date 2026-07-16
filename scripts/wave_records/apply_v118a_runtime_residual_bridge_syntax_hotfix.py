#!/usr/bin/env python3
from __future__ import annotations

import py_compile
from pathlib import Path

BAD_LINE = "from __future__ import annotations as _v118_annotations"


def main() -> int:
    root = Path.cwd().resolve()
    helper = root / "app" / "services" / "simulation" / "calibration" / "wave_runtime_correction.py"
    if not helper.exists():
        raise SystemExit(f"not found: {helper}")

    text = helper.read_text(encoding="utf-8")
    backup = helper.with_suffix(helper.suffix + ".v118_syntax_error.bak")
    if not backup.exists():
        backup.write_text(text, encoding="utf-8")

    lines = text.splitlines()
    fixed_lines = [line for line in lines if BAD_LINE not in line]
    fixed = "\n".join(fixed_lines).rstrip() + "\n"
    helper.write_text(fixed, encoding="utf-8")

    py_compile.compile(str(helper), doraise=True)

    print("V118A syntax hotfix applied")
    print(f"helper: {helper}")
    print(f"backup: {backup}")
    print("compile: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
