#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
GENERATOR = SCRIPTS / "wave_lg_bw440_soar_bracket_campaign.py"
PLAN_DIR = SCRIPTS / "wave_records"
PLAN_GLOB = "AquaNova_WAVE_V104_LG_BW440_SOAR_BRACKET_*.json"

PDF_KEYS = (
    "ccro_pdf_name",
    "pdf_name",
    "report_name",
    "report_basename",
    "target_pdf",
    "output_pdf",
    "expected_pdf",
)

def _soar_tag(case: dict) -> str | None:
    for source in (case.get("ccro_element"), case.get("element_type"), case.get("element")):
        if not source:
            continue
        s = str(source)
        if "SOAR 4000i" in s:
            return "SOAR4000i"
        if "SOAR 5000i" in s:
            return "SOAR5000i"
        if "SOAR 3000i" in s:
            return "SOAR3000i"
        if "SOAR 6000i" in s:
            return "SOAR6000i"
        if "SOAR 7000i" in s:
            return "SOAR7000i"
    return None

def _tag_pdf_name(value: str, tag: str) -> str:
    if not value:
        return value
    if tag in value:
        return value
    if value.lower().endswith(".pdf"):
        return value[:-4] + f"_{tag}.pdf"
    return value + f"_{tag}"

def patch_generator() -> int:
    if not GENERATOR.exists():
        print(f"generator_missing: {GENERATOR}")
        return 0
    text = GENERATOR.read_text(encoding="utf-8")
    old = text

    # V104 originally updated pdf_name/report_name/etc but missed ccro_pdf_name, which is
    # the field used by ccro_video runner. Add it to the loop if missing.
    text = text.replace(
        'for key in ("pdf_name", "report_name", "report_basename", "target_pdf", "output_pdf", "expected_pdf"):',
        'for key in ("ccro_pdf_name", "pdf_name", "report_name", "report_basename", "target_pdf", "output_pdf", "expected_pdf"):',
    )

    if text != old:
        GENERATOR.write_text(text, encoding="utf-8")
        print(f"patched_generator_pdf_keys: {GENERATOR}")
        return 1
    print(f"generator_pdf_keys_already_ok: {GENERATOR}")
    return 0

def patch_plan(path: Path) -> int:
    data = json.loads(path.read_text(encoding="utf-8"))
    changed = False

    if data.get("schema_version") != 1:
        if isinstance(data.get("schema_version"), str):
            data.setdefault("campaign_schema_version", data.get("schema_version"))
        data["schema_version"] = 1
        changed = True

    for case in data.get("cases") or []:
        tag = _soar_tag(case)
        if not tag:
            continue

        # Make keys/ids/PDFs unambiguous.
        for key in ("key", "id", "case_id", "name"):
            if case.get(key) and tag not in str(case[key]):
                case[key] = f"{case[key]}_{tag}"
                changed = True

        for key in PDF_KEYS:
            if case.get(key):
                new = _tag_pdf_name(str(case[key]), tag)
                if new != case[key]:
                    case[key] = new
                    changed = True

    if changed:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"patched_plan_pdf_names: {path}")
        return 1
    print(f"plan_pdf_names_ok: {path}")
    return 0

def main() -> int:
    patch_generator()
    plans = sorted(PLAN_DIR.glob(PLAN_GLOB))
    patched = 0
    for p in plans:
        patched += patch_plan(p)
    print(f"V108 SOAR PDF naming hotfix done. inspected_plans={len(plans)} patched_plans={patched}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
