#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import wave_260709_meeting_campaign as campaign


def main() -> int:
    plans = campaign._build_plans()
    assert len(plans) == 4, len(plans)
    total_cases = sum(len(p.get("cases", [])) for p in plans.values())
    assert total_cases == 16, total_cases
    fr_plan = plans["AquaNova_WAVE_V100_260709_01_fr_pump_energy_sweep.json"]
    ratios = [c.get("target_pf_feed_ratio_pct") for c in fr_plan["cases"]]
    assert ratios == [120.0, 150.0, 270.0, 300.0], ratios
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "wave_records"
        paths = campaign.write_plans(out, plans)
        assert len(paths) == 4
        for p in paths:
            data = json.loads(p.read_text(encoding="utf-8"))
            assert data["fresh_project_per_item"] is True
            assert data["cases"]
        csv_path, md_path = campaign._write_handcalc(Path(td) / "handcalc")
        assert csv_path.exists()
        assert md_path.exists()
        text = csv_path.read_text(encoding="utf-8-sig")
        assert "FR150" in text
        assert "0.91" in text or "0.910" in text
    print("V100 2026-07-09 meeting campaign selftest PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
