#!/usr/bin/env python3
"""Self-test V71 restart-safe production-plan export."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import wave_v71_plan_export as v71
import wave_v70_plan_export as v70


def _assert_restart_safe(payload: dict, *, expected_version: str) -> None:
    assert payload["plan_kit_version"] == expected_version
    assert payload["fresh_project_per_item"] is True
    assert payload["defaults"]["fresh_project_per_item"] is True
    assert payload["cases"], "plan must contain at least one case"
    assert any(case.get("kind") == "ro_excel" for case in payload["cases"])


def main() -> int:
    v71_plans = v71.build_plans()
    assert len(v71_plans) == 3
    assert all("V71" in name and "restart_safe" in name for name in v71_plans)
    for payload in v71_plans.values():
        _assert_restart_safe(payload, expected_version="V71")

    # The V70 helper is overwritten too, so re-running the old helper repairs the
    # old V70 JSON filenames in-place.
    v70_plans = v70.build_plans()
    assert len(v70_plans) == 3
    assert all("V70" in name for name in v70_plans)
    for payload in v70_plans.values():
        _assert_restart_safe(payload, expected_version="V70")

    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        written = v71.write_plans(out)
        assert len(written) == 3
        for path in written:
            payload = json.loads(path.read_text(encoding="utf-8"))
            _assert_restart_safe(payload, expected_version="V71")

    print("V71 restart-safe plan export selftest PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
