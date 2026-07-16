#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "wave_records" / "wave_v119_wide_layer_validation.py"

rows = [
    {
        "pair_id": "a",
        "split": "train",
        "process_type": "ccro",
        "metric": "feed_pressure",
        "wave_pdf_name": "V80_HRRO_1P82_R90.pdf",
        "wave_value": "9.0",
        "aquanova_raw_value": "10.0",
        "error_pct": "11.111111",
        "abs_error_pct": "11.111111",
        "wave_system_product_flow_m3h": "1.82",
        "wave_system_recovery_pct": "90",
        "wave_ccro_pf_feed_ratio_pct": "150",
    },
    {
        "pair_id": "b",
        "split": "holdout",
        "process_type": "ccro",
        "metric": "specific_energy",
        "wave_pdf_name": "V84_CCRO_1PASS_SOAR5000i_F100_R90.pdf",
        "wave_value": "1.0",
        "aquanova_raw_value": "0.8",
        "error_pct": "-20",
        "abs_error_pct": "20",
    },
]
layer = {
    "schema_version": "aquanova.wave_scope_residual_layer.v117_pass_only",
    "runtime_enabled_by_default": False,
    "models": [
        {
            "model_id": "feed_small",
            "process_type": "ccro",
            "metric": "feed_pressure",
            "regime": "ccro_small_1p82_r90_already_aligned",
            "nonnegative_output": True,
            "model_payload": {
                "prediction_mode": "bounded_residual_delta",
                "delta_ratio": -0.10,
                "residual_guards": {"min_ratio": 0.55, "max_ratio": 1.45, "max_rel_delta": 0.35, "max_abs_delta": 20.0},
            },
        },
        {
            "model_id": "sec_recovery",
            "process_type": "ccro",
            "metric": "specific_energy",
            "regime": "ccro_recovery_sweep",
            "nonnegative_output": True,
            "model_payload": {
                "prediction_mode": "bounded_residual_delta",
                "delta_ratio": 0.25,
                "residual_guards": {"min_ratio": 0.55, "max_ratio": 1.65, "max_rel_delta": 0.45, "max_abs_delta": 20.0},
            },
        },
    ],
}

with tempfile.TemporaryDirectory() as td:
    td = Path(td)
    metric_csv = td / "metric_errors.csv"
    with metric_csv.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        for row in rows:
            full = {k: row.get(k, "") for k in rows[0].keys()}
            full.update(row)
            w.writerow(full)
    layer_json = td / "layer.json"
    layer_json.write_text(json.dumps(layer), encoding="utf-8")
    outbase = td / "wide"
    subprocess.run(
        [sys.executable, str(SCRIPT), "--metric-errors", str(metric_csv), "--layer", str(layer_json), "--output-base", str(outbase), "--print-summary"],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        check=True,
    )
    summary = json.loads((td / "wide_v119_summary.json").read_text(encoding="utf-8"))
    assert summary["applied_row_count"] == 2, summary
    assert summary["applied_improvement_pct"] > 80.0, summary

print("V119 wide layer validation selftest PASS")
