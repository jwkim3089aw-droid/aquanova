#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "wave_records" / "wave_v116_scope_residual_shadow_validation.py"

rows = [
    {
        "pair_id": "p1",
        "split": "train",
        "process_type": "ccro",
        "metric": "specific_energy",
        "wave_pdf_name": "V55_CCRO_2PASS_SAFE_SOAR5000i_F100_P1R90_P2R90.pdf",
        "wave_value": "1.0",
        "aquanova_raw_value": "0.8",
        "error_pct": "-20",
        "abs_error_pct": "20",
        "pass_count_hint": "2",
    },
    {
        "pair_id": "p2",
        "split": "holdout",
        "process_type": "ccro",
        "metric": "specific_energy",
        "wave_pdf_name": "V56_CCRO_2PASS_SOAR5000i_F100_P1R90_P2R90.pdf",
        "wave_value": "1.0",
        "aquanova_raw_value": "0.8",
        "error_pct": "-20",
        "abs_error_pct": "20",
        "pass_count_hint": "2",
    },
]
layer = {
    "schema_version": "test",
    "runtime_enabled_by_default": False,
    "models": [{
        "model_id": "test_ccro_specific_energy_2pass",
        "process_type": "ccro",
        "metric": "specific_energy",
        "regime": "ccro_2pass",
        "nonnegative_output": True,
        "model_payload": {
            "delta_ratio": 0.25,
            "residual_guards": {"min_ratio": 0.55, "max_ratio": 1.65, "max_rel_delta": 0.45, "max_abs_delta": 20.0}
        }
    }]
}

with tempfile.TemporaryDirectory() as td:
    td = Path(td)
    metric_csv = td / "metric_errors.csv"
    fields = list(rows[0].keys())
    with metric_csv.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    layer_json = td / "layer.json"
    layer_json.write_text(json.dumps(layer), encoding="utf-8")
    outbase = td / "shadow"
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--metric-errors", str(metric_csv), "--layer", str(layer_json), "--output-base", str(outbase), "--print-summary"],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        check=True,
    )
    summary = json.loads((td / "shadow_v116_summary.json").read_text(encoding="utf-8"))
    assert summary["shadow_metric_row_count"] == 2, summary
    assert summary["shadow_mean_abs_error_pct"] == 0.0, summary
    assert summary["improvement_pct"] == 100.0, summary

print("V116 scope residual shadow validation selftest PASS")
