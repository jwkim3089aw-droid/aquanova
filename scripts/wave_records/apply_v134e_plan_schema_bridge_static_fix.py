#!/usr/bin/env python3
from __future__ import annotations

import json
import py_compile
from datetime import datetime
from pathlib import Path

OLD_MARKER = "# V134D WaveAutomationError bridge"
NEW_MARKER = "# V134E WaveAutomationError bridge"
NEW_BRIDGE = '# V134E WaveAutomationError bridge\nclass WaveAutomationError(RuntimeError):\n    pass\n\ntry:\n    from wave_uia import WaveAutomationError as WaveAutomationError  # type: ignore[no-redef]\nexcept Exception:\n    try:\n        from ..wave_uia import WaveAutomationError as WaveAutomationError  # type: ignore[no-redef]\n    except Exception:\n        pass\n\n'


def backup(path: Path, tag: str) -> None:
    if path.exists():
        bak = path.with_suffix(path.suffix + f".{tag}.bak")
        if not bak.exists():
            bak.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")


def replace_bridge(text: str) -> str:
    if NEW_MARKER in text:
        return text

    if OLD_MARKER not in text:
        raise SystemExit("V134D bridge marker not found in batch/plan_schema.py. Apply V134D first.")

    lines = text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if line.strip() == OLD_MARKER:
            start = i
            break
    if start is None:
        raise SystemExit("V134D bridge start not found.")

    end = start
    seen_fallback_pass = False
    while end < len(lines):
        if lines[end].strip() == "pass":
            seen_fallback_pass = True
        if seen_fallback_pass and end + 1 < len(lines) and not lines[end + 1].strip():
            end += 2
            break
        end += 1
        if end - start > 30:
            raise SystemExit("Could not safely locate end of V134D bridge block.")

    new_lines = lines[:start] + NEW_BRIDGE.strip().splitlines() + [""] + lines[end:]
    return "\n".join(new_lines).rstrip() + "\n"


def main() -> int:
    root = Path.cwd().resolve()
    plan_schema = root / "scripts" / "wave_records" / "batch" / "plan_schema.py"
    manifest = root / "scripts" / "wave_records" / "batch" / "v134e_plan_schema_bridge_static_fix_manifest.json"

    if not plan_schema.exists():
        raise SystemExit("batch/plan_schema.py not found.")

    text = plan_schema.read_text(encoding="utf-8")
    if NEW_MARKER in text and manifest.exists():
        print("V134E already applied")
        print(f"manifest={manifest}")
        return 0

    backup(plan_schema, "v134d_before_v134e")
    new_text = replace_bridge(text)
    plan_schema.write_text(new_text, encoding="utf-8")

    py_compile.compile(str(plan_schema), doraise=True)

    data = {
        "schema_version": "aquanova.refactor.v134e.plan_schema_bridge_static_fix",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "plan_schema": str(plan_schema),
        "note": "Normalizes WaveAutomationError bridge so static audit sees a top-level class definition while runtime can still override from wave_uia.",
    }
    manifest.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    print("V134E plan_schema WaveAutomationError bridge static fix applied")
    print(f"manifest={manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
