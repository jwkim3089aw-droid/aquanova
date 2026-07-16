#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "wave_records" / "wave_v117_pass_only_layer_export.py"

layer = {
    "schema_version": "test.v98",
    "runtime_enabled_by_default": False,
    "models": [
        {"model_id": "m_pass", "process_type": "ccro", "metric": "specific_energy"},
        {"model_id": "m_fail", "process_type": "ro", "metric": "specific_energy"},
    ],
}
groups = [
    {"model_id": "m_pass", "shadow_status": "pass", "flags": ""},
    {"model_id": "m_fail", "shadow_status": "fail", "flags": "holdout_regression"},
]

with tempfile.TemporaryDirectory() as td:
    td = Path(td)
    layer_path = td / "layer.json"
    group_path = td / "groups.csv"
    out = td / "pass_layer.json"
    cfg = td / "config.json"
    md = td / "report.md"
    layer_path.write_text(json.dumps(layer), encoding="utf-8")
    with group_path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["model_id", "shadow_status", "flags"])
        w.writeheader()
        w.writerows(groups)
    subprocess.run(
        [sys.executable, str(SCRIPT), "--layer", str(layer_path), "--group-summary", str(group_path), "--output", str(out), "--config-output", str(cfg), "--markdown-output", str(md), "--print-summary"],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        check=True,
    )
    exported = json.loads(out.read_text(encoding="utf-8"))
    assert len(exported["models"]) == 1, exported
    assert exported["models"][0]["model_id"] == "m_pass", exported
    assert exported["runtime_enabled_by_default"] is False, exported
    config = json.loads(cfg.read_text(encoding="utf-8"))
    assert config["enabled"] is False, config

print("V117 pass-only layer export selftest PASS")
