#!/usr/bin/env python3
"""Write V70 expansion production-plan JSON files.

Compatibility wrapper retained for existing commands.  Shared plan-building
logic now lives in wave_plan_library.py.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from wave_plan_library import build_standard_expansion_plans, print_export_summary, write_plan_files

PLAN_KIT_VERSION = "V70"


def build_plans() -> dict[str, dict[str, Any]]:
    return build_standard_expansion_plans(version=PLAN_KIT_VERSION, restart_safe=True, restart_suffix=False)


def write_plans(output_dir: Path | None = None) -> list[Path]:
    return write_plan_files(build_plans(), output_dir)


def main() -> int:
    paths = write_plans()
    print_export_summary(PLAN_KIT_VERSION, paths)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
