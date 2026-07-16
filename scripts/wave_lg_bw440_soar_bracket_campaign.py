#!/usr/bin/env python3
r"""Generate WAVE CCRO plans for LG BW 440 R G2 pilot using available SOAR surrogates.

Why this exists:
- WAVE CCRO catalog often exposes only FilmTec™ SOAR 300i/400i/500i/600i/700i.
- The actual pilot membrane is LG BW 440 R G2, but it is not selectable in WAVE CCRO.
- This script brackets LG BW 440 R G2 with SOAR 4000i and SOAR 5000i while preserving
  actual LG metadata in each case.

Run from:
    C:\Users\a\Desktop\프로젝트\AquaNova\code\scripts

Commands:
    python .\wave_lg_bw440_soar_bracket_campaign_selftest.py
    python .\wave_lg_bw440_soar_bracket_campaign.py --write --print-summary --print-run-commands

Prerequisite:
    V102 script wave_lg_bw440_pilot_campaign.py must exist in this scripts folder.
    V101 CCRO plan field passthrough hotfix should be applied so PV/elements pass through.
"""
from __future__ import annotations

import argparse
import copy
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

DEFAULT_ELEMENTS = ["FilmTec™ SOAR 4000i", "FilmTec™ SOAR 5000i"]
TAG_BY_ELEMENT = {
    "FilmTec™ SOAR 4000i": "SOAR4000i",
    "FilmTec™ SOAR 5000i": "SOAR5000i",
    "FilmTec™ SOAR 300i": "SOAR300i",
    "FilmTec™ SOAR 600i": "SOAR600i",
    "FilmTec™ SOAR 700i": "SOAR700i",
}


