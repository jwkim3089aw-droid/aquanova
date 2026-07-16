#!/usr/bin/env python3
"""Offline self-test for the V70 production-plan export helper."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from wave_v70_plan_export import build_plans, write_plans

plans = build_plans()
assert len(plans) == 3, plans.keys()
for filename, payload in plans.items():
    assert filename.endswith('.json'), filename
    assert payload['schema_version'] == 1
    assert payload['plan_kit_version'] == 'V70'
    assert isinstance(payload.get('cases'), list) and payload['cases']
    json.dumps(payload, ensure_ascii=False)

with tempfile.TemporaryDirectory() as td:
    paths = write_plans(Path(td))
    assert len(paths) == 3
    for path in paths:
        data = json.loads(path.read_text(encoding='utf-8'))
        assert data['schema_version'] == 1
        assert data['cases']

print('V70 production plan export selftest PASS')
