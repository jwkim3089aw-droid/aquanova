#!/usr/bin/env python3
"""V73 production split/refactor selftest.

This test is intentionally runtime-light.  It verifies that the public
wave_production API still resolves through the split modules and that production
plan parsing/dry-run works without launching WAVE.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import wave_production
import wave_production_plan
import wave_production_state
import wave_production_restart


def _write_sample_plan(path: Path) -> None:
    payload = {
        "schema_version": 1,
        "name": "V73 refactor sample direct plan",
        "fresh_project_per_item": True,
        "defaults": {"allow_experimental_ro": True, "allow_experimental_batch": True},
        "cases": [
            {
                "id": "V73_SAMPLE_UF",
                "kind": "uf_video",
                "uf_module": "Ultrafiltration SFP-2660",
                "uf_water_profile": "Well Water - Med Hardness",
                "uf_feed_flow": 100.0,
                "uf_pdf_name": "V73_SAMPLE_UF.pdf",
            },
            {
                "id": "V73_SAMPLE_CCRO",
                "kind": "ccro_video",
                "ccro_element": "FilmTec™ SOAR 5000i",
                "ccro_water_profile": "Well Water - Med Hardness",
                "ccro_feed_flow": 100.0,
                "ccro_recovery": 85.0,
                "ccro_pass_count": 1,
                "ccro_pdf_name": "V73_SAMPLE_CCRO.pdf",
            },
        ],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    assert wave_production.ProductionItem is wave_production_plan.ProductionItem
    assert wave_production.load_production_plan is wave_production_plan.load_production_plan
    assert wave_production.dry_run_production_plan is wave_production_plan.dry_run_production_plan
    assert hasattr(wave_production_state, "_write_manifest")
    assert hasattr(wave_production_restart, "_start_fresh_production_case")

    with tempfile.TemporaryDirectory(prefix="wave_v73_refactor_") as tmp:
        plan_path = Path(tmp) / "sample_plan.json"
        _write_sample_plan(plan_path)
        plan, items = wave_production.load_production_plan(plan_path)
        assert plan["name"] == "V73 refactor sample direct plan"
        assert [item.kind for item in items] == ["uf_video", "ccro_video"]
        assert [item.key for item in items] == ["V73_SAMPLE_UF", "V73_SAMPLE_CCRO"]
        summary = wave_production.dry_run_production_plan(plan_path)
        assert summary["case_count"] == 2
        assert wave_production_plan._plan_requires_case_isolation(plan, items) is True

    print("V73 production split refactor selftest PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
