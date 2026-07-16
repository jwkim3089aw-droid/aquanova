#!/usr/bin/env python3
"""Offline self-test for V58 production plan parsing/checkpoint helpers."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from wave_runtime import record_event

from wave_production import (
    PRODUCTION_AUTOMATION_VERSION,
    dry_run_production_plan,
    load_production_plan,
    write_production_plan_example,
    _load_checkpoint,
    _mark_checkpoint_item,
    _plan_requires_case_isolation,
    _production_family,
    _write_checkpoint,
)


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        plan_path = root / "plan.json"
        plan_path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "name": "offline-direct-plan",
                    "cases": [
                        {
                            "id": "UF_SMOKE",
                            "kind": "uf_video",
                            "uf_module": "Ultrafiltration SFP-2660",
                            "uf_water_profile": "Well Water - Med Hardness",
                            "uf_feed_flow": 100,
                            "uf_pdf_name": "UF_SMOKE.pdf",
                        },
                        {
                            "id": "CCRO_SMOKE",
                            "kind": "ccro_video",
                            "ccro_element": "FilmTec™ SOAR 5000i",
                            "ccro_pass_count": 2,
                            "ccro_recovery": 90,
                            "ccro_pass2_recovery": 90,
                            "ccro_pdf_name": "CCRO_SMOKE.pdf",
                        },
                    ],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        plan, items = load_production_plan(plan_path)
        assert plan["name"] == "offline-direct-plan"
        assert [item.key for item in items] == ["UF_SMOKE", "CCRO_SMOKE"]
        assert [item.kind for item in items] == ["uf_video", "ccro_video"]
        assert [_production_family(item) for item in items] == ["uf", "ccro"]
        assert _plan_requires_case_isolation(plan, items) is True
        plan_disabled = dict(plan)
        plan_disabled["defaults"] = {"fresh_case_per_process": False}
        assert _plan_requires_case_isolation(plan_disabled, items) is False
        dry = dry_run_production_plan(plan_path)
        assert dry["automation_version"] == PRODUCTION_AUTOMATION_VERSION
        assert dry["case_count"] == 2
        checkpoint_path = root / "checkpoint.json"
        checkpoint = _load_checkpoint(checkpoint_path)
        _mark_checkpoint_item(checkpoint, "UF_SMOKE", status="success", attempt=1, payload={"pdfs": ["UF_SMOKE.pdf"]})
        _write_checkpoint(checkpoint_path, checkpoint)
        reloaded = _load_checkpoint(checkpoint_path)
        assert reloaded["items"]["UF_SMOKE"]["status"] == "success"
        example_path = write_production_plan_example(root)
        assert example_path.exists()
        example = json.loads(example_path.read_text(encoding="utf-8"))
        assert example["schema_version"] == 1
        assert len(example["cases"]) >= 3
        # Regression: production event payload must not reuse record_event's first
        # positional parameter name (kind), which caused V56 to fail before any item ran.
        record_event("production_item_attempt_start_v58", key="UF_SMOKE", item_kind="uf_video", attempt=1)
    print("V58 production self-test PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
