#!/usr/bin/env python3
"""Offline self-test for the V52 full experimental RO schema/catalog/XLSX reader."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from wave_ro_catalog import catalog_payload
from wave_ro_excel import load_ro_cases


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--xlsx", required=True)
    parser.add_argument("--sheet", default="01_PASS_STAGE")
    parser.add_argument("--batch-group", default=None)
    args = parser.parse_args()
    cases = load_ro_cases(args.xlsx, args.sheet)
    if args.batch_group:
        wanted = args.batch_group.strip().casefold()
        cases = [case for case in cases if case.batch_group.strip().casefold() == wanted]
    for case in cases:
        case.validate()
    payload = {
        "ok": True,
        "automation_version": "V52",
        "source": str(Path(args.xlsx)),
        "sheet": args.sheet,
        "case_count": len(cases),
        "catalog_count": len(catalog_payload()["items"]),
        "groups": sorted({case.batch_group for case in cases if case.batch_group}),
        "tiers": {tier: sum(case.automation_tier == tier for case in cases) for tier in ("stable", "new", "experimental")},
        "cases": [case.to_flat_dict() for case in cases],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