def _load_v102():
    here = Path(__file__).resolve().parent
    mod_path = here / "wave_lg_bw440_pilot_campaign.py"
    if not mod_path.exists():
        raise SystemExit(
            "Missing wave_lg_bw440_pilot_campaign.py. Apply/install V102 first, then rerun V104."
        )
    spec = importlib.util.spec_from_file_location("wave_lg_bw440_pilot_campaign", mod_path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"Cannot load {mod_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    if not hasattr(module, "_build_plans"):
        raise SystemExit("V102 generator does not expose _build_plans(). Reapply V102.")
    return module


def _case_id(case: dict[str, Any]) -> str:
    for key in ("key", "case_id", "name", "id"):
        val = case.get(key)
        if val:
            return str(val)
    return "case"


def _tag_case(case: dict[str, Any], tag: str, wave_element: str) -> dict[str, Any]:
    c = copy.deepcopy(case)
    old_id = _case_id(c)
    new_id = f"{old_id}_{tag}"

    # Update common identifiers used by the production tooling.
    for key in ("key", "case_id", "id", "name"):
        if key in c and c[key]:
            c[key] = f"{c[key]}_{tag}"

    # Update common output/report fields if present.
    for key in ("ccro_pdf_name", "pdf_name", "report_name", "report_basename", "target_pdf", "output_pdf", "expected_pdf"):
        if key in c and c[key]:
            val = str(c[key])
            if val.lower().endswith(".pdf"):
                stem = val[:-4]
                c[key] = f"{stem}_{tag}.pdf"
            else:
                c[key] = f"{val}_{tag}"

    # Ensure the actual WAVE dropdown choice is the SOAR surrogate.
    for key in ("ccro_element", "element", "element_type", "wave_element", "ro_element"):
        c[key] = wave_element

    # Keep actual pilot metadata explicit.
    c["actual_membrane"] = {
        "brand": "LG Chem",
        "model": "LG BW 440 R G2",
        "active_area_ft2": 440,
        "active_area_m2": 41,
        "average_nacl_rejection_pct": 99.78,
        "max_pressure_bar": 41.4,
        "max_temperature_c": 45,
        "diameter_in": 7.9,
        "length_in": 40,
        "source": "user-provided Lenntech specification text",
    }
    c["wave_surrogate"] = {
        "element": wave_element,
        "surrogate_tag": tag,
        "reason": "LG BW 440 R G2 is not available in WAVE CCRO element dropdown",
        "interpretation": "Use SOAR 4000i/500i as WAVE-calculable bracket around 440 ft2 LG pilot element.",
    }

    tags = list(c.get("tags") or [])
    for t in ("lg_bw440_actual", "ccro_soar_surrogate", tag):
        if t not in tags:
            tags.append(t)
    c["tags"] = tags

    # Hard-set pilot geometry.
    c["pv_per_stage"] = 1
    c["elements_per_pv"] = c.get("elements_per_pv", c.get("ccro_elements_per_pv", 3))
    c["ccro_pv_per_stage"] = 1
    c["ccro_elements_per_pv"] = c.get("ccro_elements_per_pv", c.get("elements_per_pv", 3))
    return c


def _combine_plans(v102, elements: list[str]) -> dict[str, dict[str, Any]]:
    combined: dict[str, dict[str, Any]] = {}

    for element in elements:
        tag = TAG_BY_ELEMENT.get(element, element.replace(" ", "").replace("™", "").replace("-", ""))
        plans = v102._build_plans(element)
        for original_name, plan in plans.items():
            suffix = original_name
            # Rename V102 filenames to V104 filenames, preserving stage number/title if possible.
            suffix = suffix.replace("AquaNova_WAVE_V102_LG_BW440_", "")
            new_name = f"AquaNova_WAVE_V104_LG_BW440_SOAR_BRACKET_{suffix}"
            if new_name not in combined:
                new_plan = copy.deepcopy(plan)
                new_plan["cases"] = []
                new_plan["schema_version"] = 1
                new_plan["campaign_schema_version"] = "aquanova.wave_meeting_lg_bw440_soar_bracket.V104"
                new_plan["description"] = (
                    "LG BW 440 R G2 pilot WAVE test using SOAR 4000i/500i surrogate bracket."
                )
                combined[new_name] = new_plan

            for case in plan.get("cases", []):
                combined[new_name]["cases"].append(_tag_case(case, tag, element))

    # Ensure filenames end with .json
    fixed = {}
    for name, plan in combined.items():
        fixed[name if name.endswith(".json") else f"{name}.json"] = plan
    return fixed


def _run_command(plan_path: Path) -> str:
    return (
        "python .\\wave_records\\wave_video_demo.py `\n"
        f"  --run-production-plan \"{plan_path}\" `\n"
        "  --production-max-attempts 2 `\n"
        "  --production-restart-monitor-index 2 `\n"
        "  --production-rerun-completed `\n"
        "  --allow-experimental-ro `\n"
        "  --allow-experimental-batch"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="V104 LG BW440 SOAR surrogate bracket campaign.")
    parser.add_argument(
        "--wave-elements",
        nargs="+",
        default=DEFAULT_ELEMENTS,
        help="WAVE CCRO dropdown elements to use. Default: SOAR 4000i and SOAR 5000i.",
    )
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--print-summary", action="store_true")
    parser.add_argument("--print-run-commands", action="store_true")
    args = parser.parse_args()

    v102 = _load_v102()
    plans = _combine_plans(v102, args.wave_elements)

    here = Path(__file__).resolve().parent
    out_dir = here / "wave_records"
    out_dir.mkdir(exist_ok=True)

    written: list[Path] = []
    if args.write:
        for filename, plan in plans.items():
            path = out_dir / filename
            path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
            written.append(path)

    case_count = sum(len(plan.get("cases", [])) for plan in plans.values())
    element_counts: dict[str, int] = {}
    geometry_counts: dict[str, int] = {}
    for plan in plans.values():
        for case in plan.get("cases", []):
            element = case.get("ccro_element", "")
            element_counts[element] = element_counts.get(element, 0) + 1
            geom = f"{case.get('ccro_pv_per_stage')}PVx{case.get('ccro_elements_per_pv')}E"
            geometry_counts[geom] = geometry_counts.get(geom, 0) + 1

    if args.print_summary:
        print(f"V104 LG BW440 SOAR bracket campaign prepared: {len(plans)} plan file(s)")
        for path in written:
            print(path)
        print(json.dumps({
            "schema_version": "aquanova.wave_meeting_lg_bw440_soar_bracket.V104",
            "plan_count": len(plans),
            "case_count": case_count,
            "wave_element_counts": element_counts,
            "geometry_counts": geometry_counts,
            "actual_membrane": "LG BW 440 R G2",
        }, ensure_ascii=False, sort_keys=True))

    if args.print_run_commands:
        print("\nRun commands:\n")
        paths = written if written else [out_dir / filename for filename in plans]
        for path in paths:
            print(_run_command(path))
            print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
