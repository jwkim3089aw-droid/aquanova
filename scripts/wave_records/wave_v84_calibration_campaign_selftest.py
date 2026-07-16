#!/usr/bin/env python3
"""Selftest for the V84/V85 WAVE calibration campaign exporter."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from wave_v84_calibration_campaign_export import (
    build_campaign_plans,
    plan_summary,
    remove_stale_v84_anchor_plans,
    write_plans,
)


def main() -> int:
    # Fallback mode still writes planned RO/NF ranges when the workbook cannot be
    # preflighted.  The summary counts expected anchor targets, not JSON items.
    plans = build_campaign_plans(ro_start_order=1, ro_end_order=12, ro_chunk_size=5)
    summary = plan_summary(plans)
    assert summary["plan_count"] >= 7, summary
    assert summary["case_count"] >= 30, summary
    assert summary["kind_counts"].get("ro_excel", 0) == 12, summary
    assert summary["kind_counts"].get("uf_video", 0) >= 8, summary
    assert summary["kind_counts"].get("ccro_video", 0) >= 8, summary

    # Preflight mode must not create empty 011-020 / 021-030 plans when the
    # sheet only has orders 1,2,3.  This is the V85 hotfix for the user's failed
    # V84 second RO/NF batch.
    preflighted = build_campaign_plans(
        ro_start_order=1,
        ro_end_order=45,
        ro_chunk_size=10,
        available_ro_orders=[1, 2, 3],
    )
    pre_summary = plan_summary(preflighted)
    assert pre_summary["kind_counts"].get("ro_excel") == 3, pre_summary
    assert any("orders_001_003" in name for name in preflighted), sorted(preflighted)
    assert not any("orders_011_020" in name for name in preflighted), sorted(preflighted)

    for filename, plan in preflighted.items():
        assert filename.endswith(".json")
        assert plan["schema_version"] == 1
        assert plan["plan_kit_version"] == "V84"
        assert plan["fresh_project_per_item"] is True
        assert plan["defaults"]["fresh_project_per_item"] is True
        assert plan["cases"], filename
        for case in plan["cases"]:
            assert "id" in case and case["id"], case
            assert case.get("kind") in {"ro_excel", "uf_video", "ccro_video"}, case
            assert "calibration_tags" in case, case

    with tempfile.TemporaryDirectory() as tmp:
        out_dir = Path(tmp)
        stale = out_dir / "AquaNova_WAVE_V84_anchor_01_ro_nf_orders_011_020.json"
        stale.write_text("{}", encoding="utf-8")
        paths = write_plans(out_dir, preflighted)
        removed = remove_stale_v84_anchor_plans(out_dir, paths)
        assert stale in removed, removed
        assert len(paths) == len(preflighted)
        for path in paths:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            assert loaded["calibration_campaign"] is True
            assert loaded["cases"]

    print("V84 calibration campaign selftest PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
