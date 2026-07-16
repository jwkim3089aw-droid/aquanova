#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
GENERATOR = SCRIPTS / "wave_lg_bw440_soar_bracket_campaign.py"
PLAN_DIR = SCRIPTS / "wave_records"
PLAN_GLOB = "AquaNova_WAVE_V104_LG_BW440_SOAR_BRACKET_*.json"
PRODUCTION_SCHEMA_VERSION = 1
CAMPAIGN_SCHEMA = "aquanova.wave_meeting_lg_bw440_soar_bracket.V104"


def patch_generator() -> bool:
    if not GENERATOR.exists():
        print(f"generator_missing: {GENERATOR}")
        return False

    text = GENERATOR.read_text(encoding="utf-8")
    original = text

    # The production plan loader requires top-level schema_version to be integer 1.
    # Keep the campaign identifier under campaign_schema_version.
    text = text.replace(
        'new_plan["schema_version"] = "aquanova.wave_meeting_lg_bw440_soar_bracket.V104"',
        'new_plan["schema_version"] = 1\n                new_plan["campaign_schema_version"] = "aquanova.wave_meeting_lg_bw440_soar_bracket.V104"',
    )

    # Make the replacement robust if spacing changed.
    text = re.sub(
        r'new_plan\["schema_version"\]\s*=\s*CAMPAIGN_SCHEMA',
        'new_plan["schema_version"] = 1\n                new_plan["campaign_schema_version"] = CAMPAIGN_SCHEMA',
        text,
    )

    if text != original:
        GENERATOR.write_text(text, encoding="utf-8")
        print(f"patched_generator: {GENERATOR}")
        return True

    print(f"generator_already_ok_or_pattern_not_found: {GENERATOR}")
    return False


def patch_plan_file(path: Path) -> bool:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"plan_read_error: {path} {exc!r}")
        return False

    old_schema = data.get("schema_version")
    changed = False

    if old_schema != PRODUCTION_SCHEMA_VERSION:
        if isinstance(old_schema, str):
            data.setdefault("campaign_schema_version", old_schema)
        data["schema_version"] = PRODUCTION_SCHEMA_VERSION
        changed = True

    data.setdefault("campaign_schema_version", CAMPAIGN_SCHEMA)

    if changed:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"patched_plan_schema: {path} old={old_schema!r} new=1")
        return True

    print(f"plan_schema_ok: {path}")
    return False


def main() -> int:
    patch_generator()

    plans = sorted(PLAN_DIR.glob(PLAN_GLOB))
    if not plans:
        print(f"no_existing_v104_plans_found: {PLAN_DIR / PLAN_GLOB}")
        print("Regenerate plans with:")
        print('  cd "C:\\Users\\a\\Desktop\\프로젝트\\AquaNova\\code\\scripts"')
        print("  python .\\wave_lg_bw440_soar_bracket_campaign.py --write --print-summary --print-run-commands")
        return 0

    patched = 0
    for plan in plans:
        if patch_plan_file(plan):
            patched += 1

    print(f"V106 V104 production schema hotfix done. plan_count={len(plans)} patched_count={patched}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
