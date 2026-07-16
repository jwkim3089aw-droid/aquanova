#!/usr/bin/env python3
"""V73 plan exporter selftest."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from wave_v73_plan_export import build_plans, write_plans


def main() -> int:
    plans = build_plans()
    assert len(plans) == 4, sorted(plans)
    step04_names = [name for name in plans if "production_plan_04_mixed_10_cautious" in name]
    assert len(step04_names) == 1
    step04 = plans[step04_names[0]]
    assert step04["fresh_project_per_item"] is True
    assert step04["defaults"]["fresh_project_per_item"] is True
    assert step04["plan_kit_version"] == "V73"
    kinds = [case["kind"] for case in step04["cases"]]
    assert kinds == ["ro_excel", "uf_video", "uf_video", "uf_video", "ccro_video", "ccro_video", "ccro_video"]

    with tempfile.TemporaryDirectory(prefix="wave_v73_plan_") as tmp:
        paths = write_plans(Path(tmp))
        assert len(paths) == 4
        for path in paths:
            data = json.loads(path.read_text(encoding="utf-8"))
            assert data["fresh_project_per_item"] is True

    print("V73 plan exporter selftest PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
