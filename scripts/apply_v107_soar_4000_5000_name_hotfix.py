#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
GENERATOR = SCRIPTS / "wave_lg_bw440_soar_bracket_campaign.py"
PLAN_DIR = SCRIPTS / "wave_records"
PLAN_GLOB = "AquaNova_WAVE_V104_LG_BW440_SOAR_BRACKET_*.json"

REPLACEMENTS = {
    "FilmTec™ SOAR 400i": "FilmTec™ SOAR 4000i",
    "FilmTec™ SOAR 500i": "FilmTec™ SOAR 5000i",
    "SOAR400i": "SOAR4000i",
    "SOAR500i": "SOAR5000i",
    "SOAR 400i": "SOAR 4000i",
    "SOAR 500i": "SOAR 5000i",
}


def _replace_text(text: str) -> tuple[str, int]:
    count = 0
    for old, new in REPLACEMENTS.items():
        n = text.count(old)
        if n:
            text = text.replace(old, new)
            count += n
    return text, count


def patch_generator() -> int:
    if not GENERATOR.exists():
        print(f"generator_missing: {GENERATOR}")
        return 0
    text = GENERATOR.read_text(encoding="utf-8")
    new_text, count = _replace_text(text)
    if count:
        GENERATOR.write_text(new_text, encoding="utf-8")
        print(f"patched_generator: {GENERATOR} replacements={count}")
    else:
        print(f"generator_already_ok: {GENERATOR}")
    return count


def _fix_obj(obj):
    if isinstance(obj, dict):
        return {k: _fix_obj(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_fix_obj(v) for v in obj]
    if isinstance(obj, str):
        new, _ = _replace_text(obj)
        return new
    return obj


def patch_plan(path: Path) -> int:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"plan_read_error: {path} {exc!r}")
        return 0

    before = json.dumps(data, ensure_ascii=False, sort_keys=True)
    data = _fix_obj(data)

    # Keep production loader compatible.
    old_schema = data.get("schema_version")
    if old_schema != 1:
        if isinstance(old_schema, str):
            data.setdefault("campaign_schema_version", old_schema)
        data["schema_version"] = 1

    after = json.dumps(data, ensure_ascii=False, sort_keys=True)
    if before != after:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"patched_plan: {path}")
        return 1
    print(f"plan_already_ok: {path}")
    return 0


def main() -> int:
    patch_generator()

    plans = sorted(PLAN_DIR.glob(PLAN_GLOB))
    patched = 0
    for plan in plans:
        patched += patch_plan(plan)

    print(f"V107 SOAR 4000/5000 name hotfix done. inspected_plans={len(plans)} patched_plans={patched}")
    if not plans:
        print("No existing V104 plans found. Regenerate with:")
        print('  cd "C:\\Users\\a\\Desktop\\프로젝트\\AquaNova\\code\\scripts"')
        print("  python .\\wave_lg_bw440_soar_bracket_campaign.py --write --print-summary --print-run-commands")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
